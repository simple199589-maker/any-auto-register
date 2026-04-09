"""account_manager - 多平台账号管理后台"""
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from core.db import init_db
from core.registry import load_all
from api.accounts import router as accounts_router
from api.tasks import router as tasks_router
from api.platforms import router as platforms_router
from api.proxies import router as proxies_router
from api.config import router as config_router
from api.actions import router as actions_router
from api.integrations import router as integrations_router
from api.auth import router as auth_router
from api.outlook import router as outlook_router

_ROOT_DIR = Path(__file__).resolve().parent
_EXPECTED_PYTHON_VERSION = os.getenv("APP_PYTHON_VERSION", "")
_RUNTIME_CONTEXT = os.getenv("APP_RUNTIME_CONTEXT", "")


def _read_declared_python_version() -> str:
    """AI by zb: 读取仓库 `.python-version` 中声明的 Python 版本。"""
    if _EXPECTED_PYTHON_VERSION:
        return _EXPECTED_PYTHON_VERSION.strip()
    version_file = _ROOT_DIR / ".python-version"
    if not version_file.exists():
        return ""
    return version_file.read_text(encoding="utf-8").splitlines()[0].strip()


def _version_family(version: str) -> str:
    """AI by zb: 提取 major.minor 版本号，便于宽松比对运行环境。"""
    parts = [item for item in version.strip().split(".") if item]
    if len(parts) >= 2:
        return ".".join(parts[:2])
    return version.strip()


def _detect_virtual_env() -> str:
    """AI by zb: 检测当前 Python 是否运行在虚拟环境中。"""
    virtual_env = os.getenv("VIRTUAL_ENV", "").strip()
    if virtual_env:
        return os.path.basename(os.path.normpath(virtual_env))
    if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        return os.path.basename(os.path.normpath(sys.prefix))
    return ""


def _detect_pyenv_version() -> str:
    """AI by zb: 检测当前 pyenv 选中的 Python 版本。"""
    return os.getenv("PYENV_VERSION", "").strip()


def _resolve_frontend_static_dir() -> Path | None:
    """AI by zb: 解析后端可用的前端静态资源目录。"""
    candidates = [
        _ROOT_DIR / "static",
        _ROOT_DIR / "frontend" / "dist",
    ]
    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate
    return None


def _frontend_missing_page() -> str:
    """AI by zb: 生成前端未构建时的提示页。"""
    return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>前端资源未构建</title>
  <style>
    body { font-family: "Microsoft YaHei", sans-serif; background: #f7f7f8; color: #111827; margin: 0; }
    .wrap { max-width: 760px; margin: 64px auto; padding: 32px; background: #fff; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }
    h1 { margin-top: 0; font-size: 28px; }
    p, li, code, pre { font-size: 15px; line-height: 1.7; }
    code, pre { font-family: Consolas, monospace; background: #f3f4f6; border-radius: 8px; }
    code { padding: 2px 6px; }
    pre { padding: 14px 16px; overflow: auto; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>前端页面还没有构建出来</h1>
    <p>当前后端已经启动，但仓库根目录下没有可托管的 <code>static/index.html</code>。</p>
    <p>在项目根目录执行下面命令即可恢复页面：</p>
    <pre>cd frontend
npm install
cmd /c npm run build</pre>
    <p>构建完成后重启后端，再访问 <code>http://localhost:8000</code>。</p>
  </div>
</body>
</html>
""".strip()


def _print_runtime_info() -> None:
    expected_version = _read_declared_python_version()
    current_version = sys.version.split()[0]
    virtual_env = _detect_virtual_env()
    pyenv_version = _detect_pyenv_version()
    frontend_static_dir = _resolve_frontend_static_dir()
    print(f"[Runtime] Python: {sys.executable}")
    print(f"[Runtime] Python Version: {current_version}")
    print(f"[Runtime] Virtual Env: {virtual_env or '未检测到'}")
    print(f"[Runtime] pyenv Version: {pyenv_version or '未检测到'}")
    print(f"[Runtime] Frontend Static: {frontend_static_dir or '未检测到'}")
    if _RUNTIME_CONTEXT == "docker":
        return
    if expected_version and _version_family(current_version) != _version_family(expected_version):
        print(
            f"[WARN] 当前 Python 版本为 '{current_version}'，推荐先通过 pyenv 切换到 '{expected_version}'，"
            "再使用 uv 启动项目，否则 Turnstile Solver 可能因依赖缺失而无法启动。"
        )
    elif not virtual_env:
        print(
            "[WARN] 未检测到项目虚拟环境，推荐使用 'uv run python main.py' 或启动脚本运行，"
            "否则 Turnstile Solver 可能因依赖缺失而无法启动。"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _print_runtime_info()
    init_db()
    load_all()
    print("[OK] 数据库初始化完成")
    from core.registry import list_platforms
    print(f"[OK] 已加载平台: {[p['name'] for p in list_platforms()]}")
    from core.scheduler import scheduler
    scheduler.start()
    from services.solver_manager import start_async
    start_async()
    yield
    from core.scheduler import scheduler as _scheduler
    _scheduler.stop()
    from services.solver_manager import stop
    stop()


app = FastAPI(title="Account Manager", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/auth/") or not path.startswith("/api/"):
        return await call_next(request)
    from core.config_store import config_store as _cs
    if not _cs.get("auth_password_hash", ""):
        return await call_next(request)
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse({"detail": "未认证，请先登录"}, status_code=401)
    try:
        from api.auth import verify_token
        verify_token(auth_header[7:])
    except HTTPException as e:
        return JSONResponse({"detail": e.detail}, status_code=e.status_code)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(platforms_router, prefix="/api")
app.include_router(proxies_router, prefix="/api")
app.include_router(config_router, prefix="/api")
app.include_router(actions_router, prefix="/api")
app.include_router(integrations_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(outlook_router, prefix="/api")


@app.get("/api/solver/status")
def solver_status():
    from services.solver_manager import is_running
    return {"running": is_running()}


@app.post("/api/solver/restart")
def solver_restart():
    from services.solver_manager import stop, start_async
    stop()
    start_async()
    return {"message": "重启中"}


_static_dir = _resolve_frontend_static_dir()
if _static_dir and (_static_dir / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(_static_dir / "assets")), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str):
    if full_path.startswith(("api/", "docs", "redoc", "openapi.json")):
        raise HTTPException(status_code=404, detail="Not Found")
    if _static_dir and (_static_dir / "index.html").is_file():
        return FileResponse(_static_dir / "index.html")
    return HTMLResponse(_frontend_missing_page(), status_code=503)


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload_enabled = os.getenv("APP_RELOAD", "0").lower() in {"1", "true", "yes"}
    uvicorn.run("main:app", host=host, port=port, reload=reload_enabled)
