import pytest

from carecover.workers.ingest import manifest_path


@pytest.mark.parametrize(
    "raw_path",
    [
        r"data\raw\manual.pdf",
        "data/raw/manual.pdf",
    ],
)
def test_manifest_path_normalizes_separators(raw_path):
    assert manifest_path(raw_path).as_posix() == "data/raw/manual.pdf"
