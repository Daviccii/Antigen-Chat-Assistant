"""
One-off migration: convert memories.embedding from TEXT to a real pgvector
column (vector(768), matching nomic-embed-text's output size), now that
generate_and_store_embedding uses local Ollama embeddings instead of OpenAI.

This does NOT delete any memory rows. It only resets the embedding column
to NULL — any old embeddings were either never generated (most likely) or
were OpenAI's 1536-dim vectors, which aren't valid at the new 768-dim size
anyway, so there's nothing worth preserving in that column specifically.
Your memory content, type, key, tags, etc. are all left untouched.

Prerequisites (from backend/, with your venv active):
    pip install pgvector
    ollama pull nomic-embed-text

Run this migration as a module so relative imports resolve:
    python -m app.fix_embedding_column

After it finishes, regenerate embeddings for existing memories by calling
POST /memories/batch_generate_embeddings (there's already an endpoint for
this) or just let them fill in lazily as you keep chatting — newly created
memories get embedded automatically.
"""
from sqlalchemy import text
from .db import engine


def main():
    print("Ensuring the pgvector extension is enabled...")
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    print("Converting memories.embedding to vector(768)...")
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE memories ALTER COLUMN embedding TYPE vector(768) USING NULL"))
        conn.commit()

    print("Done. Existing memory rows are untouched; their embedding column was reset to NULL.")
    print("Next: call POST /memories/batch_generate_embeddings to (re)generate them locally,")
    print("or just keep chatting — new memories get embedded automatically going forward.")


if __name__ == "__main__":
    main()