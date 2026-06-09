from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv
import pathlib
from routes import shell, files, code, system, monitor, git, package, apps, refactor, batch, gpts, dispatch

load_dotenv()

_REPO_ROOT = pathlib.Path(__file__).resolve().parent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(shell.router, prefix="/shell")
app.include_router(files.router, prefix="/files")
app.include_router(files.router, prefix="/manageFiles")  # Alias for tool compatibility
app.include_router(code.router, prefix="/code")
app.include_router(system.router, prefix="/system")
app.include_router(monitor.router, prefix="/monitor")
app.include_router(git.router, prefix="/git")
app.include_router(package.router, prefix="/package")
app.include_router(apps.router, prefix="/apps")
app.include_router(refactor.router, prefix="/refactor")
app.include_router(batch.router, prefix="/batch")
app.include_router(gpts.router, prefix="/gpts")
app.include_router(dispatch.router, prefix="/dispatch")

@app.get("/debug/routes")
def list_routes():
    return [r.path for r in app.routes]


@app.get("/openapi.yaml", response_class=PlainTextResponse, include_in_schema=False)
def serve_openapi_yaml():
    """Serve the raw openapi.yaml so GPT editors can import it via URL."""
    yaml_path = _REPO_ROOT / "openapi.yaml"
    return PlainTextResponse(yaml_path.read_text(encoding="utf-8"), media_type="text/yaml")

@app.get("/cos-openapi.yaml", response_class=PlainTextResponse, include_in_schema=False)
def serve_cos_openapi_yaml():
    """Serve the Chief of Staff restricted OpenAPI schema (dispatch-only)."""
    yaml_path = _REPO_ROOT / "cos-openapi.yaml"
    return PlainTextResponse(yaml_path.read_text(encoding="utf-8"), media_type="text/yaml")