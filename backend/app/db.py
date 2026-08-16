from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy import text
from .config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def init_db():
    # Import models to ensure they're registered on the Base metadata
    from . import models  # noqa: F401

    try:
        Base.metadata.create_all(bind=engine)
    except sqlalchemy_exc.ProgrammingError as exc:
        if "already exists" in str(exc).lower() or "duplicate" in str(exc).lower():
            pass
        else:
            raise
    except Exception:
        # Allow repeated restarts to proceed even if some objects already exist.
        pass

    with engine.connect() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        except Exception:
            # Creating extensions may require superuser; ignore if not allowed in the environment.
            pass
