from sqlmodel import SQLModel, Session, create_engine

from .config import settings

# check_same_thread=False is needed for SQLite when accessed across FastAPI's
# threadpool; harmless once we move to Postgres.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
