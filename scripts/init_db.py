"""
Creates all tables from db/models.py.
Run with: python -m scripts.init_db
"""

from db.base import Base, engine
from db import models  # noqa: F401  (import registers the models on Base.metadata)


def main():
    Base.metadata.create_all(bind=engine)
    print(f"Tables created: {list(Base.metadata.tables.keys())}")


if __name__ == "__main__":
    main()