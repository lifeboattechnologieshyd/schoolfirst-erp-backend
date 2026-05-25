# SamsR-BACKEND

## Setup Builder

`docker buildx create --name container-builder --driver docker-container --bootstrap --use`

## Use Builder

`docker buildx use container-builder`

## Build Image

`docker buildx build --platform linux/amd64,linux/arm64 -t schoolfirst-backend:latest --load .`

## Push Image

`docker push schoolfirst-backend:latest`

## Build and Push

`docker buildx build --platform linux/amd64,linux/arm64 -t schoolfirst-backend:latest --push .`

## Pull Image

`docker pull schoolfirst-backend:latest`

## Local Setup

1. Create virtual environment: ```python3.14 -m venv .venv```
2. Activate virtual environment: ```source .venv/bin/activate```
3. Install dependencies: ```pip install -r requirements/development.txt```
4. Create .env file with necessary environment variables (refer to .env.example for guidance)
5. Run the migrations: ```python manage.py migrate```
6. Create the admin user if needed: ```python manage.py create_admin_user --email admin@schoolfirst.us --password Admin@123 --first-name John --last-name Doe```
7. Start the development server: ```python manage.py runserver```

Note:- If using docker for local development, run ```docker compose -f ./deploy/compose/docker-compose.yaml up -d --build --remove-orphans postgres qdrant mailpit``` to start the necessary services, before running the migrations and starting the development server.

## AI Agent Instructions

This project uses a three-layer instruction set for AI agents:

- **[AGENTS.md](AGENTS.md)** - Workflow, validation order, escalation, and instruction maintenance
- **[.github/copilot-instructions.md](.github/copilot-instructions.md)** - Technical codebase details, architecture, and conventions
- **[.agents/skills/README.md](.agents/skills/README.md)** - Task-scoped skills for common work such as backend API changes, backend debugging, and instruction maintenance

Use all three together: AGENTS for how to work, copilot instructions for repo rules, and skills for focused task checklists.
