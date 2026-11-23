# CareCover Dataset Documentation

## 1. Purpose

This document records the healthcare data sources identified for the CareCover project, their access status, and reuse considerations.

## 2. Identified Data Sources

| Source | Dataset / Document | Access Status |
|---|---|---|
| National Health Authority (NHA) | PM-JAY HBP 2022 Package Master | robots_unknown |
| National Health Authority (NHA) | Senior Citizens FAQs | blocked_robots |

## 3. Access and Download Status

- The PM-JAY HBP 2022 Package Master source returned a robots.txt timeout.
- The Senior Citizens FAQs source explicitly disallowed crawling through robots.txt.
- No documents were downloaded from these sources.
- Sources without confirmed robots permission were excluded from the download queue.

## 4. Licence and Reuse Considerations

The reuse and redistribution terms for these documents have not been verified.

CareCover does not assume that publicly accessible information is automatically free to reuse.

Before using or redistributing either document, the applicable licence and permissions must be verified.

## 5. Data Storage

Intended storage location for downloaded documents:

`data/raw/`

Raw downloaded files are excluded from Git version control.

## 6. Limitations

The current dataset does not contain downloaded source documents because permission to crawl could not be confirmed.

Future data ingestion must respect website access policies, robots.txt rules, and applicable licence conditions.
