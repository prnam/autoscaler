# Stage 1: Test stage
FROM python:3.12.1-alpine as test-stage

# Set working directory
WORKDIR /app

# Install dependencies in a separate layer for better caching
COPY requirements-test.txt .
RUN pip install --no-cache-dir -r requirements-test.txt

# Copy application code
COPY autoscaler.py test_autoscaler.py ./ 

# Run Bandit security checks
RUN bandit -r autoscaler.py

# Run tests
RUN pytest

# Stage 2: Application stage
FROM python:3.12.1-alpine as release-stage

# Set working directory
WORKDIR /app

# Copy application code from the previous stage
COPY --from=test-stage /app /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Define environment variables with default values
ENV HOST=0.0.0.0 \
    PORT=8123 \
    USE_HTTPS=false \
    TARGET_CPU_USAGE=0.80 \
    POLLING_INTERVAL=15 \
    RETRY_COUNT=5 \
    RETRY_DELAY=2

# Run autoscaler.py when the container launches
CMD python autoscaler.py \
    --host ${HOST} \
    --port ${PORT} \
    $(if [ "${USE_HTTPS}" = "true" ] ; then echo "--https"; fi) \
    --target-cpu-usage ${TARGET_CPU_USAGE} \
    --polling-interval ${POLLING_INTERVAL} \
    --retry-count ${RETRY_COUNT} \
    --retry-delay ${RETRY_DELAY}