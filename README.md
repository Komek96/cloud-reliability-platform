# Cloud Reliability & Deployment Platform

A cloud infrastructure and reliability engineering portfolio
project focused on reproducible deployment, service monitoring,
persistent data storage, and failure recovery.

## Project Status

**Phase 1: Local Application Development — Complete**

The application currently runs locally using Docker Compose.
AWS deployment, Terraform infrastructure, CI/CD, and cloud
monitoring are planned for subsequent phases.

## Technology Stack

- Python 3.12
- FastAPI
- Amazon DynamoDB Local
- boto3
- Docker and Docker Compose
- pytest
- Git and GitHub

Planned technologies:

- Amazon Web Services (AWS)
- Terraform
- GitHub Actions
- Amazon CloudWatch
- Amazon ECR
- AWS Lambda

## Implemented Features

### REST API

- GET /health — application health check
- POST /events — create an incident event
- GET /events/{event_id} — retrieve an incident event

The API validates incoming requests and returns appropriate
HTTP status codes for successful and invalid operations.

### Persistent Data Storage

Incident events are stored in DynamoDB Local.

A persistent Docker volume preserves records across container
removal and recreation.

Database initialization automatically creates the events
table when necessary without replacing an existing table.

### Docker Deployment

Four Docker Compose services manage the local environment:

1. volume-init — prepares database directory permissions
2. dynamodb — runs the local DynamoDB database
3. db-init — initializes the events table
4. app — runs the FastAPI application

Compose manages service dependencies and startup order.

### Codespaces Compatibility

A separate compose.codespaces.yaml configuration provides
a networking workaround for the GitHub Codespaces environment.

This configuration allows the API and database initializer
to share DynamoDB's network namespace.

The standard Compose configuration remains available for
environments with functioning Docker bridge networking.

### Automated Testing

Five automated pytest tests verify:

- Application health reporting
- Unknown endpoint handling
- Incident creation and retrieval
- Missing incident handling
- Invalid request rejection

Additional integration testing verified the API against
a running DynamoDB Local database.

### Persistence and Recovery

A recovery test successfully:

- Recreated the application and database containers
- Reused the existing persistent database volume
- Initialized the database without replacing its table
- Retrieved an incident record created before the restart

This verifies local database persistence across container
recreation. Automated cloud recovery is not yet implemented.

## Running Locally

Install dependencies in a Python virtual environment:

    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt

Run automated tests:

    .venv/bin/python -m pytest -v

Start the standard Docker Compose environment:

    docker compose up -d --build

For GitHub Codespaces, use both Compose files:

    docker compose -f compose.yaml \
      -f compose.codespaces.yaml up -d --build

The Codespaces configuration publishes the API on a
dynamically assigned localhost port.

Find the published API port:

    docker compose -f compose.yaml \
      -f compose.codespaces.yaml port dynamodb 8080

If the default Docker builder has corrupted image layers,
the project can be rebuilt using a dedicated BuildKit builder,
then started with the Compose --no-build option.

Stop the Codespaces stack without deleting database records:

    docker compose -f compose.yaml \
      -f compose.codespaces.yaml down

Do not add -v to the shutdown command unless intentionally
deleting the persistent database volume.

## Project Roadmap

- [x] Develop FastAPI application
- [x] Implement automated tests
- [x] Containerize the application
- [x] Integrate DynamoDB Local
- [x] Automate database initialization
- [x] Configure Docker Compose
- [x] Verify local database persistence
- [ ] Publish project repository
- [ ] Implement GitHub Actions CI/CD
- [ ] Provision AWS infrastructure with Terraform
- [ ] Configure cloud deployment
- [ ] Implement monitoring, logging, and alerts
- [ ] Demonstrate cloud failure detection and recovery
- [ ] Document security decisions and operational costs

## Security and Operational Notes

The local environment uses test credentials for DynamoDB
Local. These are not real AWS credentials.

The application runs as a non-root container user.

The event endpoints do not yet implement authentication.
They must be secured before any public cloud deployment.

No AWS resources are required for the current local setup.

## Purpose

This project demonstrates the progression from enterprise
IT operations and incident monitoring into infrastructure
engineering, automated deployment, and service reliability.

The long-term goal is to demonstrate a complete deployment
lifecycle: infrastructure provisioning, automated testing,
deployment, observability, failure investigation, and recovery.
