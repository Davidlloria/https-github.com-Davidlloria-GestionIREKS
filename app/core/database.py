from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import DATA_DIR, DB_URL

DATA_DIR.mkdir(parents=True, exist_ok=True)
engine = create_engine(DB_URL, echo=False, connect_args={"check_same_thread": False})


def _migrate_ingredient_columns() -> None:
    with engine.begin() as conn:
        for table in ("ingredientes_ireks", "ingredientes_std"):
            columns = [row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()]
            if "descripcion" in columns and "nombre" not in columns:
                conn.exec_driver_sql(f"ALTER TABLE {table} RENAME COLUMN descripcion TO nombre")


def init_db() -> None:
    # Ensure all SQLModel tables are imported before metadata creation.
    import app.models.entities  # noqa: F401

    _migrate_ingredient_columns()
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
