import pytest

from app.observability import _otel_headers


def test_otel_headers_are_parsed_without_logging_values() -> None:
    assert _otel_headers("Authorization=Bearer example,x-scope=demo") == {
        "Authorization": "Bearer example", "x-scope": "demo"
    }
    assert _otel_headers("") is None


def test_invalid_otel_headers_fail_closed() -> None:
    with pytest.raises(ValueError):
        _otel_headers("invalid")
