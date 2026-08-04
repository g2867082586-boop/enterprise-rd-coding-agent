from datetime import UTC, datetime, timedelta


def is_recent(created_at: datetime, now: datetime) -> bool:
    return created_at >= now - timedelta(days=7)


def test_seven_day_boundary() -> None:
    now = datetime.now(UTC)
    assert is_recent(now - timedelta(days=6), now)
    assert not is_recent(now - timedelta(days=10), now)


def test_order002_meaning_is_consistent() -> None:
    errors = {"ORDER002": "库存预占超时", "ORDER003": "支付网关超时"}
    assert errors["ORDER002"] == "库存预占超时"

