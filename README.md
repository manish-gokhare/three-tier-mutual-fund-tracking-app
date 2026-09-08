# Mutual Fund Tracker — Three-Tier Docker Application

This repository runs a three-tier Mutual Fund Tracking application using Docker.

The application consists of:

* **Frontend** — Express/EJS dashboard
* **Backend** — FastAPI REST API
* **NAV Updater** — AMFI NAV synchronization worker
* **Database** — PostgreSQL 16

The dashboard communicates with the FastAPI backend through the Node.js server and never connects directly to PostgreSQL.

---

# Architecture

```text
                    ┌──────────────────────┐
                    │       Browser        │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Frontend Container   │
                    │ Express / EJS        │
                    │ Port: 3000           │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Backend Container    │
                    │ FastAPI              │
                    │ Port: 8000           │
                    └──────────┬───────────┘
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
                 ▼                           ▼
       ┌──────────────────┐       ┌──────────────────┐
       │ PostgreSQL       │       │ NAV Updater      │
       │ 16-alpine        │       │ AMFI NAV Sync    │
       └────────┬─────────┘       └────────┬─────────┘
                │                          │
                └──────────┬───────────────┘
                           ▼
                   Persistent Volume
```

---

# Local Environment Setup

## Prerequisites

Install:

* Docker
* Docker Compose

Verify:

```sh
docker --version
docker compose version
```

## Configure environment variables

Create a `.env` file in the project root.

Example:

```env
# PostgreSQL
POSTGRES_USER=mf_admin
POSTGRES_PASSWORD=change_this_local_password
POSTGRES_DB=mf_tracker
POSTGRES_PORT=5432

# Application
BACKEND_PORT=8000
FRONTEND_PORT=3000
BACKEND_API_URL=http://backend:8000

# Authentication
JWT_SECRET=replace_with_a_long_random_secret
JWT_EXPIRE_MINUTES=480
COOKIE_SECURE=false

# AMFI NAV
AMFI_NAV_URL=https://portal.amfiindia.com/spages/NAVAll.txt
NAV_REFRESH_INTERVAL_SECONDS=21600
```

**Important:** Never commit the real `.env` file, database password, or production JWT secret to GitHub.

A safe `.env.example` file can be committed instead.

---

# Start the Application Locally

From the project directory:

```sh
docker compose up --build
```

The first startup initializes the PostgreSQL database with:

* A demo investor
* 50 Indian equity mutual funds
* Large, Mid, Small, Flexi and Multi Cap categories
* 60 days of deterministic fallback NAV data

The `nav_updater` service checks AMFI's official NAV report every six hours and stores the latest published end-of-day NAV.

AMFI NAV data is end-of-day data and is not an intraday price feed.

---

# Access the Application

Dashboard:

```text
http://localhost:3000
```

FastAPI Swagger documentation:

```text
http://localhost:8000/docs
```

---

# Stop and Start Containers

## Temporarily stop containers

If running in the foreground:

```sh
Ctrl+C
```

If running in detached mode:

```sh
docker compose stop
```

Start them again:

```sh
docker compose start
```

Alternatively:

```sh
docker compose up -d
```

---

# Stop and Remove Containers

To stop and remove containers and the Docker network:

```sh
docker compose down
```

**Note:** PostgreSQL data remains intact because the persistent volume is retained.

---

# Completely Reset the Database

To remove the PostgreSQL persistent volume and start with a completely fresh database:

```sh
docker compose down -v
```

Then start the application again:

```sh
docker compose up -d
```

The PostgreSQL database will be initialized again using the values from `.env`.

> **Warning:** `docker compose down -v` permanently deletes the PostgreSQL data stored in the Compose volume.

The SQL initializer runs only when PostgreSQL starts with a new data volume.

---

# Sign In

The dashboard opens on a login page.

Local demo account:

```text
Email:    demo@mftracker.local
Password: DemoPass!2026
```

Passwords use PBKDF2-SHA256 hashes in PostgreSQL.

The Node.js dashboard stores the API JWT in an `HttpOnly`, `SameSite=Lax` cookie.

For HTTPS deployments:

```env
COOKIE_SECURE=true
```

Before any non-local deployment, replace:

```env
POSTGRES_PASSWORD
JWT_SECRET
```

with strong, unique secrets.

---

# API Highlights

### Funds

```http
GET /funds
```

List funds with their latest NAV.

Optional filters:

```text
category
search
```

### NAV History

```http
GET /funds/{fund_id}/nav?days=30
```

### Authentication

```http
POST /auth/register
POST /auth/login
```

