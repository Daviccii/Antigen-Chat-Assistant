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
    from . import attachment_models  # noqa: F401
    from . import security_models  # noqa: F401

    # Create pgvector extension BEFORE creating tables (required for VECTOR type)
    with engine.connect() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
            print("Successfully created/verified pgvector extension")
        except Exception as e:
            print(f"Warning: Could not create pgvector extension: {e}")
            print("This may be due to insufficient permissions. The VECTOR type may not work.")
            # Creating extensions may require superuser; ignore if not allowed in the environment.
            pass

    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        print("Database tables created successfully")
    except sqlalchemy_exc.ProgrammingError as exc:
        if "already exists" in str(exc).lower() or "duplicate" in str(exc).lower():
            print("Some tables already exist, continuing...")
        else:
            print(f"Programming error during table creation: {exc}")
            raise
    except Exception as e:
        print(f"Error during table creation: {e}")
        raise
