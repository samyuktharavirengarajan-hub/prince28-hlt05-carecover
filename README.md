
# CareCover

Tells a family whether a treatment is covered under Ayushman Bharat PM-JAY and Tamil Nadu's CMCHIS, the package rate, and which empanelled hospitals offer it.

**Status:** Day 4 foundation complete — FastAPI, PostgreSQL, Docker Compose, migrations, and automated tests. Live URL from Day 5.

## Who it's for

Daughter of a daily-wage worker in Vellore whose father needs a knee replacement and who does not know which scheme covers it.

## The problem

Health benefit package lists contain hundreds of procedures with different package codes, rates, pre-authorisation rules and hospital restrictions. Tamil Nadu's CMCHIS has its own package list, which may overlap with PM-JAY. Families find it difficult to compare the schemes and identify the correct coverage and eligible hospitals.

## Data sources

NHA Health Benefit Packages (HBP 2022) manual and package master, PM-JAY guidelines and FAQs, CMCHIS Tamil Nadu package list and hospital list.

- https://pmjay.gov.in/
- https://nha.gov.in/
- https://www.cmchistn.com/

Terms: Public scheme documents. Cite package codes and document dates.

## Hardest problem (my interview story)

Two schemes with overlapping packages: PM-JAY and CMCHIS have different codes, rates and rules for the same procedure, and some packages are reserved for government hospitals. Answers must say which scheme, which code and which hospital type, never mixing rates.

## Signature feature

Package card: procedure shown with the PM-JAY code and rate next to the CMCHIS code and rate, with 'pre-auth needed' and 'govt hospital only' badges.

## Target metric

Correct scheme + code + rate for 90%+ of 50 procedure questions.

## Run locally with Docker (recommended)

Requirements:
- Docker Desktop
- Docker Compose

Start the complete application:

```bash
docker compose up --build -d
```

Services:
- API: http://localhost:8001
- Swagger documentation: http://localhost:8001/docs
- PostgreSQL: localhost:5433
- Redis: localhost:6379

Check service health:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs -f
```

Stop the stack while preserving database data:

```bash
docker compose down
```

Remove containers and database volumes:

```bash
docker compose down -v
```

## Run locally without Docker

Requirements: Python 3.12 and uv.

```bash
uv sync
```

Copy `.env.example` to `.env` and configure the database connection.

Apply migrations and load sample data:

```bash
uv run poe migrate
uv run poe seed
```

Start the API:

```bash
uv run poe dev
```

Open http://localhost:8000/docs

## Tests and quality checks

Run unit tests:

```bash
uv run poe test
```

Run PostgreSQL integration tests (requires Docker Compose database):

```bash
uv run poe test-integration
```

Run all tests with coverage:

```bash
uv run poe cov
```

Run lint and formatting checks:

```bash
uv run poe lint
```

## Makefile shortcuts

On systems with GNU Make:

```bash
make up
make down
make logs
make ps
make test
make test-integration
make cov
make lint
make migrate
make seed
```
