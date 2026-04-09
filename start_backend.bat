@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_VERSION=%APP_PYTHON_VERSION%"
if "%PYTHON_VERSION%"=="" if exist ".python-version" set /p PYTHON_VERSION=<.python-version
set "HOST=%HOST%"
if "%HOST%"=="" set "HOST=0.0.0.0"
set "PORT=%PORT%"
if "%PORT%"=="" set "PORT=8000"
set "RESTART_EXISTING=%RESTART_EXISTING%"
if "%RESTART_EXISTING%"=="" set "RESTART_EXISTING=1"

where pyenv >nul 2>nul
if errorlevel 1 (
  echo [ERROR] 未找到 pyenv 命令。请先安装 pyenv-win，并确保 pyenv 可在终端中使用。
  exit /b 1
)

where uv >nul 2>nul
if errorlevel 1 (
  echo [ERROR] 未找到 uv 命令。请先安装 uv，并确保 uv 可在终端中使用。
  exit /b 1
)

if "%PYTHON_VERSION%"=="" (
  echo [ERROR] 未找到 .python-version，请先在仓库根目录声明 Python 版本。
  exit /b 1
)

set "PYENV_VERSION=%PYTHON_VERSION%"
for /f "usebackq delims=" %%i in (`pyenv which python 2^>nul`) do set "PYENV_PYTHON=%%i"

if not exist "%PYENV_PYTHON%" (
  echo [ERROR] pyenv 未找到 Python %PYTHON_VERSION%，请先执行 pyenv install %PYTHON_VERSION%。
  exit /b 1
)

echo [INFO] 项目目录: %CD%
echo [INFO] 使用 pyenv Python: %PYTHON_VERSION%
echo [INFO] 启动后端: http://localhost:%PORT%
echo [INFO] 按 Ctrl+C 可停止服务

if "%RESTART_EXISTING%"=="1" (
  echo [INFO] 启动前先清理旧的后端 / Solver 进程
  pwsh -NoLogo -File "%~dp0stop_backend.ps1" -BackendPort %PORT% -SolverPort 8889 -FullStop 0
)

set "PYTHON_EXE="
for /f "usebackq delims=" %%i in (`uv run --python "%PYENV_PYTHON%" cmd /c where python`) do if not defined PYTHON_EXE set "PYTHON_EXE=%%i"

if not exist "%PYTHON_EXE%" (
  echo [ERROR] uv 未能创建项目虚拟环境，请先执行 uv sync --python "%PYENV_PYTHON%"。
  exit /b 1
)

set "HOST=%HOST%"
set "PORT=%PORT%"
echo [INFO] Python: %PYTHON_EXE%
uv run --python "%PYENV_PYTHON%" python main.py
