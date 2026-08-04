from collections.abc import Iterator

from sqlalchemy.orm import Session, sessionmaker

from app.database.connection import get_app_engine


def create_app_session() -> Session:
    return sessionmaker(bind=get_app_engine(), expire_on_commit=False)()


def get_db() -> Iterator[Session]:
    session = create_app_session()
    try:
        yield session
    finally:
        session.close()

