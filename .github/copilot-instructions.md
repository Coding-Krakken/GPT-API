# Copilot Instructions for GPT-API

## Project Overview
- **Purpose:** Exposes a universal FastAPI-based control API for GPT agents to perform system operations (file, shell, code, package, git, apps, refactor, monitor, batch, etc.).
- **Core Entry:** `main.py` (FastAPI app), `cli.py` (CLI wrapper), `openapi.yaml` (OpenAPI schema for endpoint discovery).
- **API Endpoints:** Defined in `routes/` (one file per major operation, e.g., `shell.py`, `files.py`, `code.py`, etc.).
- **Authentication:** All endpoints require an `x-api-key` header. See `.env` for config.

## Key Directories & Files
- `routes/` — API endpoints, one file per operation type. Each file defines a FastAPI router.
- `assistants/` — Utilities for managing OpenAI GPT Assistants (optional, DB-backed).
- `utils/auth.py` — API key authentication logic.
- `openapi.yaml` — OpenAPI spec for endpoint structure and agent guidance.
- `gpt-instructions.md` — Custom GPT instructions for using the API endpoints.
- `tests/` — Test suite for all endpoints and workflows.

## Developer Workflows
- **Start server:** `python cli.py` or `python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
- **Run tests:** `python -m pytest` or run individual scripts in `tests/` (e.g., `python test_full_api.py`).
- **API docs:** Swagger at `/docs`, ReDoc at `/redoc` when server is running.
- **Debug routes:** `GET /debug/routes` for a list of all endpoints.

## Project Conventions
- **Endpoint design:** Each operation (shell, files, code, etc.) is a POST endpoint accepting a JSON body with an `action` field and operation-specific parameters.
- **Authentication:** Enforced via `utils/auth.py` and checked in every route.
- **Error handling:** Standardized error responses; check for 403 (auth), 500 (internal), and validation errors.
- **Testing:** `test_full_api.py` provides comprehensive endpoint coverage; use after any major change.
- **Database:** Optional, only required for `/assistants` endpoints. Uses PostgreSQL via SQLAlchemy.
- **Environment:** All config via `.env` (API key, host, port, DB params, etc.).

## Integration & Patterns
- **External tools:** Supports pip, npm, apt, brew, winget, etc. for package ops; git for VCS; system shell for commands.
- **Batch ops:** `/batch` endpoint allows multi-step workflows in a single request.
- **Refactoring:** `/refactor` endpoint for search/replace across files, with dry-run support.
- **Monitoring:** `/system` and `/monitor` for system info and real-time stats.
- **Custom GPTs:** Use `gpt-instructions.md` and `openapi.yaml` to guide agent behavior and endpoint usage.

## Examples
- **File read:** `POST /files {"action": "read", "path": "file.txt"}`
- **Shell command:** `POST /shell {"command": "ls -la"}`
- **Code run:** `POST /code {"action": "run", "path": "script.py", "language": "python"}`
- **Batch:** `POST /batch {"operations": [{"action": "shell", "args": {"command": "echo hi"}}]}`

## Tips for AI Agents
- Always include the `x-api-key` header.
- Use the OpenAPI spec (`openapi.yaml` or `/openapi.json`) for endpoint discovery.
- Prefer `/batch` for multi-step workflows.
- For new endpoints, follow the pattern in `routes/` and update the OpenAPI spec.
- Reference `gpt-instructions.md` for agent-specific usage guidance.

---
For more, see `README.md` and the running API docs at `/docs`.
