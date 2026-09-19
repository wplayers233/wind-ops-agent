# Repository Guidelines

## Project Adapter

- `@@PROJECT:wind-ops-agent@@` — multimodal RAG workbench for wind-turbine operations; a local, reproducible demo.
- `@@TRUTH:memory-bank/@architecture.md@@` — internal truth source (architecture + owner map); `memory-bank/@design-document.md` holds the product definition. `README.md` is the external user-facing doc, not the internal truth source.
- `@@COMMAND:./build.ps1@@` — root quality gate; see "Build, Test, and Development Commands" below for per-app commands.
- `@@STACK:Python/FastAPI/LangGraph + React/TypeScript/Vite + pytest + Docker Compose@@`
- `@@OWNER:memory-bank/@architecture.md (Owner Map section)@@` — single owner for every shared concept; `app/main.py` and the frontend may only adapt protocol/UI, never own domain semantics.
- `@@BOUNDARY:offline-first demo@@` — external services (OCR, vision, embedding, reranker, Redis, Milvus) are optional adapters with explicit degradation; no production-ops, multi-tenant, or cloud scope.

## Project Structure & Module Organization

This repository is a wind-operations RAG demo organized as a small monorepo:

- `apps/backend/` contains the FastAPI service. Application code is in `app/`, with domain services under `app/services/` and sample/evaluation data under `app/data/`.
- `apps/backend/tests/` is split into `unit/services/`, `integration/api/`, and `integration/e2e/`.
- `apps/frontend/` contains the React + TypeScript + Vite UI (`src/`), its package manifest, and production Dockerfile.
- `build.ps1` is the root quality-gate entry point; `docker-compose.yml` describes local infrastructure and app services. Keep generated files (`__pycache__`, `.pytest_cache`, `dist`, `.venv`) out of commits.

## Build, Test, and Development Commands

Run from the repository root unless noted:

- `./build.ps1` (PowerShell) runs backend syntax/dependency checks and tests, then the frontend production build.
- `./build.ps1 -SmokeOnline` adds `/health` and `/metrics` checks against a running backend at `127.0.0.1:8000`.
- In `apps/backend/`, `python -m pytest` runs the complete test suite; `python scripts/build.py` runs the backend quality gate.
- In `apps/frontend/`, `npm install` installs dependencies, `npm run dev` starts Vite, and `npm run check` runs TypeScript checking plus a production build.
- `docker compose up --build` starts the complete local stack, including Redis and Milvus dependencies.

## Coding Style & Naming Conventions

Use four-space indentation and UTF-8 source files. Python follows standard `snake_case` for modules, functions, and variables; use `PascalCase` for classes and Pydantic models. TypeScript/React uses `camelCase` for values and handlers and `PascalCase` for components. Keep API schemas in `app/schemas.py` and model definitions in `app/models.py`; prefer small service functions over duplicating workflow logic. Preserve existing type annotations and run the relevant formatter/linter configured by your editor before submitting.

## Testing Guidelines

Tests use `pytest` and are discovered as `test_*.py`. Name test functions `test_<behavior>` and place fast isolated tests in `tests/unit/`; API contracts belong in `tests/integration/api/`, and end-to-end workflow coverage belongs in `tests/integration/e2e/`. Add regression coverage for behavior changes and run the full suite before opening a pull request.

## Commit & Pull Request Guidelines

The repository uses git; existing history follows short, imperative subjects (`feat: ...`, `fix: ...`). Keep each commit focused. Pull requests should explain the user-visible change, link the relevant issue or work item, list validation commands, and include screenshots or API examples when UI or contract behavior changes. Call out configuration, migration, or new environment-variable requirements explicitly.

## Security & Configuration Tips

Never commit `.env` files or API keys. Start from `apps/backend/.env.example` when available, and rely on the documented mock/rule fallback when external model, OCR, vector, or reranker services are unavailable. Review changes to safety gates, retrieval sources, and prompt/provider configuration with extra care.

## Important Instructions

- Before writing any code, read `memory-bank/@architecture.md` in full.
- Before writing any code, read `memory-bank/@design-document.md` in full.
- After each major feature or milestone, update `memory-bank/@architecture.md` to reflect the resulting architecture.
