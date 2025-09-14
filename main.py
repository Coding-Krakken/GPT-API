from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routes import shell, files, code, system, monitor, git, package, apps, refactor, batch, screen, input, safety, session, flow, clipboard

load_dotenv()

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

# GUI Automation Routes
app.include_router(screen.router, prefix="/screen")
app.include_router(input.router, prefix="/input")
app.include_router(safety.router, prefix="/safety")
app.include_router(session.router, prefix="/session")
app.include_router(flow.router, prefix="/flow")
app.include_router(clipboard.router, prefix="/clipboard")

@app.get("/debug/routes")
def list_routes():
    return [r.path for r in app.routes]