### Holdings

```http
POST /me/holdings
GET /me/holdings
```

Repeated additions are merged using a weighted purchase NAV.

### NAV Synchronization

```http
GET /nav-sync/status
```

Example holding request:

```json
{
  "fund_id": 1,
  "units": 12.5,
  "average_purchase_nav": 104.25
}
```

---

# CI/CD Pipeline

The application uses **GitHub Actions with a self-hosted Ubuntu runner** for CI/CD.

The pipeline performs:

1. Code checkout
2. Python linting using Ruff
3. Automated testing using Pytest
4. Docker image build
5. Docker image push
6. Deployment to Amazon Linux EC2

The EC2 server does **not build the Docker images**.

Images are built by the GitHub Actions self-hosted runner and pushed to a container registry. The EC2 instance pulls those images and runs them using Docker Compose.

---

# CI/CD Architecture

```text
                         Developer
                             │
                             │ git push
                             ▼
                  ┌─────────────────────┐
                  │   GitHub Repository │
                  └──────────┬──────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │   GitHub Actions    │
                  │                     │
                  │ Self-hosted Ubuntu  │
                  │ Runner              │
                  └──────────┬──────────┘
                             │
                 ┌───────────┼───────────┐
                 │           │           │
                 ▼           ▼           ▼
              Ruff        Pytest      Docker Build
                 │           │           │
                 └───────────┴───────────┘
                             │
                             ▼
                    Docker Image Push
                             │
                    ┌────────┴─────────┐
                    │                  │
                    ▼                  ▼
               Docker Hub          Amazon ECR
                             │
                             ▼
                   Amazon Linux EC2
                             │
                    docker login
                             │
                    docker pull
                             │
                             ▼
                    Docker Compose
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
      Frontend            Backend          NAV Updater
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
                             ▼
                        PostgreSQL
                             │
                             ▼
                    Persistent Volume
```

---

# GitHub Actions CI Pipeline

The CI pipeline validates the application before Docker images are published.

Example workflow:

```text
Git Push
   │
   ▼
Checkout Code
   │
   ▼
Install Python Dependencies
   │
   ▼
Ruff Lint
   │
   ▼
Pytest
   │
   ├── Failure → Stop Pipeline
   │
   ▼
Docker Build
   │
   ▼
Docker Image Push
```

If Ruff or Pytest fails, the pipeline stops and the images are not deployed.

---

# Docker Images

The application produces three application images:

```text
mf-three-tier-app-backend
mf-three-tier-app-frontend
mf-three-tier-app-nav_updater
```

PostgreSQL uses the official image:

```text
postgres:16-alpine
```

Example registry layout:

```text
Docker Hub

<dockerhub-user>/mf-three-tier-app-backend
<dockerhub-user>/mf-three-tier-app-frontend
<dockerhub-user>/mf-three-tier-app-nav_updater
```

or:

```text
Amazon ECR

<aws-account>.dkr.ecr.<region>.amazonaws.com/mf-three-tier-app-backend
<aws-account>.dkr.ecr.<region>.amazonaws.com/mf-three-tier-app-frontend
<aws-account>.dkr.ecr.<region>.amazonaws.com/mf-three-tier-app-nav_updater
```

---

# Production Docker Compose

The production EC2 deployment should use **pre-built images** rather than `build:` instructions.

Example:

```yaml
services:

  backend:
    image: <registry>/mf-three-tier-app-backend:${IMAGE_TAG}

  frontend:
    image: <registry>/mf-three-tier-app-frontend:${IMAGE_TAG}

  nav_updater:
    image: <registry>/mf-three-tier-app-nav_updater:${IMAGE_TAG}

  postgres:
    image: postgres:16-alpine
```

This is important because the EC2 server should **pull the images from the registry instead of building them locally**.

---

# Amazon Linux EC2 Deployment

The target deployment server is an **Amazon Linux EC2 instance**.

The EC2 instance is responsible for:

* Running Docker
* Running Docker Compose
* Pulling application images
* Running the application containers
* Maintaining the PostgreSQL persistent volume

The EC2 instance does not run the CI build process.

Deployment flow:

```text
GitHub Actions
      │
      │ Docker images
      ▼
Docker Hub / ECR
      │
      │ docker pull
      ▼
Amazon Linux EC2
      │
      ▼
docker compose up -d
```

---

# EC2 Deployment Directory

The application deployment files are maintained on the EC2 instance under:

```text
/opt/mftracker
```

The directory should be owned by the deployment user and have appropriate permissions.

Example:

