FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py \
    FLASK_ENV=production \
    DATABASE_URL=sqlite:////data/app.db \
    RUNNING_IN_DOCKER=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    sqlite3 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Gunicorn
RUN pip install --no-cache-dir gunicorn

# Copy application code
COPY . .

# Create data directory for SQLite database and initialize an empty database
RUN mkdir -p /data && \
    chmod 777 /data && \
    sqlite3 /data/app.db "PRAGMA journal_mode=WAL;" && \
    chmod 666 /data/app.db

# Make the startup script executable
RUN chmod +x start.py

# Create non-root user and give appropriate permissions
RUN useradd -m appuser && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /data

USER appuser

# Run the startup script
CMD ["python", "start.py"]