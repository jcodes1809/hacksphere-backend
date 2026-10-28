import pytest
from app.catalyst_store import _to_body


def test_bytes_stay_bytes():
    assert _to_body(b"a,b\n1,2\n") == b"a,b\n1,2\n"


def test_empty_body_rejected():
    with pytest.raises(ValueError):
        _to_body(b"")
