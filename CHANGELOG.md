# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.1.0] - 17-01-2026
### Added
- Initial Project Setup
- Configured settings for databases, object storage, and authentication, including JWT and CORS settings.
- Established a structured settings module with environment-based configurations for development and production.
- Created Docker Compose files for PostgreSQL and MinIO services to support application dependencies.
- Updated `manage.py` to load environment variables and initialize tracing.
- Added cron job configurations and integrated Django Silk for profiling.
- Implemented OpenTelemetry metrics in `config/metrics.py` for tracking HTTP request durations and job run durations.
- Added OpenTelemetry tracing in `config/tracing.py` to monitor application performance and request handling.
- Included requirements for base, development, and production environments to manage dependencies effectively.

---

This changelog follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
