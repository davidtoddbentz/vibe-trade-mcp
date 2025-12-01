.PHONY: install run emulator seed seed-dry-run test lint format format-check check ci clean \
	terraform-init terraform-plan terraform-apply terraform-apply-auto terraform-destroy terraform-output terraform-validate terraform-fmt \
	docker-build docker-push docker-build-push deploy deploy-image deploy-info force-revision

install:
	uv sync --all-groups

# Start Firestore emulator using Docker (no Java/Xcode needed)
emulator:
	@echo "🔥 Starting Firestore emulator in background (Docker)..."
	@docker stop firestore-emulator 2>/dev/null || true
	@docker rm firestore-emulator 2>/dev/null || true
	@docker run -d --name firestore-emulator -p 8081:8080 -e FIRESTORE_PROJECT_ID=demo-project mtlynch/firestore-emulator-docker
	@sleep 3
	@echo "✅ Emulator running in background (container: firestore-emulator)"
	@echo "   Stop it with: make emulator-stop"

# Stop background emulator
emulator-stop:
	@echo "🛑 Stopping Firestore emulator..."
	@docker stop firestore-emulator 2>/dev/null || echo "   Emulator not running"
	@docker rm firestore-emulator 2>/dev/null || true
	@echo "✅ Emulator stopped"

# Check if emulator is running
check-emulator:
	@if ! nc -z localhost 8081 2>/dev/null; then \
		echo "❌ Firestore emulator is not running on localhost:8081"; \
		echo "   Start it with: make emulator (in another terminal)"; \
		exit 1; \
	fi

# Run the server locally
# Uses emulator if FIRESTORE_EMULATOR_HOST is set in .env, otherwise production
run:
	@bash -c '\
	if [ -f .env ]; then \
		export $$(grep -v "^#" .env | xargs); \
	fi; \
	if [ -z "$$FIRESTORE_EMULATOR_HOST" ] && [ -z "$$GOOGLE_CLOUD_PROJECT" ]; then \
		echo "⚠️  Warning: Neither FIRESTORE_EMULATOR_HOST nor GOOGLE_CLOUD_PROJECT set"; \
		echo "   For local dev: export FIRESTORE_EMULATOR_HOST=localhost:8081"; \
		echo "   For production: export GOOGLE_CLOUD_PROJECT=vibe-trade-475704"; \
	fi; \
	if [ -n "$$FIRESTORE_EMULATOR_HOST" ]; then \
		nc -z localhost 8081 2>/dev/null || (echo "❌ Firestore emulator is not running on localhost:8081"; echo "   Start it with: make emulator"; exit 1); \
		echo "✅ Firestore emulator is running"; \
	fi; \
	echo "🚀 Starting MCP server..."; \
	if [ -n "$$FIRESTORE_EMULATOR_HOST" ]; then \
		echo "   Using Firestore Emulator: $$FIRESTORE_EMULATOR_HOST"; \
	else \
		echo "   Using Production Firestore: $$GOOGLE_CLOUD_PROJECT"; \
	fi; \
	echo "   Endpoint: http://localhost:8080/mcp"; \
	uv run main'

# Seed archetypes into database
seed:
	@echo "🌱 Seeding archetypes..."
	uv run python -m src.scripts.seed_archetypes

# Dry run seed (see what would be done)
seed-dry-run:
	@echo "🌱 [DRY RUN] Seeding archetypes..."
	uv run python -m src.scripts.seed_archetypes --dry-run

# Seed to production (requires GOOGLE_CLOUD_PROJECT set)
seed-prod:
	@echo "🌱 Seeding archetypes to production..."
	@if [ -z "$$GOOGLE_CLOUD_PROJECT" ]; then \
		echo "❌ Error: GOOGLE_CLOUD_PROJECT not set"; \
		echo "   Set it with: export GOOGLE_CLOUD_PROJECT=vibe-trade-475704"; \
		exit 1; \
	fi
	@if [ -n "$$FIRESTORE_EMULATOR_HOST" ]; then \
		echo "⚠️  Warning: FIRESTORE_EMULATOR_HOST is set - this will seed the emulator, not production!"; \
		echo "   Unset it with: unset FIRESTORE_EMULATOR_HOST"; \
		exit 1; \
	fi
	uv run python -m src.scripts.seed_archetypes

