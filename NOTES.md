
# Day 3 — PostgreSQL Migration Evidence
## D03

## 1. Database Setup

- Database: Neon PostgreSQL
- Database name: neondb
- PostgreSQL version: 18.7
- Connection: Direct connection using asyncpg
- SSL: Required

## 2. Database Migrations

Created two Alembic migrations.

### Migration 1 — Documents and Pages

Revision: `8ca236ce4f07`

Created:
- `documents` table
- `pages` table
- Primary keys
- Foreign key from pages to documents
- Unique constraint on document external_id
- Unique constraint on document_id and page_no
- Check constraint ensuring page_no >= 1
- Indexes for document lookup

Command:
`uv run alembic upgrade head`

### Migration 2 — GIN Index

Revision: `29711785f078`

Created:
- GIN index: `ix_documents_metadata_gin`
- PostgreSQL JSONB operator class: `jsonb_path_ops`

This index supports efficient JSONB containment queries.

### Migration Verification

Rollback command:
`uv run alembic downgrade -1`

Verified current revision:
`8ca236ce4f07`

Re-applied migration:
`uv run alembic upgrade head`

Migration history:

```text
8ca236ce4f07 -> 29711785f078 (head), add gin index on metadata
<base> -> 8ca236ce4f07, create documents and pages
```

## 3. Idempotent Data Loader

Script: `scripts/load_db.py`

The loader uses SHA-256 fingerprints to detect changes in source records.

### Run 1 — Initial insertion

```text
Inserted: 20
Updated: 0
Unchanged: 0
```

### Run 2 — Same input

```text
Inserted: 0
Updated: 0
Unchanged: 20
```

This confirms that running the loader again does not create duplicate records.

### Run 3 — Modified record

After changing the title of PMJAY001:

```text
Inserted: 0
Updated: 1
Unchanged: 19
```

This confirms that the loader updates only records whose content has changed.

## 4. EXPLAIN ANALYZE Experiment

Script: `scripts/explain.py`

Query:

```sql
EXPLAIN ANALYZE
SELECT id, title
FROM documents
WHERE metadata @> CAST(:filter AS jsonb);
```

Filter used:

```json
{"scheme": "CMCHIS"}
```

### Experiment 1 — Default Query Plan

Actual PostgreSQL output:

```text
Seq Scan on documents
(cost=0.00..11.00 rows=1 width=36)
(actual time=0.558..0.944 rows=10.00 loops=1)

Filter: (metadata @> '{"scheme": "CMCHIS"}'::jsonb)

Rows Removed by Filter: 10

Execution Time: 0.971 ms
```

PostgreSQL selected a Sequential Scan and checked all 20 records. It returned 10 matching records.

### Experiment 2 — Sequential Scan Disabled

Actual PostgreSQL output:

```text
Bitmap Heap Scan on documents
(cost=12.81..16.82 rows=1 width=36)
(actual time=1.374..1.379 rows=10.00 loops=1)

Recheck Cond: (metadata @> '{"scheme": "CMCHIS"}'::jsonb)

-> Bitmap Index Scan on ix_documents_metadata_gin
   (cost=0.00..12.81 rows=1 width=0)
   (actual time=1.348..1.348 rows=10.00 loops=1)

Execution Time: 1.431 ms
```

This confirms that PostgreSQL can use the GIN index for JSONB containment queries.

## 5. Technical Understanding

### Why did PostgreSQL choose Sequential Scan?

The documents table contains only 20 records. Scanning the entire table is inexpensive, so PostgreSQL estimates that a Sequential Scan is cheaper than using an index.

### When is a GIN index useful?

A GIN index is useful when:
- A table contains a large number of records.
- Queries frequently filter JSONB columns.
- JSONB containment queries use the `@>` operator.
- Index-based filtering can reduce the number of rows PostgreSQL needs to inspect.

### Why was the index plan slower in this experiment?

The table is very small. Index lookup and heap access introduce additional overhead. Therefore, the index plan took 1.431 ms, while the Sequential Scan took 0.971 ms.

Disabling sequential scans was only an experiment to demonstrate index usage. It is not a recommended production setting.

## 6. Key Learning Outcomes

- Understood PostgreSQL database connectivity using SQLAlchemy async and asyncpg.
- Created database tables using Alembic migrations.
- Learned how to roll back and re-apply migrations.
- Understood JSONB storage and GIN indexing.
- Implemented an idempotent loader using SHA-256 fingerprints.
- Migrated API document retrieval from JSON storage to PostgreSQL.
- Understood query execution plans using EXPLAIN ANALYZE.
- Verified that PostgreSQL can use the GIN index for JSONB filtering.


