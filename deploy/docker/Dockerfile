# Define Base Image
FROM python:3.14-slim-bookworm AS base


# ---- Python Build Stage ----
FROM base AS python-build-stage


# Install system dependencies required for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    # dependencies for building Python packages
    build-essential \
    gcc \
    libpq-dev \
    python3-dev


# Copy dependency files
COPY requirements.txt ./
COPY requirements ./requirements

# Create Python Dependency and Sub-Dependency Wheels.
RUN pip wheel --wheel-dir /usr/src/app/wheels  \
    -r requirements.txt


# ---- Alloy Download Stage ----
FROM base AS alloy-download-stage

ARG ALLOY_VERSION=1.11.0
ARG TARGETARCH
ARG BUILDPLATFORM

WORKDIR /tmp

RUN echo "Running on ${BUILDPLATFORM} for ${TARGETARCH}"

RUN apt-get update && apt-get install --no-install-recommends -y \
    curl unzip ca-certificates && \
    curl -LO "https://github.com/grafana/alloy/releases/download/v${ALLOY_VERSION}/alloy-linux-${TARGETARCH}.zip" && \
    unzip alloy-linux-${TARGETARCH}.zip && \
    chmod +x alloy-linux-${TARGETARCH} && \
    mv alloy-linux-${TARGETARCH} alloy


# ---- Final Stage ----
FROM base AS final

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /project/

# 1. Install system dependencies required for running (Static)
RUN apt-get update && apt-get install --no-install-recommends -y \
    cron \
    libpq5 \
    procps \
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/*

# 2. Copy and install python dependencies (Only changes on requirements change)
COPY --from=python-build-stage /usr/src/app/wheels  /wheels/
RUN pip install --no-cache-dir --no-index --find-links=/wheels/ /wheels/* \
    && rm -rf /wheels/

# 3. Setup non-code tools and scripts (Alloy, entrypoints)
# These change less frequently than the application code.
COPY --from=alloy-download-stage /tmp/alloy /usr/local/bin/alloy
RUN chmod +x /usr/local/bin/alloy

COPY deploy/docker/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY deploy/docker/prestop.sh /usr/local/bin/prestop.sh
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/prestop.sh || true

# 4. Copy actual project code (Finally)
# This layer is most likely to change, so it's kept at the end.
COPY . /project/

# Make project scripts executable (depends on project code)
RUN chmod +x /project/scripts/* || true

# Expose ports
EXPOSE 8000 12345

# Use the entrypoint to run migrations, start cron, and launch Gunicorn
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