test:
	uv run pytest tests/ -v

test-cov:
	uv run pytest tests/ --cov=src --cov-report=term-missing --cov-report=html --cov-fail-under=60

lint:
	uv run ruff check .

lint-fix:
	uv run ruff check . --fix

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

check: lint format-check test-cov
	@echo "✅ All checks passed!"

ci: lint-fix format-check test-cov
	@echo "✅ CI checks passed!"

clean:
	find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov/ coverage.xml
	rm -rf *.egg-info build/ dist/

# Terraform commands
terraform-init:
	cd terraform && terraform init

terraform-plan:
	cd terraform && terraform plan

terraform-apply:
	cd terraform && terraform apply

terraform-apply-auto:
	cd terraform && terraform apply -auto-approve

terraform-destroy:
	cd terraform && terraform destroy

terraform-output:
	cd terraform && terraform output

terraform-validate:
	cd terraform && terraform validate

terraform-fmt:
	cd terraform && terraform fmt

# Docker commands - get values from terraform
TERRAFORM_IMAGE_REPO := $(shell cd terraform && terraform output -raw artifact_registry_url 2>/dev/null || echo "us-central1-docker.pkg.dev/vibe-trade-475704/vibe-trade-mcp")
IMAGE_TAG := $(TERRAFORM_IMAGE_REPO)/vibe-trade-mcp:latest

docker-build:
	@echo "🏗️  Building Docker image..."
	@echo "   Image: $(IMAGE_TAG)"
	docker build --platform linux/amd64 -t $(IMAGE_TAG) .
	@echo "✅ Build complete"

docker-push:
	@echo "📤 Pushing Docker image..."
	@echo "   Image: $(IMAGE_TAG)"
	docker push $(IMAGE_TAG)
	@echo "✅ Push complete"

docker-build-push: docker-build docker-push

# Deployment workflow
deploy: docker-build-push terraform-apply-auto force-revision
	@echo ""
	@echo "✅ Deployment complete!"
	@echo ""
	@echo "📋 Service Information:"
	@cd terraform && terraform output mcp_endpoint 2>/dev/null || echo "Run 'make terraform-output' for details"

# Force Cloud Run to create a new revision with the latest image
force-revision:
	@echo "🔄 Forcing Cloud Run to use latest image..."
	@cd terraform && \
		SERVICE_NAME=$$(terraform output -raw service_name 2>/dev/null || echo "vibe-trade-mcp") && \
		REGION=$$(terraform output -raw region 2>/dev/null || echo "us-central1") && \
		PROJECT_ID=$$(terraform output -raw project_id 2>/dev/null || echo "vibe-trade-475704") && \
		IMAGE_REPO=$$(terraform output -raw artifact_registry_url 2>/dev/null || echo "us-central1-docker.pkg.dev/vibe-trade-475704/vibe-trade-mcp") && \
		echo "   Service: $$SERVICE_NAME" && \
		echo "   Region: $$REGION" && \
		echo "   Image: $$IMAGE_REPO/vibe-trade-mcp:latest" && \
		gcloud run services update $$SERVICE_NAME \
			--region=$$REGION \
			--project=$$PROJECT_ID \
			--image=$$IMAGE_REPO/vibe-trade-mcp:latest \
			2>&1 | grep -E "(Deploying|revision|Service URL|Done)" || (echo "⚠️  Update may have failed or no changes needed" && exit 1)

deploy-image: docker-build-push
	@echo ""
	@echo "✅ Image deployed!"
	@echo "📋 Run 'make terraform-apply-auto' to update Cloud Run service with new image"

# Get deployment info
deploy-info:
	@echo "📋 Service Information:"
	@cd terraform && terraform output 2>/dev/null || echo "⚠️  Terraform not initialized or no outputs available. Run 'make terraform-init' first."
