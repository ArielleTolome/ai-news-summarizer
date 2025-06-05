FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY templates/ ./templates/

# Create necessary directories
RUN mkdir -p output cache metrics github_repo

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Default command
CMD ["python", "-m", "src.pipeline.news_pipeline"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Expose port for potential web interface (future enhancement)
EXPOSE 8000

# Volume mounts for persistent data
VOLUME ["/app/output", "/app/cache", "/app/github_repo"]

# Labels
LABEL maintainer="AI News Summarizer"
LABEL version="1.0.0"
LABEL description="Automated AI-powered news summarization pipeline"