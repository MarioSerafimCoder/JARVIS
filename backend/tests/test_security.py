import pytest

from app.core.security import safe_child_path, validate_upload


def test_upload_rejects_traversal_name():
    with pytest.raises(ValueError):
        validate_upload("../segredo.txt", 10)


def test_upload_rejects_unsupported_extension():
    with pytest.raises(ValueError):
        validate_upload("malware.exe", 10)


def test_safe_child_path_stays_inside(tmp_path):
    assert safe_child_path(tmp_path, "document.txt").parent == tmp_path.resolve()
    with pytest.raises(ValueError):
        safe_child_path(tmp_path, "../outside.txt")

