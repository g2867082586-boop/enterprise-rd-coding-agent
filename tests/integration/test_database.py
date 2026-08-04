from app.database.repository import failed_orders_last_seven_days


def test_relative_time_seed_excludes_ten_day_order(seeded_database) -> None:
    result = failed_orders_last_seven_days()
    grouped = {row["error_code"]: row["failure_count"] for row in result["rows"]}
    assert grouped == {"ORDER002": 3, "ORDER003": 1}

