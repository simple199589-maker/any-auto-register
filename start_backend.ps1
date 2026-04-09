param(
    [string]$PythonVersion = "",
    [string]$BindHost = "0.0.0.0",
    [int]$Port = 8000,
    [switch]$RestartExisting = $true
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$pyenv = Get-Command pyenv -ErrorAction SilentlyContinue
if (-not $pyenv) {
    Write-Error "未找到 pyenv 命令。请先安装 pyenv-win，并确保 pyenv 可在终端中使用。"
    exit 1
}

$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Error "未找到 uv 命令。请先安装 uv，并确保 uv 可在终端中使用。"
    exit 1
}

if (-not $PythonVersion) {
    $pythonVersionFile = Join-Path $root ".python-version"
    if (-not (Test-Path $pythonVersionFile)) {
        Write-Error "未找到 .python-version，请先在仓库根目录声明 Python 版本。"
        exit 1
    }
    $PythonVersion = (Get-Content $pythonVersionFile -TotalCount 1).Trim()
}

$env:PYENV_VERSION = $PythonVersion
$pyenvPython = (& $pyenv.Source which python).Trim()
if (-not $pyenvPython -or -not (Test-Path $pyenvPython)) {
    Write-Error "pyenv 未找到 Python $PythonVersion，请先执行 'pyenv install $PythonVersion'。"
    exit 1
}

Write-Host "[INFO] 项目目录: $root"
Write-Host "[INFO] 使用 pyenv Python: $PythonVersion"
$displayHost = if ($BindHost -eq "0.0.0.0") { "localhost" } else { $BindHost }
Write-Host "[INFO] 启动后端: http://$displayHost`:$Port"
Write-Host "[INFO] 按 Ctrl+C 可停止服务"

if ($RestartExisting) {
    Write-Host "[INFO] 启动前先清理旧的后端 / Solver 进程"
    & pwsh -NoLogo -File "$root\stop_backend.ps1" -BackendPort $Port -SolverPort 8889 -FullStop 0
}

$pythonExe = (& $uv.Source run --python $pyenvPython python -c "import sys; print(sys.executable)").Trim()
if (-not (Test-Path $pythonExe)) {
    Write-Error "uv 未能创建项目虚拟环境，请先执行 'uv sync --python $pyenvPython'。"
    exit 1
}

$env:HOST = $BindHost
$env:PORT = [string]$Port

Write-Host "[INFO] Python: $pythonExe"
& $uv.Source run --python $pyenvPython python main.py
