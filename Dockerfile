FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DOCKER_ENV=true

# Set working directory
WORKDIR /app

# NOTE: there is deliberately no `RUN pip install` and no `RUN apt-get` here.
# The application uses the Python standard library only (urllib.request +
# json + http.server), so the build needs ZERO network access. That matters on
# hosts with flaky egress, where a pypi.org round trip is the single most
# likely reason a build fails.

# Copy application files
COPY zhipu_usage.py .
COPY server.py .
COPY dashboard.html .

# Create data directory
RUN mkdir -p /app/data

# Port inside the container. The host port is chosen by the compose mapping.
ENV PORT=8080
EXPOSE 8080

# Health check (uses the image's built-in python3, so curl is not needed).
# The port is read from $PORT at runtime, so it cannot drift out of sync with
# the `environment:` block in docker-compose.yml.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import os,urllib.request,sys; p=os.environ.get('PORT','8080'); sys.exit(0 if urllib.request.urlopen('http://localhost:'+p+'/api/status', timeout=5).status == 200 else 1)" || exit 1

# Run server
CMD ["python3", "server.py"]
