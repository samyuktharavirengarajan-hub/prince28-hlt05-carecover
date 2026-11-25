"""Compare two parsers on collected PDF, HTML and Excel files."""

import json
import re
import sys
import time
from pathlib import Path

from openpyxl import load_workbook
from python_calamine import CalamineWorkbook

from carecover.ingest.parse import (
    ParseError,
    finish,
    headings_in,
    parse_file,
    split_pages,
)

MANIFESTS = [
    Path("data/manifest.jsonl"),
    Path("data/manual_manifest.jsonl"),
]
NOTES = Path("NOTES.md")
START, END = "<!-- parsers:start -->", "<!-- parsers:end -->"


def strip_tags(path):
    html = path.read_text(encoding="utf-8", errors="replace")
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    return finish("strip-tags", "html", "", split_pages(re.sub(r"(?s)<[^>]+>", " ", html)))


def measure(parser, path):
    started = time.perf_counter()
    try:
        doc = parser(path)
    except ParseError as error:
        return {
            "ok": False,
            "note": error.reason,
            "seconds": time.perf_counter() - started,
        }

    content = "\n".join(page.text for page in doc.pages)
    return {
        "ok": True,
        "pages": len(doc.pages),
        "chars": len(content),
        "headings": len(headings_in(content)[0]),
        "tables": sum(page.tables for page in doc.pages),
        "seconds": time.perf_counter() - started,
    }


def normalize(value):
    if value is None:
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return str(value).strip()


def read_openpyxl(path):
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        return [
            [normalize(value) for value in row]
            for sheet in workbook.worksheets
            for row in sheet.iter_rows(values_only=True)
        ]
    finally:
        workbook.close()


def read_calamine(path):
    workbook = CalamineWorkbook.from_path(path)
    return [
        [normalize(value) for value in row]
        for index in range(len(workbook.sheet_names))
        for row in workbook.get_sheet_by_index(index).to_python()
    ]


def cell_count(rows):
    return sum(1 for row in rows for value in row if value != "")


def load_files():
    files = {}
    for manifest in MANIFESTS:
        if not manifest.exists():
            continue

        records = [
            json.loads(line)
            for line in manifest.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        for record in records:
            path = record.get("path") or record.get("file_path")
            if record.get("status") == "downloaded" and path and Path(path).is_file():
                files[path] = Path(path)

    return sorted(files.values(), key=lambda path: path.name)


def cells(result):
    if not result["ok"]:
        return f"FAILED: {result['note']}"
    return f"{result['chars']:,} chars, {result['headings']} headings, {result['tables']} tables"


def main():
    sys.stdout.reconfigure(errors="replace")
    files = [Path(arg) for arg in sys.argv[1:]] or load_files()
    rows = []

    for path in files:
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            a = measure(parse_file, path)
            b = measure(lambda p: parse_file(p, pdf_parser="pypdf"), path)
            names = "PyMuPDF / pypdf"
            pages = a.get("pages", "-")
            found_a, found_b = cells(a), cells(b)
            speed = f"{a['seconds']:.2f} s / {b['seconds']:.2f} s"

        elif suffix in {".html", ".htm"}:
            a = measure(parse_file, path)
            b = measure(strip_tags, path)
            names = "trafilatura / strip tags"
            pages = a.get("pages", "-")
            found_a, found_b = cells(a), cells(b)
            speed = f"{a['seconds']:.2f} s / {b['seconds']:.2f} s"

        elif suffix in {".xlsx", ".xlsm"}:
            started = time.perf_counter()
            a = read_openpyxl(path)
            time_a = time.perf_counter() - started

            started = time.perf_counter()
            b = read_calamine(path)
            time_b = time.perf_counter() - started

            identical = a == b
            names = "openpyxl / python-calamine"
            pages = f"{len(a)} rows"
            found_a = f"{cell_count(a):,} non-empty cells"
            found_b = f"{cell_count(b):,} non-empty cells; identical={identical}"
            speed = f"{time_a:.2f} s / {time_b:.2f} s"

        else:
            continue

        row = f"| {path.name[:48]} | {names} | {pages} | {found_a} | {found_b} | {speed} | |"
        rows.append(row)
        print(row)

    table = "\n".join(
        [
            START,
            (
                "| File | Parsers (A / B) | Pages / Rows | A found | "
                "B found | Time (A / B) | Better, why |"
            ),
            "|---|---|---|---|---|---|---|",
            *rows,
            END,
        ]
    )

    text = NOTES.read_text(encoding="utf-8")
    if text.count(START) != 1 or text.count(END) != 1:
        raise ValueError("NOTES.md must contain exactly one parser marker pair.")

    start = text.index(START)
    end = text.index(END)
    if start >= end:
        raise ValueError("Parser markers are in the wrong order.")

    text = text[:start] + table + text[end + len(END) :]
    NOTES.write_text(text, encoding="utf-8")

    print(f"Compared {len(rows)} files. Updated NOTES.md successfully.")


if __name__ == "__main__":
    main()
