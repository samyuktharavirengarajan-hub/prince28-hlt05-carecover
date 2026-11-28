import hashlib
import json

from scripts import parse_corpus


def test_load_records_keeps_all_manual_files(tmp_path, monkeypatch):
    """All manual workbooks sharing one source URL must be retained."""
    paths = [
        tmp_path / "open.xlsx",
        tmp_path / "without_pay.xlsx",
        tmp_path / "with_pay.xlsx",
    ]

    for path in paths:
        path.write_bytes(b"sample workbook: " + path.name.encode())

    manifest = tmp_path / "manual_manifest.jsonl"
    records = [
        {
            "url": "https://example.com/packages",
            "source": "CMCHIS",
            "title": path.stem,
            "licence": "Reuse terms not verified",
            "status": "downloaded",
            "path": str(path),
        }
        for path in paths
    ]
    manifest.write_text(
        "\n".join(json.dumps(record) for record in records),
        encoding="utf-8",
    )

    monkeypatch.setattr(parse_corpus, "MANIFEST", tmp_path / "missing.jsonl")
    monkeypatch.setattr(parse_corpus, "MANUAL_MANIFEST", manifest)

    loaded = parse_corpus.load_records()

    assert len(loaded) == 3
    assert {record["path"] for record in loaded} == {str(path) for path in paths}
    for record, path in zip(loaded, paths, strict=True):
        assert record["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_load_records_supports_pdf_file_path(tmp_path, monkeypatch):
    """Existing fetcher records using file_path must remain compatible."""
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"sample PDF content")

    manifest = tmp_path / "manifest.jsonl"
    record = {
        "url": "https://example.com/sample.pdf",
        "source": "Example",
        "title": "Sample PDF",
        "licence": "Test",
        "status": "downloaded",
        "file_path": str(pdf_path),
    }
    manifest.write_text(json.dumps(record), encoding="utf-8")

    monkeypatch.setattr(parse_corpus, "MANIFEST", manifest)
    monkeypatch.setattr(
        parse_corpus,
        "MANUAL_MANIFEST",
        tmp_path / "missing_manual.jsonl",
    )

    loaded = parse_corpus.load_records()

    assert len(loaded) == 1
    assert loaded[0]["path"] == str(pdf_path)
    assert loaded[0]["sha256"] == hashlib.sha256(pdf_path.read_bytes()).hexdigest()
