
# CareCover

Tells a family whether a treatment is covered under Ayushman Bharat PM-JAY and Tamil Nadu's CMCHIS, the package rate, and which empanelled hospitals offer it.

**Status:** Day 1 foundation (FastAPI skeleton, quality gates). Live URL from Day 5.

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

## Run it locally

```bash
uv sync
cp .env.example .env   # Windows: copy .env.example .env
uv run uvicorn carecover.api.main:create_app --factory --reload
```

Then open http://localhost:8000/docs

## Checks

```bash
uv run pytest
uv run ruff check .
```
