FROM python:3.11-slim

WORKDIR /app

# Install uv for linux/amd64
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN chmod +x /usr/local/bin/uv

# Copy dependency files and source code (needed for package installation)
COPY pyproject.toml ./
COPY uv.lock ./
COPY src/ ./src/
COPY data/ ./data/

# Install dependencies
RUN uv sync --no-dev --frozen

# Expose port (Cloud Run uses PORT env var, default to 8080)
ENV PORT=8080
EXPOSE 8080

# Run the server
CMD ["uv", "run", "python", "-m", "src.main"]