# Day 4 — Docker, Compose and Automated Testing

## 1. Multi-stage Dockerfile

Created a production-oriented multi-stage Dockerfile.

### Build stage
- Base image: Python 3.12 slim
- Installed pinned uv version 0.11.32
- Used `uv sync --locked` for reproducible dependency installation.
- Used Docker cache mounts to avoid repeatedly downloading dependencies.

### Runtime stage
- Copied only the required virtual environment and application files.
- Created a non-root `app` user.
- Exposed port 8000.
- Configured Uvicorn to run the FastAPI application.

### Build verification
- Built successfully using `docker build -t carecover:dev .`
- Image disk usage: approximately 300 MB.
- Image content size: approximately 70 MB.
- Verified that unchanged layers were cached during rebuilds.
- Verified that code changes rebuilt the required application layer.

## 2. Docker Compose Stack

Created `docker-compose.yml` to run the application and its dependencies.

Services:

- PostgreSQL with pgvector, version 17
- Redis 7 Alpine
- Migration and sample-data loading service
- FastAPI application

### Port mapping

- API: localhost:8001 → container:8000
- PostgreSQL: localhost:5433 → container:5432
- Redis: localhost:6379

### Startup dependencies

- PostgreSQL and Redis have health checks.
- Migration service waits for PostgreSQL to become healthy.
- API waits for PostgreSQL, Redis and successful migration completion.

### Database initialization

Created `docker/initdb/01-create-test-db.sql` to create a separate `app_test` database when PostgreSQL initializes a new volume.

## 3. Docker Stack Verification

Commands used:

```bash
docker compose config
docker compose up --build -d
docker compose ps
```

Verified:
- Docker Compose configuration was valid.
- PostgreSQL became healthy.
- Redis became healthy.
- Migration service completed successfully.
- API became healthy.
- Swagger documentation was accessible at `/docs`.
- `GET /v1/documents` returned HTTP 200 with 20 records.

## 4. Liveness and Readiness Testing

Performed a controlled database failure test.

### Database stopped

Command:

```bash
docker compose stop db
```

Results:

- `/health` returned HTTP 200.
- `/ready` returned HTTP 503.
- Readiness check correctly reported the database as unavailable.

### Database restarted

Command:

```bash
docker compose start db
```

After the database recovered:

- `/ready` returned HTTP 200.
- Database readiness check returned true.

This verified the difference between application liveness and dependency readiness.

## 5. Idempotent Data Loading

Stopped and restarted the Compose stack without deleting its database volume.

Verified migration and seed logs:

```text
Inserted: 0
Updated: 0
Unchanged: 20
```

This confirmed that restarting the stack did not create duplicate sample records.

## 6. Unit and Integration Test Separation

Organized the test suite into:

- `tests/unit/`
- `tests/integration/`

Created separate test configuration for each suite.

### Unit tests

Command:

```bash
uv run poe test
```

Result:

```text
11 passed
```

### Integration tests

Command:

```bash
uv run poe test-integration
```

Result:

```text
7 passed
```

Integration tests use a unique PostgreSQL database for each test run.

The fixture:
- Creates a temporary database.
- Applies Alembic migrations.
- Runs integration tests.
- Drops the temporary database after completion.

This prevents integration tests from interfering with development data or one another.

## 7. Test Coverage

Command:

```bash
uv run poe cov
```

Result:

```text
18 passed
Total coverage: 80%
```

Configured coverage reporting to show missing lines and branch coverage.

Added `.coverage` and `htmlcov/` to `.gitignore`.

## 8. Developer Shortcuts

Added Poe tasks in `pyproject.toml`:

- `uv run poe dev`
- `uv run poe lint`
- `uv run poe test`
- `uv run poe test-integration`
- `uv run poe cov`
- `uv run poe migrate`
- `uv run poe seed`

Created a Makefile with shortcuts for Docker Compose, testing, coverage, linting and database operations.

## 9. Key Technical Learnings

- Multi-stage Docker builds separate build dependencies from the runtime image.
- Docker layer caching makes repeated builds faster.
- Running containers as non-root users improves security.
- Docker Compose service names allow containers to communicate without using localhost.
- Health checks help coordinate service startup.
- Liveness checks indicate whether the application is running; readiness checks indicate whether it can serve requests.
- Isolated integration-test databases protect development data.
- Coverage reports identify untested application code.

## 10. Day 4 Git Commits

- `10c3804` — build: multi-stage Dockerfile with uv, non-root user
- `0d1c7be` — build: docker compose stack with postgres, redis, migrations and api
- `503b8df` — test: split unit and integration suites with fresh database


