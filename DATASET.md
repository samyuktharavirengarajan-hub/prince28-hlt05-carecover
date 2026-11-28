# CareCover Dataset Documentation

## 1. Purpose

This document records the healthcare data sources collected for CareCover, their access status, and known reuse limitations.

## 2. Collection Summary

Verified against `data/manifest.jsonl`, `data/manual_manifest.jsonl`, `data/raw/`, and PostgreSQL.

| Metric | Verified result |
|---|---:|
| PDF manifest records | 22 |
| Successfully downloaded PDFs | 7 |
| Manually collected Excel workbooks | 3 |
| Total unique collected files | 10 |
| Total collected file size | 22,771,211 bytes (~21.72 MiB) |
| PostgreSQL document records | 30 |
| Parsed pages stored in PostgreSQL | 1,044 |
| Remaining parsing failures | 0 |

## 3. Successfully Collected Documents

### PDF documents

1. PM-JAY Claim Settlement Guidelines
2. CMCHIS and PM-JAY Scheme Continuation G.O. 530
3. PM-JAY HBP 2022 and HIMCARE Packages
4. PM-JAY Compendium of Instructions Part II
5. PM-JAY Standard Operating Protocol for Hospitals
6. Claims Adjudication Manual (February 2019)
7. Fraud Investigation and Medical Audit Manual (December 2018)

The 727-page HBP 2022 and HIMCARE PDF was downloaded from HPSBYS. Its embedded PDF title is `HIMCARE Packages final 2022 -Latest.xls`. Its extracted package tables contain PM-JAY and HIMCARE package-related fields. It is recorded as an alternate package dataset, not as the exact official NHA HBP 2022 Package Master.

### Excel workbooks

The following three workbooks were manually collected from the CMCHIS PM-JAY source page:

1. `pmjay_open_to_all.xlsx`
2. `pmjay_reserved_to_govt_without_pay.xlsx`
3. `pmjay_reserved_to_govt_with_pay.xlsx`

Their reuse terms have not been independently verified.

## 4. Required Sources Not Collected

| Source | Manifest status | Observed limitation |
|---|---|---|
| PM-JAY HBP 2022 Package Master (`pmjay.gov.in`) | `robots_unknown` | robots.txt request timed out; permission could not be confirmed |
| PM-JAY HBP 2022 Package Master (`nha.gov.in`) | `blocked_robots` | robots.txt disallowed crawling |
| PM-JAY Senior Citizens FAQs (`nha.gov.in`) | `blocked_robots` | robots.txt disallowed crawling |
| PM-JAY CMCHIS FAQs (`cmchistn.com`) | `failed` | Download did not complete successfully |

These sources are not counted among the collected files. No attempt is made to bypass robots.txt restrictions.

Other manifest entries also remain blocked, unavailable, invalid, or unverified. Their statuses are retained in `data/manifest.jsonl`.

## 5. Access, Licensing, and Reuse

- Automated PDF downloads are attempted only when the collection process confirms access is permitted. Manually collected workbooks are tracked separately; their reuse terms remain unverified.
- `robots_unknown` is not treated as permission to crawl.
- `blocked_robots` sources are excluded from downloading.
- Public accessibility does not automatically establish permission to reproduce or redistribute a document.
- Reuse and redistribution terms have not been verified for every collected source.
- CareCover should cite the original source and document title/date when using source material.

## 6. Storage

- Downloaded source files are stored under `data/raw/`.
- PDF collection metadata is maintained in `data/manifest.jsonl`.
- Manually collected workbook metadata is maintained in `data/manual_manifest.jsonl`.
- Raw source files are excluded from Git version control.

## 7. Limitations and Next Steps

- The exact official NHA HBP 2022 Package Master has not been collected.
- The listed NHA Senior Citizens FAQ and CMCHIS FAQ have not been collected.
- The alternate HPSBYS package PDF must not be represented as an exact substitute for the official NHA master.
- Some source URLs remain blocked, unavailable, invalid, or unverified.
- The collected corpus is useful for ingestion and parsing work but is not a complete representation of all PM-JAY and CMCHIS documents.
- Any future collection attempt must respect robots.txt, source access policies, and applicable licence conditions.
