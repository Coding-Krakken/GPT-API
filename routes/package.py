from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import subprocess
import time
import os
import shutil
import shlex
from utils.auth import verify_key
from utils.operation_policy import block_if_confirmation_required, confirmation_present, error_payload, package_danger_reasons

router = APIRouter()


class PackageRequest(BaseModel):
    manager: str
    action: str
    package: str = ""
    packages: Optional[List[str]] = None
    version: Optional[str] = None
    dev: bool = False
    global_: bool = Field(default=False, alias="global")
    working_dir: Optional[str] = None
    requirements_file: Optional[str] = None
    lockfile: Optional[str] = None
    timeout_seconds: int = Field(default=600, ge=1, le=3600)
    dry_run: bool = False
    confirm: bool = False
    confirmation: Optional[str] = None

    class Config:
        populate_by_name = True


MANAGERS = {"pip","pipx","poetry","uv","npm","pnpm","yarn","apt","pacman","brew","cargo","go","winget"}
ACTIONS = {"install","remove","update","list","upgrade","audit","freeze","sync","lock","outdated","resolve"}


def _pkgs(req: PackageRequest):
    pkgs = req.packages or ([req.package] if req.package else [])
    if req.version and len(pkgs) == 1:
        if req.manager in ["npm", "pnpm", "yarn"]:
            pkgs = [f"{pkgs[0]}@{req.version}"]
        elif req.manager in ["pip", "uv", "poetry", "pipx"]:
            pkgs = [f"{pkgs[0]}=={req.version}"]
    return pkgs


def _cmd(req: PackageRequest):
    m, a, pkgs = req.manager, req.action, _pkgs(req)
    if m == "pip":
        mp = {"install":["pip","install"],"remove":["pip","uninstall","-y"],"update":["pip","install","--upgrade","pip"],"upgrade":["pip","install","--upgrade"],"list":["pip","list"],"freeze":["pip","freeze"],"audit":["pip-audit"],"outdated":["pip","list","--outdated"],"resolve":["pip","install","--dry-run"],"sync":["pip","install","-r",req.requirements_file or "requirements.txt"],"lock":["pip","freeze"]}
        return mp[a] + (pkgs if a in ["install","remove","upgrade","resolve"] else [])
    if m == "uv":
        mp = {"install":["uv","pip","install"],"remove":["uv","pip","uninstall"],"list":["uv","pip","list"],"freeze":["uv","pip","freeze"],"sync":["uv","pip","sync",req.requirements_file or "requirements.txt"],"lock":["uv","lock"],"audit":["uv","pip","check"],"outdated":["uv","pip","list","--outdated"],"update":["uv","self","update"],"upgrade":["uv","pip","install","--upgrade"],"resolve":["uv","pip","compile",req.requirements_file or "requirements.in"]}
        return mp[a] + (pkgs if a in ["install","remove","upgrade"] else [])
    if m == "poetry":
        mp = {"install":["poetry","add"],"remove":["poetry","remove"],"update":["poetry","update"],"upgrade":["poetry","update"],"list":["poetry","show"],"freeze":["poetry","export","-f","requirements.txt"],"sync":["poetry","install","--sync"],"lock":["poetry","lock"],"audit":["poetry","check"],"outdated":["poetry","show","--outdated"],"resolve":["poetry","lock","--no-update"]}
        cmd = mp[a] + (pkgs if a in ["install","remove"] else [])
        if req.dev and a == "install": cmd.insert(2, "--group=dev")
        return cmd
    if m in ["npm","pnpm","yarn"]:
        base = m
        install = "add" if m in ["pnpm","yarn"] else "install"
        remove = "remove" if m in ["pnpm","yarn"] else "uninstall"
        mp = {"install":[base,install],"remove":[base,remove],"update":[base,"update"],"upgrade":[base,"update"],"list":[base,"list","--depth=0"],"audit":[base,"audit"],"outdated":[base,"outdated"],"sync":[base,"install"],"lock":[base,"install","--package-lock-only"] if m=="npm" else [base,"install","--lockfile-only"],"freeze":[base,"list","--depth=0"],"resolve":[base,"install","--dry-run"] if m=="npm" else [base,"install","--lockfile-only"]}
        cmd = mp[a] + (pkgs if a in ["install","remove"] else [])
        if req.dev and a == "install": cmd.append("--save-dev")
        if req.global_ and a in ["install","remove"]: cmd.append("--global")
        return cmd
    if m == "apt":
        mp = {"install":["apt-get","install","-y"],"remove":["apt-get","remove","-y"],"update":["apt-get","update"],"upgrade":["apt-get","upgrade","-y"],"list":["apt","list","--installed"],"audit":["apt-get","check"],"outdated":["apt","list","--upgradable"],"freeze":["apt-mark","showmanual"],"sync":["apt-get","update"],"lock":["apt-mark","showmanual"],"resolve":["apt-cache","policy"]}
        return mp[a] + (pkgs if a in ["install","remove","resolve"] else [])
    if m == "pacman":
        mp = {"install":["pacman","-S","--noconfirm"],"remove":["pacman","-R","--noconfirm"],"update":["pacman","-Sy"],"upgrade":["pacman","-Syu","--noconfirm"],"list":["pacman","-Q"],"audit":["pacman","-Qk"],"outdated":["pacman","-Qu"],"freeze":["pacman","-Qqe"],"sync":["pacman","-Syu","--noconfirm"],"lock":["pacman","-Qqe"],"resolve":["pacman","-Si"]}
        return mp[a] + (pkgs if a in ["install","remove","resolve"] else [])
    if m == "brew":
        mp = {"install":["brew","install"],"remove":["brew","uninstall"],"update":["brew","update"],"upgrade":["brew","upgrade"],"list":["brew","list"],"audit":["brew","audit"],"outdated":["brew","outdated"],"freeze":["brew","bundle","dump","--file=-"],"sync":["brew","bundle"],"lock":["brew","bundle","dump"],"resolve":["brew","info"]}
        return mp[a] + (pkgs if a in ["install","remove","resolve"] else [])
    if m == "cargo":
        mp = {"install":["cargo","add"],"remove":["cargo","remove"],"update":["cargo","update"],"upgrade":["cargo","update"],"list":["cargo","metadata","--no-deps"],"audit":["cargo","audit"],"outdated":["cargo","outdated"],"freeze":["cargo","metadata","--locked"],"sync":["cargo","fetch"],"lock":["cargo","generate-lockfile"],"resolve":["cargo","metadata"]}
        return mp[a] + (pkgs if a in ["install","remove"] else [])
    if m == "go":
        mp = {"install":["go","get"],"remove":["go","mod","edit","-droprequire"],"update":["go","get","-u","./..."],"upgrade":["go","get","-u"],"list":["go","list","-m","all"],"audit":["govulncheck","./..."],"outdated":["go","list","-u","-m","all"],"freeze":["go","list","-m","all"],"sync":["go","mod","tidy"],"lock":["go","mod","tidy"],"resolve":["go","mod","graph"]}
        return mp[a] + (pkgs if a in ["install","remove","upgrade"] else [])
    if m == "winget":
        mp = {"install":["winget","install"],"remove":["winget","uninstall"],"update":["winget","upgrade","--all"],"upgrade":["winget","upgrade","--all"],"list":["winget","list"],"audit":["winget","list"],"freeze":["winget","list"],"sync":["winget","upgrade","--all"],"lock":["winget","list"],"outdated":["winget","upgrade"],"resolve":["winget","show"]}
        return mp[a] + (pkgs if a in ["install","remove","resolve"] else [])
    if m == "pipx":
        mp = {"install":["pipx","install"],"remove":["pipx","uninstall"],"update":["pipx","upgrade-all"],"upgrade":["pipx","upgrade"],"list":["pipx","list"],"audit":["pipx","list"],"freeze":["pipx","list"],"sync":["pipx","list"],"lock":["pipx","list"],"outdated":["pipx","list"],"resolve":["pipx","install","--dry-run"]}
        return mp[a] + (pkgs if a in ["install","remove","upgrade","resolve"] else [])
    raise ValueError("Unsupported manager/action")