# Day 5 — CI/CD, Production Deployment and Monitoring
## D05

## 1. Production Deployment

- Hosting: Render
- Production URL: https://carecover-oi5g.onrender.com
- API documentation: https://carecover-oi5g.onrender.com/docs
- Health endpoint: https://carecover-oi5g.onrender.com/health
- Database: Neon PostgreSQL
- Container registry: GitHub Container Registry (GHCR)

Verified:
- Application deployed successfully.
- `/health` returned HTTP 200.
- `/ready` confirmed database connectivity.
- `/docs` was accessible.
- Production API returned HTTP 200 for `/v1/documents?limit=1`.

## 2. Continuous Integration

Created GitHub Actions CI workflow.

Checks:
- Ruff linting
- Ruff formatting
- Unit and integration tests
- Docker image build
- GHCR image publishing

CI workflow:
https://github.com/samyuktharavirengarajan-hub/prince28-hlt05-carecover/actions/workflows/ci.yml

PR #6:
https://github.com/samyuktharavirengarajan-hub/prince28-hlt05-carecover/pull/6

## 3. Continuous Deployment

Created GitHub Actions CD workflow.

Deployment sequence:
1. Wait for successful CI completion on main.
2. Apply Alembic migrations to Neon.
3. Deploy the exact SHA-tagged image to Render.
4. Run production smoke tests.

The workflow also supports manual rollback using a previous commit SHA.

CD workflow:
https://github.com/samyuktharavirengarajan-hub/prince28-hlt05-carecover/actions/workflows/cd.yml

PR #7:
https://github.com/samyuktharavirengarajan-hub/prince28-hlt05-carecover/pull/7

## 4. Production Smoke Testing

Created `scripts/smoke.py`.

It verifies:
- `/health` reports the expected application version.
- `/ready` confirms database readiness.
- `/v1/documents?limit=1` returns HTTP 200 and an items field.

Final production smoke test passed against:
`b3f6d56a1c638a4b982278bf4fa82502de8fe26d`

## 5. Rollback Drill

Selected the pre-CD CI merge commit:

`5b38e137cb97616430d50586679b6fdd8d3d6c9e`

Manual CD run #3:
https://github.com/samyuktharavirengarajan-hub/prince28-hlt05-carecover/actions/runs/44775107497

Result:
- Workflow completed successfully.
- Database migrations were skipped.
- Older SHA-tagged image was deployed.
- Production `/health` returned HTTP 200.
- Live version matched the rollback SHA.

## 6. Roll-forward Verification

Restored the latest main version:

`b3f6d56a1c638a4b982278bf4fa82502de8fe26d`

Manual CD run #4:
https://github.com/samyuktharavirengarajan-hub/prince28-hlt05-carecover/actions/runs/44775883420

Result:
- Workflow completed successfully.
- Latest image was deployed.
- Production `/health` returned HTTP 200.
- Live version matched the expected main SHA.

## 7. Database Safety During Rollback

The rollback workflow skips database migrations and does not run Alembic downgrade.

Therefore, the database schema remains at its existing migration revision while the application image is rolled back.

This avoids destructive schema downgrades. Safe rollback depends on backward-compatible database migrations and application versions that can work with the retained schema.

## 8. Monitoring

Created an UptimeRobot HTTP(S) monitor.

- Monitor URL: https://carecover-oi5g.onrender.com/health
- Check interval: 5 minutes
- Alert: Email notification
- Badge: Monitor-specific read-only API key

The API health route was updated to support both GET and HEAD requests because the free UptimeRobot monitor uses HEAD.

Unit tests verify HEAD support.

## 9. Secrets Management

GitHub repository Settings → Secrets and variables → Actions:

Secrets:
- DATABASE_URL
- RENDER_DEPLOY_HOOK

Repository variable:
- LIVE_URL

Sensitive values are not stored in the repository.

## 10. Performance Improvement

Render Free instances can sleep when inactive. The first request may take longer because the service needs to wake up.

One possible improvement is using an always-on hosting instance to reduce cold-start latency.

## 11. Final Validation

- Unit tests: 13 passed.
- Ruff check: Passed.
- Ruff format: 32 files formatted.
- Rollback: Verified.
- Roll-forward: Verified.
- Production health: HTTP 200.


# Day 7 — Document Parsing

## 1. Database Schema

- Added `headings` JSONB column to the pages table.
- Created `parse_failures` table.
- Generated and applied the Alembic migration.

## 2. Parser Implementation

Created:
- `src/carecover/ingest/parse.py`
- `src/carecover/ingest/store.py`
- `scripts/parse_corpus.py`
- `tests/unit/test_parse.py`
- `tests/integration/test_parse_store.py`

