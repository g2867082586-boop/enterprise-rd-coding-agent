"""Verify web-table CRUD and denial of business-table access without printing credentials."""

import uuid

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.database.connection import get_app_engine


def verify() -> dict[str, object]:
    marker = f"verify_{uuid.uuid4().hex[:12]}"
    web_crud = False
    business_table_denied = False
    with get_app_engine().connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text(
                "INSERT INTO app_users (id, username, email, password_hash, display_name, role, "
                "is_active, created_at, updated_at) VALUES (:id, :username, :email, :password_hash, "
                ":display_name, 'user', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ), {"id": str(uuid.uuid4()), "username": marker, "email": f"{marker}@example.test",
                "password_hash": "$argon2id$verification-only", "display_name": "权限验证"})
            web_crud = connection.scalar(
                text("SELECT COUNT(*) FROM app_users WHERE username=:username"), {"username": marker}
            ) == 1
        finally:
            transaction.rollback()
        try:
            connection.execute(text("SELECT COUNT(*) FROM orders"))
        except DBAPIError:
            business_table_denied = True
    return {"web_table_crud": web_crud, "business_table_access_denied": business_table_denied}


if __name__ == "__main__":
    print(verify())
