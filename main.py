from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from dotenv import load_dotenv
from datetime import datetime, timezone
import importlib
import pathlib
import re
from routes import (
    shell, files, code, system, monitor, git, package, apps, refactor, batch,
    repo, workspace, patch, test_runner, quality, policy, coding_agent, tasks,
    github, diagnostics, env, coding_dispatch, evals,
)

load_dotenv()

_REPO_ROOT = pathlib.Path(__file__).resolve().parent

app = FastAPI()
app.router.redirect_slashes = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def normalize_duplicate_slashes(request: Request, call_next):
    path = request.scope.get("path", "")
    if "//" in path:
        request.scope["path"] = re.sub(r"/+", "/", path)
        request.scope["raw_path"] = request.scope["path"].encode("ascii", errors="ignore")
    return await call_next(request)


def _include_optional_route(module_name: str, prefix: str) -> None:
    try:
        module = importlib.import_module(f"routes.{module_name}")
        app.include_router(module.router, prefix=prefix)
    except Exception:
        # Some deployments/checkouts omit optional browser-dispatch/GPT routes.
        return


# General-purpose operator routes.
app.include_router(shell.router, prefix="/shell")
app.include_router(files.router, prefix="/files")
app.include_router(files.router, prefix="/manageFiles")
app.include_router(code.router, prefix="/code")
app.include_router(system.router, prefix="/system")
app.include_router(monitor.router, prefix="/monitor")
app.include_router(git.router, prefix="/git")
app.include_router(package.router, prefix="/package")
app.include_router(apps.router, prefix="/apps")
app.include_router(refactor.router, prefix="/refactor")
app.include_router(batch.router, prefix="/batch")
_include_optional_route("gpts", "/gpts")
_include_optional_route("dispatch", "/dispatch")

# Narrow coding-agent routes.
app.include_router(repo.router, prefix="/repo")
app.include_router(workspace.router, prefix="/workspace")
app.include_router(patch.router, prefix="/patch")
app.include_router(test_runner.router, prefix="/test")
app.include_router(quality.router, prefix="/quality")
app.include_router(policy.router, prefix="/policy")
app.include_router(coding_agent.router, prefix="/agent")
app.include_router(tasks.router, prefix="/tasks")
app.include_router(github.router, prefix="/github")
app.include_router(diagnostics.router, prefix="/diagnostics")
app.include_router(env.router, prefix="/env")
app.include_router(coding_dispatch.router, prefix="/coding")
app.include_router(evals.router, prefix="/evals")


@app.get("/debug/routes")
def list_routes():
    return [r.path for r in app.routes]


@app.get("/health", include_in_schema=False)
@app.get("/healthz", include_in_schema=False)
@app.get("/api/health", include_in_schema=False)
def health():
    return {
        "status": "ok",
        "service": "gpt-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
def unsupported_api_namespace(path: str):
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "code": "unsupported_namespace",
                "message": "This service is GPT-API, not the application /api backend.",
                "path": f"/api/{path}",
            },
            "status": 404,
        },
    )


@app.get("/openapi.yaml", response_class=PlainTextResponse, include_in_schema=False)
def serve_openapi_yaml():
    yaml_path = _REPO_ROOT / "openapi.yaml"
    return PlainTextResponse(yaml_path.read_text(encoding="utf-8"), media_type="text/yaml")


@app.get("/cos-openapi.yaml", response_class=PlainTextResponse, include_in_schema=False)
def serve_cos_openapi_yaml():
    yaml_path = _REPO_ROOT / "cos-openapi.yaml"
    return PlainTextResponse(yaml_path.read_text(encoding="utf-8"), media_type="text/yaml")


@app.get("/coding-openapi.yaml", response_class=PlainTextResponse, include_in_schema=False)
def serve_coding_openapi_yaml():
    yaml_path = _REPO_ROOT / "coding-openapi.yaml"
    return PlainTextResponse(yaml_path.read_text(encoding="utf-8"), media_type="text/yaml")


@app.get("/coding-gpt-core-openapi.yaml", response_class=PlainTextResponse, include_in_schema=False)
def serve_coding_core_openapi_yaml():
    yaml_path = _REPO_ROOT / "coding-gpt-core-openapi.yaml"
    return PlainTextResponse(yaml_path.read_text(encoding="utf-8"), media_type="text/yaml")