## 3. Validation

- Unit tests: 36 passed.
- Integration tests: 10 passed.
- Ruff lint: Passed.
- Python syntax check for `compare_parsers.py`: Passed.

## 4. Dataset Status

Verified against `data/manifest.jsonl`, `data/manual_manifest.jsonl`,
the files in `data/raw/`, and PostgreSQL.

- PDF manifest records: 22.
- Successfully downloaded PDF files: 7.
- Manually collected Excel files: 3.
- Total unique collected files: 10.
- Total collected file size: 22,771,211 bytes (approximately 21.72 MiB).
- Document records stored in PostgreSQL: 30.
- Parsed pages stored in PostgreSQL: 1,044.
- Remaining parsing failures: 0.

The corpus includes PM-JAY package data, HBP 2022/HIMCARE
packages, hospital instructions, claim settlement, claims adjudication,
fraud investigation, and a TNHSP scheme document.

Some source URLs remain blocked, unavailable, or unverified.
The figures above describe the files actually collected and validated;
they do not imply that the source corpus is complete.

## D07 · Parser comparison

<!-- parsers:start -->
| File | Parsers (A / B) | Pages / Rows | A found | B found | Time (A / B) | Better, why |
|---|---|---|---|---|---|---|
| pm-jay_claims_adjudication_manual_(february_2019 | PyMuPDF / pypdf | 32 | 61,525 chars, 315 headings, 15 tables | 62,883 chars, 0 headings, 0 tables | 8.01 s / 1.45 s | PyMuPDF extracts more structural information (315 headings, 15 tables); pypdf is faster and extracts slightly more characters. |
| pm-jay_fraud_investigation_and_medical_audit_man | PyMuPDF / pypdf | 68 | 85,935 chars, 383 headings, 40 tables | 70,486 chars, 0 headings, 0 tables | 5.35 s / 1.62 s | PyMuPDF extracts more characters and detects 383 headings and 40 tables; pypdf is faster but detects no structure. |
| pm-jay_pm-jay_claim_settlement_guidelines.pdf | PyMuPDF / pypdf | 4 | 6,611 chars, 7 headings, 0 tables | 6,571 chars, 0 headings, 0 tables | 0.05 s / 0.08 s | PyMuPDF is faster and detects 7 headings; text extraction is similar. |
| pm-jay_pm-jay_compendium_of_instructions_part_ii | PyMuPDF / pypdf | 96 | 101,378 chars, 81 headings, 7 tables | 99,211 chars, 0 headings, 0 tables | 3.54 s / 1.99 s | PyMuPDF detects 81 headings and 7 tables and extracts slightly more text; pypdf is faster. |
| pm-jay_pm-jay_hbp_2022_and_himcare_packages.pdf | PyMuPDF / pypdf | 727 | 1,612,927 chars, 24 headings, 1 tables | 1,603,617 chars, 0 headings, 0 tables | 3.74 s / 28.70 s | PyMuPDF is substantially faster and detects headings and a table; pypdf extracts slightly fewer characters without structural details. |
| pm-jay_pm-jay_standard_operating_protocol_for_ho | PyMuPDF / pypdf | 110 | 65,174 chars, 139 headings, 9 tables | 100,294 chars, 0 headings, 0 tables | 1.94 s / 1.97 s | PyMuPDF detects 139 headings and 9 tables; pypdf extracts more characters at a similar speed, but detects no structure. |
| pmjay_open_to_all.xlsx | openpyxl / python-calamine | 598 rows | 7,165 non-empty cells | 7,165 non-empty cells; identical=True | 0.05 s / 0.01 s | Both parsers produce identical normalized cell values; python-calamine is faster in this run. |
| pmjay_reserved_to_govt_with_pay.xlsx | openpyxl / python-calamine | 495 rows | 1,483 non-empty cells | 1,483 non-empty cells; identical=True | 0.02 s / 0.00 s | Both parsers produce identical normalized cell values; python-calamine is faster in this run. |
| pmjay_reserved_to_govt_without_pay.xlsx | openpyxl / python-calamine | 318 rows | 952 non-empty cells | 952 non-empty cells; identical=True | 0.01 s / 0.00 s | Both parsers produce identical normalized cell values; python-calamine is faster in this run. |
| tnhsp_cmchis_and_pm-jay_scheme_continuation_g.o. | PyMuPDF / pypdf | - | FAILED: no_text_layer | FAILED: no_text_layer | 0.00 s / 0.00 s | Both text parsers fail because the PDF is scanned; OCR was used separately to extract its pages. |
<!-- parsers:end -->
