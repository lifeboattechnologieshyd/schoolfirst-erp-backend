#!/bin/bash
set -e

############################################
# Defaults (override via environment)
############################################
HTTP_PORT=${HTTP_PORT:-8000}

GUNICORN_WORKERS=${GUNICORN_WORKERS:-1}
GUNICORN_THREADS_PER_WORKER=${GUNICORN_THREADS_PER_WORKER:-8}

PROJECT_ROOT_DIR=${PROJECT_ROOT_DIR:-"/project"}
LOG_DIR=${LOG_DIR:-"/logs"}

DEPLOYMENT_MODE=${DEPLOYMENT_MODE:-"FULL"}  # API | CRON | FULL

############################################
# Validation
############################################
if ! [[ "$HTTP_PORT" =~ ^[0-9]+$ ]] || [ "$HTTP_PORT" -le 0 ] || [ "$HTTP_PORT" -gt 65535 ]; then
    echo "❌ Invalid HTTP_PORT: $HTTP_PORT"
    exit 1
fi

############################################
# Logging
############################################
echo "========================================"
echo "Starting application with configuration:"
echo "HTTP_PORT                   = $HTTP_PORT"
echo "GUNICORN_WORKERS            = $GUNICORN_WORKERS"
echo "GUNICORN_THREADS_PER_WORKER = $GUNICORN_THREADS_PER_WORKER"
echo "PROJECT_ROOT_DIR            = $PROJECT_ROOT_DIR"
echo "LOG_DIR                     = $LOG_DIR"
echo "DEPLOYMENT_MODE             = $DEPLOYMENT_MODE"
echo "========================================"

############################################
# Export env vars for cron (OPTION 1)
############################################
echo "Exporting environment variables for cron..."
printenv | grep -vE '^(no_proxy|NO_PROXY)=' > /etc/environment

############################################
# Prepare filesystem
############################################
mkdir -p "${PROJECT_ROOT_DIR}${LOG_DIR}"

cd "$PROJECT_ROOT_DIR"

############################################
# Django setup
############################################
echo "Running migrations..."
python manage.py migrate

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Cleaning stale cron locks..."
python manage.py remove_cronjob_locks || true


############################################
# Cron handling
############################################
start_cron() {
    if command -v cron >/dev/null 2>&1; then
        echo "Starting cron (cron)..."
        cron
    elif command -v crond >/dev/null 2>&1; then
        echo "Starting cron (crond)..."
        crond
    elif [ -x /etc/init.d/cron ]; then
        echo "Starting cron (/etc/init.d/cron)..."
        /etc/init.d/cron start
    else
        echo "⚠️ Cron not available; skipping"
    fi
}

############################################
# Signal handling
############################################
terminate() {
    echo "Received termination signal"
    exit 0
}

trap terminate SIGTERM SIGINT

############################################
# Deployment modes
############################################

############################################
# CRON-only mode
############################################
if [ "$DEPLOYMENT_MODE" = "CRON" ]; then
    echo "Configuring CRON-only mode"
    start_cron
    python manage.py crontab add

    echo "CRON mode active; waiting indefinitely"
    exec sleep infinity
fi

############################################
# API-only mode
############################################
if [ "$DEPLOYMENT_MODE" = "API" ]; then
    echo "Starting API-only mode"
    exec gunicorn \
        --bind "0.0.0.0:${HTTP_PORT}" \
        --workers "${GUNICORN_WORKERS}" \
        --threads "${GUNICORN_THREADS_PER_WORKER}" \
        --worker-class gthread \
        --timeout 300 \
        --graceful-timeout 400 \
        --keep-alive 5 \
        --max-requests 1000 \
        --max-requests-jitter 200 \
        --access-logfile "-" \
        --error-logfile "-" \
        --log-level info \
        settings.wsgi:application
fi

############################################
# FULL mode (API + CRON)
############################################
echo "Starting FULL mode (API + CRON)"

start_cron
python manage.py crontab add

exec gunicorn \
    --bind "0.0.0.0:${HTTP_PORT}" \
    --workers "${GUNICORN_WORKERS}" \
    --threads "${GUNICORN_THREADS_PER_WORKER}" \
    --worker-class gthread \
    --timeout 300 \
    --graceful-timeout 400 \
    --keep-alive 5 \
    --max-requests 1000 \
    --max-requests-jitter 200 \
    --access-logfile "-" \
    --error-logfile "-" \
    --log-level info \
    settings.wsgi:application