@router.post("", dependencies=[Depends(verify_key)])
@router.post("/", dependencies=[Depends(verify_key)])
async def package_post(request: Request):
    start = time.time()
    try:
        if request.headers.get("content-type", "").startswith("application/json"):
            try:
                data = await request.json()
            except Exception:
                data = dict(request.query_params)
        else:
            data = dict(request.query_params)
        if not data.get("manager") or data.get("manager") not in MANAGERS:
            raise HTTPException(status_code=400, detail="Unsupported package manager")
        if not data.get("action") or data.get("action") not in ACTIONS:
            raise HTTPException(status_code=400, detail="Unsupported action")
        req = PackageRequest(**data)
        reasons = package_danger_reasons(req.manager, req.action, global_install=req.global_)
        decision = block_if_confirmation_required(area="package", operation=req.action, reasons=reasons, confirmed=confirmation_present(req.confirmation, explicit_confirm=req.confirm))
        if not decision.allowed:
            return error_payload(decision)
        argv = _cmd(req)
        exe = shutil.which(argv[0])
        if not exe:
            return {"stdout": "", "stderr": f"Executable not found: {argv[0]}", "exit_code": 127, "status": 400, "latency_ms": round((time.time()-start)*1000,2), "timestamp": int(time.time()*1000)}
        cwd = os.path.abspath(os.path.expanduser(req.working_dir)) if req.working_dir else None
        if cwd and not os.path.isdir(cwd):
            return {"error": {"code": "invalid_working_dir", "message": f"Working directory does not exist: {cwd}"}, "status": 400}
        if req.dry_run:
            return {"stdout": shlex.join(argv), "stderr": "", "exit_code": 0, "dry_run": True, "status": 200, "latency_ms": round((time.time()-start)*1000,2), "timestamp": int(time.time()*1000)}
        r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=req.timeout_seconds)
        stdout = r.stdout[:8000] + ("\n...output truncated" if len(r.stdout) > 8000 else "")
        return {"stdout": stdout, "stderr": r.stderr, "exit_code": r.returncode, "lockfile_changed": False, "changed_files": [], "status": 200 if r.returncode == 0 else 400, "latency_ms": round((time.time()-start)*1000,2), "timestamp": int(time.time()*1000)}
    except HTTPException:
        raise
    except Exception as e:
        return {"error": {"code": "internal_error", "message": str(e)}, "status": 500, "latency_ms": round((time.time()-start)*1000,2), "timestamp": int(time.time()*1000)}
