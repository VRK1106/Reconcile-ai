FROM python:3.10-slim

WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and assets
COPY backend/ ./backend/
COPY console/ ./console/
COPY data/ ./data/
COPY src/ ./src/
COPY README.md .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

# Expose port (default 7860 for Hugging Face Spaces / Render)
EXPOSE 7860

# Universal start command supporting $PORT override
CMD ["sh", "-c", "uvicorn backend.api.server:app --host 0.0.0.0 --port ${PORT:-7860}"]
