from sqlalchemy import create_engine, text, inspect
from app.config import settings

engine = create_engine(settings.DATABASE_URL)
conn = engine.connect()
inspector = inspect(conn)

print('Current database tables:', inspector.get_table_names())

if 'memories' in inspector.get_table_names():
    columns = [col['name'] for col in inspector.get_columns('memories')]
    print('Memory columns:', columns)
    
    # Check embedding column type
    for col in inspector.get_columns('memories'):
        if col['name'] == 'embedding':
            print(f'Embedding column type: {col["type"]}')

conn.close()
