"""Check existing users."""
from sqlalchemy import create_engine, text
from app.config import settings

engine = create_engine(settings.DATABASE_URL)
conn = engine.connect()

result = conn.execute(text("SELECT id, username, display_name, email FROM users"))
users = result.fetchall()

print("Existing users:")
for user in users:
    print(f"ID: {user[0]}, Username: {user[1]}, Display Name: {user[2]}, Email: {user[3]}")

conn.close()
