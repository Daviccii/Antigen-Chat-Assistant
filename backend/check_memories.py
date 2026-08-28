from sqlalchemy import create_engine, text
from app.config import settings

engine = create_engine(settings.DATABASE_URL)
conn = engine.connect()

# Check existing memories
result = conn.execute(text("SELECT COUNT(*) FROM memories"))
count = result.fetchone()[0]
print(f'Total memories: {count}')

# Check memories with embeddings
result = conn.execute(text("SELECT COUNT(*) FROM memories WHERE embedding IS NOT NULL"))
with_embedding = result.fetchone()[0]
print(f'Memories with embeddings: {with_embedding}')

# Check embedding format
result = conn.execute(text("SELECT id, content, embedding FROM memories LIMIT 3"))
for row in result:
    print(f'Memory {row[0]}: {row[1][:50]}... embedding: {row[2][:50] if row[2] else "NULL"}...')

conn.close()
