import pytest

from backend.app.services import coordination


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_redis_timeout_must_be_finite(monkeypatch, value):
    monkeypatch.setenv("SIPM_REDIS_TIMEOUT_SECONDS", value)
    with pytest.raises(RuntimeError, match="SIPM_REDIS_TIMEOUT_SECONDS"):
        coordination._redis_timeout_seconds()


@pytest.mark.parametrize("value", ["0.25", "5", "12.5"])
def test_redis_timeout_accepts_positive_finite_values(monkeypatch, value):
    monkeypatch.setenv("SIPM_REDIS_TIMEOUT_SECONDS", value)
    assert coordination._redis_timeout_seconds() == float(value)
