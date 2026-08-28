"""Test list_memories directly to debug the issue."""
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, func
from app.config import settings
from app.models import Memory
from app.services import list_memories as svc_list_memories

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

try:
    print("Testing list_memories service...")
    items, meta = svc_list_memories(db=db, page=1, page_size=20, user_id=1)
    print(f"Success! Items: {len(items)}, Meta: {meta}")
    for item in items:
        print(f"  - {item['id']}: {item['content'][:50]}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