```sh
sudo mkdir -p /opt/mftracker
sudo chown -R $USER:$USER /opt/mftracker
```

The production deployment can contain:

```text
/opt/mftracker/
├── docker-compose.yml
├── .env
└── deployment files
```

The production `.env` file should **not** be stored in GitHub.

---

# Production Environment Variables

Production credentials should be supplied securely on the EC2 instance or through a secrets-management mechanism.

Example:

```env
POSTGRES_USER=mf_admin
POSTGRES_PASSWORD=<strong-production-password>
POSTGRES_DB=mf_tracker

BACKEND_PORT=8000
FRONTEND_PORT=3000
BACKEND_API_URL=http://backend:8000

JWT_SECRET=<strong-production-secret>
JWT_EXPIRE_MINUTES=480
COOKIE_SECURE=true

AMFI_NAV_URL=https://portal.amfiindia.com/spages/NAVAll.txt
NAV_REFRESH_INTERVAL_SECONDS=21600
```

Do not commit production secrets to the repository.

---

# Production Database Persistence

PostgreSQL uses a persistent Docker volume.

```text
PostgreSQL Container
        │
        ▼
Docker Named Volume
        │
        ▼
Persistent Database Data
```

Updating the application containers does not delete the PostgreSQL data.

For example:

```sh
docker compose pull
docker compose up -d
```

will update the application containers while retaining the PostgreSQL volume.

**Do not use:**

```sh
docker compose down -v
```

on the production EC2 instance unless you intentionally want to destroy the database.

---

# CI/CD Deployment Strategy

The recommended deployment sequence is:

```text
1. Developer pushes code
          │
          ▼
2. GitHub Actions starts
          │
          ▼
3. Ruff linting
          │
          ▼
4. Pytest
          │
          ▼
5. Build Docker images
          │
          ▼
6. Tag images
          │
          ▼
7. Push images to registry
          │
          ▼
8. Connect to Amazon Linux EC2
          │
          ▼
9. Pull new images
          │
          ▼
10. Restart application containers
          │
          ▼
11. PostgreSQL volume remains intact
```

---

# Image Tagging

For production deployments, immutable image tags are preferred over relying only on `latest`.

Example:

```text
mf-three-tier-app-backend:abc1234
mf-three-tier-app-frontend:abc1234
mf-three-tier-app-nav_updater:abc1234
```

where:

```text
abc1234 = Git commit SHA
```

This makes it possible to identify exactly which version is deployed.

Example:

```text
Git Commit
    │
    ▼
abc1234
    │
    ├── backend:abc1234
    ├── frontend:abc1234
    └── nav_updater:abc1234
```

The EC2 instance then deploys the images corresponding to that commit.

---

# GitHub Actions Secrets

The following values should be configured as GitHub Actions secrets rather than committed to the repository:

```text
DOCKERHUB_USERNAME
DOCKERHUB_TOKEN
```

If using Amazon ECR:

```text
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_REGION
AWS_ACCOUNT_ID
```

If the deployment connects to EC2 through SSH, the required SSH credentials should also be stored as GitHub Actions secrets.

Prefer AWS IAM roles / short-lived credentials where possible instead of long-lived AWS access keys.

---

# Deployment Principle

The key principle of this CI/CD architecture is:

```text
                 BUILD ONCE
                     │
                     ▼
              GitHub Actions
                     │
                     ▼
              Docker Registry
                     │
             ┌───────┴───────┐
             │               │
             ▼               ▼
          Docker Hub       Amazon ECR
             │               │
             └───────┬───────┘
                     │
                     ▼
                EC2 Server
                     │
                     ▼
               PULL IMAGE
                     │
                     ▼
              RUN CONTAINER
```

The production EC2 instance **pulls pre-built images**. It does not build application images from source code.

---

# Future Kubernetes Deployment

The current Docker Compose deployment provides the foundation for a future Kubernetes deployment.

Current:

```text
GitHub
   │
   ▼
GitHub Actions
   │
   ▼
Docker Images
   │
   ▼
ECR
   │
   ▼
Amazon Linux EC2
   │
   ▼
Docker Compose
```

Future:

```text
GitHub
   │
   ▼
GitHub Actions
   │
   ▼
Docker Images
   │
   ▼
Amazon ECR
   │
   ▼
Kubernetes
   │
   ├── Frontend Deployment
   ├── Backend Deployment
   ├── NAV Updater
   └── PostgreSQL + Persistent Storage
```

This allows the project to evolve from a Docker Compose-based deployment to a Kubernetes-based deployment without changing the fundamental image build and registry workflow.
