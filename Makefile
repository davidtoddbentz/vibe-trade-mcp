.PHONY: install test lint format format-check check ci clean terraform-init terraform-plan terraform-apply terraform-destroy terraform-output

install:
	uv sync --all-groups

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

terraform-destroy:
	cd terraform && terraform destroy

terraform-output:
	cd terraform && terraform output
