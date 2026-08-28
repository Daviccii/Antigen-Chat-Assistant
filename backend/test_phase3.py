"""Test Phase 3 Memory Architecture."""
from sqlalchemy import create_engine, text, inspect
from app.config import settings
from app.memory_service import MemoryService, MemoryCategory, MemoryImportance, MemorySource, MemoryStatus
from app.context_engine import ContextEngine
from app.models import Memory, Project, User
from sqlalchemy.orm import sessionmaker

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

print("Testing Phase 3 Memory Architecture...")

# Check if migration has been applied
inspector = inspect(engine)
print(f"Current database tables: {inspector.get_table_names()}")

# Check Memory table columns
if 'memories' in inspector.get_table_names():
    memory_columns = [col['name'] for col in inspector.get_columns('memories')]
    print(f"Memory table columns: {memory_columns}")
    
    # Check for Phase 3 specific columns
    phase3_columns = ['category', 'importance', 'confidence', 'status', 'project_id', 'last_accessed_at', 'last_confirmed_at', 'extra_metadata']
    missing_columns = [col for col in phase3_columns if col not in memory_columns]
    if missing_columns:
        print(f"WARNING: Missing Phase 3 columns: {missing_columns}")
    else:
        print("All Phase 3 columns present in Memory table")

# Check Projects table
if 'projects' in inspector.get_table_names():
    print("Projects table exists")
else:
    print("WARNING: Projects table missing")

# Test MemoryService classes
print(f"\nMemoryCategory constants: {MemoryCategory.EXPLICIT}, {MemoryCategory.USER_PROFILE}, {MemoryCategory.PROJECT}")
print(f"MemoryImportance constants: {MemoryImportance.LOW}, {MemoryImportance.NORMAL}, {MemoryImportance.HIGH}, {MemoryImportance.CRITICAL}")
print(f"MemorySource constants: {MemorySource.USER_EXPLICIT}, {MemorySource.USER_CORRECTION}, {MemorySource.CONVERSATION}")
print(f"MemoryStatus constants: {MemoryStatus.ACTIVE}, {MemoryStatus.ARCHIVED}, {MemoryStatus.SUPERSEDED}")

# Test memory command detection
test_messages = [
    "Remember that my backend uses PostgreSQL",
    "Don't forget that I prefer step-by-step explanations",
    "What do you remember about Antigen?",
    "Forget that I use MySQL",
    "No, I actually use PostgreSQL 15"
]

print("\nTesting memory command detection:")
for msg in test_messages:
    result = MemoryService.detect_memory_command(msg)
    print(f"Message: '{msg}' -> {result}")

# Test correction detection
print("\nTesting correction detection:")
correction_test = "No, I actually use PostgreSQL 15"
correction_result = MemoryService.detect_correction(correction_test, "You use MySQL")
print(f"Message: '{correction_test}' -> {correction_result}")

# Test preference detection
print("\nTesting preference detection:")
preference_test = "I prefer concise responses"
preference_result = MemoryService.detect_preference(preference_test)
print(f"Message: '{preference_test}' -> {preference_result}")

# Check for existing users
user_count = db.query(User).count()
print(f"\nCurrent users in database: {user_count}")

if user_count > 0:
    # Get first user for testing
    test_user = db.query(User).first()
    print(f"Test user: {test_user.username} (ID: {test_user.id})")
    
    # Test creating a Phase 3 memory
    try:
        test_memory = MemoryService.create_memory(
            db=db,
            user_id=test_user.id,
            content="Test memory for Phase 3 verification",
            memory_type="fact",
            category=MemoryCategory.EXPLICIT,
            source=MemorySource.USER_EXPLICIT,
            importance=MemoryImportance.HIGH,
            confidence=0.9
        )
        print(f"Created test memory: ID {test_memory.id}, category: {test_memory.category}, importance: {test_memory.importance}")
        
        # Test retrieving memories
        memories = MemoryService.get_user_memories(db, test_user.id, limit=5)
        print(f"Retrieved {len(memories)} memories for user")
        
        # Clean up test memory
        MemoryService.delete_memory(db, test_memory.id, test_user.id)
        print("Cleaned up test memory")
        
    except Exception as e:
        print(f"Error testing memory operations: {e}")

db.close()
print("\nPhase 3 Memory Architecture verification completed!")
