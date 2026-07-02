FROM python:3.13-slim

LABEL description="Online Everywhere LinkedIn Agent"
LABEL maintainer="Online Everywhere"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY mcp_servers/ mcp_servers/
COPY templates/ templates/
COPY telegram_bot.py .
COPY entrypoint.sh .

# Create directories
RUN mkdir -p /app/assets /app/data

# Default shell entrypoint
ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]
