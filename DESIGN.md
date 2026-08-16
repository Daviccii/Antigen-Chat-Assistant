# Antigen — Design and Architecture

Last updated: 2026-08-04

This document captures the high-level vision, goals, and initial architecture for the Antigen personal AI assistant. It is intentionally concise and meant to guide near-term implementation decisions and longer-term evolution.

## Vision

To build an intelligent, secure, and continuously evolving personal AI assistant that understands its user, communicates naturally, automates tasks, learns new capabilities with user approval, and serves as a central interface for managing digital work and everyday activities.

## Mission

Provide a local-first, privacy-respecting assistant that: understands natural language (voice and text), remembers important context over time, automates repetitive tasks safely, and grows via modular, reviewable skills.

## Primary Goals

- Natural dialog (voice + text)
- Long-term memory and context
- Safe task automation and system control
- Modular skills/plugins and incremental learning
- Local-first hosting with optional cloud sync

## Architectural Principles

- Modularity: separate concerns (API, memory, skills, automation, UI).
- Minimal privileges by default; explicit confirmation for risky actions.
- Local-first: default deployment is local on user machine, with optional opt-in sync.
- Extensible: add skills/plugins without core changes.
- Testable: components have clear interfaces and unit tests.

## Initial Tech Stack (already scaffolded)

- Backend: Python + FastAPI (`backend/app/`)
- Frontend: React + Vite (`frontend/`)
- Database: PostgreSQL (local via `docker-compose.yml`)
- LLM provider (configurable): OpenAI (via backend `/chat` integration)
- Persistence: SQLAlchemy ORM with simple Conversation/Message models

## High-level Components

- API (FastAPI)
  - Chat endpoint that proxies LLM requests and persists messages.
  - Conversation management (list, get, delete) with pagination and filtering.
  - Memory, skills, auth, and automation endpoints (planned).

- Persistence
  - Conversations and messages (relational storage in Postgres).
  - Long-term memory store (specialized tables for memories, key-value, embeddings later).

- Skills / Plugins
  - Self-contained Python modules (or external binaries) exposing a capabilities manifest and safe execution wrapper.
  - A skills registry and approval workflow.

- Automation Executor
  - Sandbox for running actions on the local machine.
  - Require confirmation for risky operations; support dry-run and undo where possible.

- UI
  - Conversation UI with controls for listing, deleting, and viewing conversations.
  - Future: voice UI, settings, memory management.

## Data Model (initial)

- Conversation
  - id, created_at, metadata

- Message
  - id, conversation_id (FK), role, content, created_at

- Memory (planned)
  - id, type, key, content, source, created_at, tags

- Skill (planned)
  - id, name, version, manifest, enabled, created_at

Indexes and query patterns
- Index conversations by created_at for ordering and paging.
- Index messages by conversation_id and created_at for efficient lookups.
- For text search, plan to add PostgreSQL tsvector or trigram indexes when needed.

## APIs (near-term)

- POST `/chat` — Send messages to the LLM, persist messages, return assistant response and `conversation_id`.
- GET `/conversations` — Paginated list with `page`, `page_size`, `search`, `date_from`, `date_to` → returns `items` + `meta`.
- GET `/conversations/{id}` — Conversation detail and ordered messages.
- DELETE `/conversations/{id}` — Permanently delete a conversation and messages.

Planned APIs:
- Memory CRUD: store/retrieve personal facts and documents.
- Skills registry: list/enable/disable/upload skills.
- Automation: request/execute approved actions with logs.
- Auth: local user auth and permissions (initially single-user).

## Security & Privacy

- Local-first defaults: API keys and data remain on the user's machine.
- Environment-driven secrets via `.env`; do not commit keys.
- Confirmations required for sensitive actions (file deletes, program execution, network operations).
- Audit logs for important actions and an emergency stop flag.
- Plan for role-based access control and multi-user support later.

## Extensibility

- Plugin/skill interface: manifest (name, version, capabilities), input/output schema, permissions required.
- Skills run in a sandbox or separate process; user explicitly approves enabling a skill.
- Versioning and capability review workflow before permanent enablement.

## Dev & Deployment (Local)

- Local dev: use `docker compose up -d` for Postgres (see `docker-compose.yml`).
- Backend: install `backend/requirements.txt` and run with `uvicorn app.main:app --reload`.
- Frontend: `npm install` in `frontend/` and `npm run dev`.
- Environment: copy `backend/.env.example` → `.env` and set `OPENAI_API_KEY` for LLM access.

## Observability & Testing

- Unit tests for services and endpoints; integration tests for DB-backed flows.
- Basic metrics and logs captured to files; consider Prometheus + Grafana if moving to remote hosting.

## Roadmap (near-term priorities)

1. `DESIGN.md` (this document).
2. Authentication & local user management (protect sensitive endpoints).
3. Long-term memory schema and APIs.
4. Skills/plugin system with approval workflow.
5. Voice (STT/TTS) integration and a richer UI.
6. Safe automation executor and audit logs.
7. Tests, CI, and developer docs.

## Notes and next decisions

- Consider adding full-text search (Postgres tsvector) for `search` filters when message volume grows.
- For embeddings and semantic search, add an embeddings table and vector index (pgvector) later.
- Decide on a backup/restore strategy for local databases (export/import tools).

---

This file is a starting point and should evolve as features are implemented and priorities shift.
