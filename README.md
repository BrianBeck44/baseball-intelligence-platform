# Baseball Intelligence Platform

A portfolio-grade, end-to-end baseball analytics and intelligence platform built to demonstrate modern data engineering, backend development, analytics, SQL, and frontend engineering.

## Project Overview

The Baseball Intelligence Platform will ingest baseball data from external sources, transform and model that data in PostgreSQL, calculate advanced baseball metrics, expose analytical capabilities through a FastAPI backend, and present insights through a React application.

The project is being designed and built as a realistic production-style system rather than simply a baseball statistics website.

### Core Architecture

```text
External Baseball Data
        │
        ▼
Data Ingestion
(Python)
        │
        ▼
PostgreSQL
Raw → Core → Analytical
        │
        ▼
FastAPI
Routes → Services → Repositories
        │
        ▼
React + TypeScript
        │
        ▼
Baseball Intelligence
```

## Technology Stack

| Layer               | Technology                   |
| ------------------- | ---------------------------- |
| Database            | PostgreSQL                   |
| Backend             | Python                       |
| API                 | FastAPI                      |
| Data Processing     | Python + SQL                 |
| Frontend            | React + TypeScript           |
| Styling             | Tailwind CSS                 |
| Database Migrations | Alembic                      |
| Testing             | pytest + React testing tools |
| Containers          | Docker / Docker Compose      |
| Version Control     | Git / GitHub                 |
| Documentation       | Markdown                     |

## Project Goals

The primary goals of this project are to demonstrate practical experience with:

* Relational database design
* Advanced SQL
* Data modeling and data warehousing concepts
* Data ingestion and ETL/ELT pipelines
* Python development
* FastAPI and REST API design
* Service-layer architecture
* Repository patterns
* Baseball analytics and statistical modeling
* React and TypeScript
* Automated testing
* Docker and containerization
* CI/CD
* System architecture
* Technical documentation

## Architecture Principles

The project will follow several core principles:

### 1. Data First

Data sources, data quality, data modeling, and table grain will be established before application features are built.

### 2. Grain Before Schema

Every analytical table will have a clearly defined grain before its schema is designed.

### 3. Separation of Responsibilities

The system will maintain clear boundaries between:

```text
Data Ingestion
      ↓
Data Storage
      ↓
Data Transformation
      ↓
Analytics
      ↓
API
      ↓
Frontend
```

### 4. SQL as a First-Class Tool

SQL will be used extensively for data transformation, aggregation, analytical calculations, and complex querying.

Python will complement SQL rather than replace it.

### 5. Architecture Decisions Are Documented

Important technical decisions will be recorded as Architecture Decision Records (ADRs).

Examples include:

* Frontend framework
* Primary data source
* Database architecture
* Data modeling strategy
* API architecture
* Analytics architecture
* Deployment strategy

## Documentation

Project documentation will be maintained in the `docs/` directory.

Planned documentation includes:

```text
docs/
├── 00-project-charter.md
├── 01-data-strategy.md
├── 02-database-architecture.md
├── 03-data-pipeline.md
├── 04-api-architecture.md
├── 05-analytics.md
└── adr/
```

## Development Roadmap

### Project 0 — System Architecture & Project Charter

Establish the overall vision, scope, technology stack, architecture, and engineering principles.

**Status:** Complete

### Project 1 — Data Architecture & Database Design

Define:

* Data sources
* Entities
* Relationships
* Table grain
* Primary and foreign keys
* Constraints
* Indexes
* Raw/core/analytical data layers

**Status:** Complete

### Project 2 — Data Ingestion Pipeline

Build the Python-based pipeline responsible for acquiring, validating, and loading baseball data.

**Status:** Complete

### Project 3 — Analytics & Advanced SQL

Develop analytical transformations, baseball metrics, player analysis, team analysis, and advanced SQL queries.

**Status:** In Progress

### Project 4 — FastAPI Backend

Build the REST API and application/service architecture.

**Status:** Planned

### Project 5 — React Application

Build the user-facing baseball intelligence interface using React, TypeScript, and Tailwind CSS.

**Status:** In Progress

The initial Vite + React + TypeScript app lives in `frontend/`. It
loads player game history from `GET /players/{player_id}/games`. Setup
and run instructions are in `frontend/README.md`.

### Project 6 — Testing & Quality

Implement unit, integration, API, and data-quality testing.

**Status:** Planned

### Project 7 — Infrastructure & Deployment

Implement Docker, CI/CD, deployment, logging, and production-oriented infrastructure.

**Status:** Planned

### Project 8 — Portfolio & Documentation

Prepare the final project for portfolio presentation, including architecture documentation, technical walkthroughs, and project demonstrations.

**Status:** Planned

## Current Focus

The immediate focus is **Project 0 — Data Source & Data Strategy**.

Before designing the database, the project will evaluate potential baseball data sources based on:

* Data richness
* Historical coverage
* Data granularity
* API accessibility
* Reliability
* Rate limits
* Cost
* Licensing and portfolio usage
* Historical backfill capabilities
* Incremental update capabilities

The selected source will become a documented architectural decision.

## Architecture Decision Records

Architectural decisions will be tracked in:

```text
docs/adr/
```

### Current Decisions

| ADR     | Decision                         | Status   |
| ------- | -------------------------------- | -------- |
| ADR-001 | React + TypeScript for frontend  | Accepted |
| ADR-002 | Primary baseball data source     | Pending  |
| ADR-003 | PostgreSQL database architecture | Pending  |
| ADR-004 | Data ingestion architecture      | Pending  |
| ADR-005 | FastAPI application architecture | Pending  |

## Project Philosophy

This project is being developed with an emphasis on **engineering reasoning rather than simply producing working code**.

Important decisions will be documented along the way, including the problems considered, alternatives evaluated, tradeoffs, and reasons for the final decision.

The goal is to build a system that can be explained in a technical interview from the data source all the way through the database, API, analytics, and frontend.

---

## License

License to be determined.

## Project Status

🚧 **Active Development — Project 0**
