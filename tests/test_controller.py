import pytest
from app.controller import decide, RENEWABLE, MAIN_GRID


@pytest.mark.parametrize("demand,hour,mode,overload", [
    (160.0, 10, MAIN_GRID, False),    # exactly 160 outside window
    (160.01, 10, RENEWABLE, False),
    (199.99, 10, RENEWABLE, False),
    (200.0, 10, RENEWABLE, True),     # exactly 200 is overload
    (100.0, 17, MAIN_GRID, False),
    (100.0, 18, RENEWABLE, False),
    (100.0, 22, RENEWABLE, False),    # 22:xx included
    (100.0, 23, MAIN_GRID, False),
    (160.0, 18, RENEWABLE, False),    # 160 inside window
    (250.0, 3, RENEWABLE, True),
])
def test_rules(demand, hour, mode, overload):
    r = decide(demand, hour)
    assert r["mode"] == mode
    assert r["overload"] == overload


def test_overload_always_renewable():
    for h in range(24):
        r = decide(200.0, h)
        assert r["overload"] and r["mode"] == RENEWABLE
