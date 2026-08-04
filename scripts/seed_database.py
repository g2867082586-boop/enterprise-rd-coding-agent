"""Idempotently rebuild the documented relative-time demo rows."""

from init_database import init_database


if __name__ == "__main__":
    print(init_database())
