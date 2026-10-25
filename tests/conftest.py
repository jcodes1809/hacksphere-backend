import pytest
from app import quickml


@pytest.fixture(autouse=True)
def never_call_real_quickml(monkeypatch):
    """Safety net: no test may ever reach the real (quota-limited) endpoint."""
    monkeypatch.setenv("QUICKML_CALL_BUDGET", "0")
    def _boom(*a, **k):
        raise AssertionError("Real QuickML must not be called in tests")
    monkeypatch.setattr(quickml, "call_quickml", _boom)
    quickml.reset()
    yield
    quickml.reset()
