
# Day 3 — PostgreSQL Migration Evidence

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
