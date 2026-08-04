"""Create or promote an administrator without exposing a password in command history."""

import getpass
import sys
import uuid

from sqlalchemy import or_, select

from app.auth.password import hash_password
from app.auth.service import utcnow
from app.database.models import AppUser
from app.database.session import create_app_session


def main() -> None:
    username = input("管理员用户名: ").strip().lower()
    email = input("管理员邮箱: ").strip().lower()
    display_name = input("显示名称: ").strip() or username
    password = getpass.getpass("管理员密码（输入不会显示）: ")
    db = create_app_session()
    try:
        user = db.scalar(select(AppUser).where(or_(AppUser.username == username, AppUser.email == email)))
        if user:
            user.role = "admin"
            user.is_active = True
            user.updated_at = utcnow()
            action = "promoted"
        else:
            now = utcnow()
            user = AppUser(
                id=str(uuid.uuid4()), username=username, email=email, password_hash=hash_password(password),
                display_name=display_name, role="admin", is_active=True, created_at=now,
                updated_at=now, last_login_at=None,
            )
            db.add(user)
            action = "created"
        db.commit()
        print({"admin": username, "action": action})
    finally:
        db.close()


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        sys.exit("已取消")
