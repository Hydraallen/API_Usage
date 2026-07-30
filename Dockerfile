FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DOCKER_ENV=true

# Set working directory
WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir requests==2.34.2

# Copy application files
COPY zhipu_usage.py .
COPY server.py .
COPY dashboard.html .

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 8080

# Health check (uses the image's built-in python3, so curl is not needed)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8080/api/status', timeout=5).status == 200 else 1)" || exit 1

# Run server
CMD ["python3", "server.py"]
