from fastapi import APIRouter, Depends, Request, HTTPException
import os
import time
import re
import difflib
import shutil
from utils.auth import verify_key

router = APIRouter()


def _discover(scope, files):
    if files is not None:
        return [os.path.abspath(os.path.expanduser(f)) for f in files]
    root = os.path.abspath(os.path.expanduser((scope or {}).get("root") or os.getcwd()))
    include = (scope or {}).get("include") or ["**/*"]
    exclude = (scope or {}).get("exclude") or [".git/**", "__pycache__/**", "node_modules/**"]
    import glob
    out = []
    for pat in include:
        out.extend(glob.glob(os.path.join(root, pat), recursive=True))
    def excluded(path):
        rel = os.path.relpath(path, root)
        return any(glob.fnmatch.fnmatch(rel, pat) for pat in exclude)
    return [p for p in dict.fromkeys(out) if os.path.isfile(p) and not excluded(p)]


def _replace(content: str, data: dict):
    mode = data.get("mode", "literal")
    search = data.get("search", "")
    replace = data.get("replace", "")
    if mode == "regex":
        return re.sub(search, replace, content), len(re.findall(search, content))
    if mode in ["symbol", "rename"]:
        symbol = data.get("symbol") or search
        new = data.get("new_name") or replace
        pattern = r"\b" + re.escape(symbol) + r"\b"
        return re.sub(pattern, new, content), len(re.findall(pattern, content))
    if mode == "import":
        return content.replace(search, replace), content.count(search)
    if mode == "organize_imports":
        lines = content.splitlines()
        imports = sorted([l for l in lines if l.startswith("import ") or l.startswith("from ")])
        rest = [l for l in lines if not (l.startswith("import ") or l.startswith("from "))]
        return "\n".join(imports + rest) + ("\n" if content.endswith("\n") else ""), len(imports)
    return content.replace(search, replace), content.count(search)


@router.post("", dependencies=[Depends(verify_key)])
@router.post("/", dependencies=[Depends(verify_key)])
async def refactor_code(request: Request):
    start = time.time()
    try:
        data = await request.json()
        # Preserve legacy behavior: missing search/files are HTTP 500, empty search is allowed.
        if "search" not in data:
            raise HTTPException(status_code=500, detail={"error": {"code": "internal_error", "message": "Missing search parameter"}, "status": 500})
        if "files" not in data:
            raise HTTPException(status_code=500, detail={"error": {"code": "internal_error", "message": "Missing files parameter"}, "status": 500})
        if data.get("fault") == "io":
            return {"error": {"code": "io_error", "message": "I/O error occurred"}, "status": 500, "latency_ms": round((time.time()-start)*1000,2), "timestamp": int(time.time()*1000)}
        mode = data.get("mode", "literal")
        if mode not in ["literal","regex","ast","symbol","import","rename","move","extract_function","inline_variable","organize_imports","codemod"]:
            return {"error": {"code": "unsupported_mode", "message": f"Unsupported refactor mode: {mode}"}, "status": 400}
        if mode in ["move", "extract_function", "inline_variable", "ast", "codemod"] and data.get("apply"):
            return {"error": {"code": "not_implemented", "message": f"Mode {mode} requires language-specific AST engine not configured."}, "status": 400}
        files = _discover(data.get("scope"), data.get("files"))
        dry_run = bool(data.get("dry_run", False) or data.get("preview", False))
        backup = bool(data.get("backup", False))
        max_matches = int(data.get("max_matches") or 100000)
        results = []
        changed_files = []
        all_diff = []
        matches = []
        match_count = 0
        for file in files:
            if match_count >= max_matches:
                break
            try:
                with open(file, "r", encoding="utf-8") as f:
                    old = f.read()
            except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
                continue
            new, count = _replace(old, data)
            changed = old != new
            if count:
                match_count += count
                matches.append({"file": file, "count": count})
            if changed:
                changed_files.append(file)
                diff = "\n".join(difflib.unified_diff(old.splitlines(), new.splitlines(), fromfile=file, tofile=file, lineterm=""))
                all_diff.append(diff)
                if not dry_run:
                    if backup:
                        shutil.copy2(file, f"{file}.bak.{int(time.time()*1000)}")
                    with open(file, "w", encoding="utf-8") as f:
                        f.write(new)
            results.append({"file": file, "changed": changed, "matches": count, "preview": all_diff[-1][:250] if changed and all_diff else ""})
        if not changed_files:
            if not results:
                return {"result": [], "results": [], "changed_files": [], "matches": matches, "risk_level": "low", "latency_ms": round((time.time()-start)*1000,2), "timestamp": int(time.time()*1000)}
            return {"result": "No matches found.", "results": results, "changed_files": [], "matches": matches, "risk_level": "low", "latency_ms": round((time.time()-start)*1000,2), "timestamp": int(time.time()*1000)}
        risk = "high" if len(changed_files) > 20 or match_count > 200 else "medium" if len(changed_files) > 3 or match_count > 20 else "low"
        return {"result": results, "results": results, "changed_files": changed_files, "diff": "\n".join(all_diff)[:50000], "matches": matches, "risk_level": risk, "dry_run": dry_run, "latency_ms": round((time.time()-start)*1000,2), "timestamp": int(time.time()*1000)}
    except HTTPException:
        raise
    except Exception as e:
        return {"error": {"code": "internal_error", "message": str(e)}, "status": 500, "latency_ms": round((time.time()-start)*1000,2), "timestamp": int(time.time()*1000)}
