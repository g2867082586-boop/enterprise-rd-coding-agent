"""Idempotent production bootstrap that never reseeds an existing business schema."""

import pymysql

from app.config import get_settings
from scripts.init_database import init_database
from scripts.provision_web_database import provision


def business_schema_exists() -> bool:
    settings = get_settings()
    connection = pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_admin_user,
        password=settings.mysql_admin_password,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema=%s AND table_name IN ('users','orders')",
                (settings.mysql_database,),
            )
            return int(cursor.fetchone()[0]) == 2
    finally:
        connection.close()


def main() -> None:
    if not business_schema_exists():
        print({"business_schema": "missing", "initialization": init_database()})
    else:
        print({"business_schema": "existing", "initialization": "skipped safely"})
    print({"web_and_order_accounts": provision()})


if __name__ == "__main__":
    main()
