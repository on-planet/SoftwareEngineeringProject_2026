@echo off
setlocal EnableDelayedExpansion

set "PROJECT_DIR=%~dp0"
set "REPO_DIR=%PROJECT_DIR%repo"
set "ENV_FILE=%PROJECT_DIR%.env.local"
set "VENV_PYTHON=%PROJECT_DIR%.venv\Scripts\python.exe"
for /f "usebackq delims=" %%i in (`where python 2^>nul`) do (
  if not defined SYSTEM_PYTHON set "SYSTEM_PYTHON=%%i"
)
if not defined SYSTEM_PYTHON set "SYSTEM_PYTHON=python"
set "CHECK_CMD=import importlib.util,sys;mods='fastapi,uvicorn,sqlalchemy,psycopg2,pydantic,redis,yaml,pysnowball,baostock,akshare'.split(',');missing=[m for m in mods if importlib.util.find_spec(m) is None];print('Missing Python modules: ' + ', '.join(missing)) if missing else None;sys.exit(1 if missing else 0)"

if exist "%ENV_FILE%" (
  for /f "usebackq delims=" %%A in ("%ENV_FILE%") do (
    set "LINE=%%A"
    if not "!LINE!"=="" if not "!LINE:~0,1!"=="#" (
      for /f "tokens=1* delims==" %%B in ("!LINE!") do set "%%B=%%C"
    )
  )
)

if not defined XUEQIUTOKEN if defined SNOWBALL_TOKEN set "XUEQIUTOKEN=%SNOWBALL_TOKEN%"
if not defined SNOWBALL_TOKEN if defined XUEQIUTOKEN set "SNOWBALL_TOKEN=%XUEQIUTOKEN%"

REM 自动启动 Redis（如未运行）
"%PROJECT_DIR%services\redis\redis-cli.exe" ping >nul 2>&1
if errorlevel 1 (
  echo [依赖检查] Redis 未运行，正在启动...
  start /b "" "%PROJECT_DIR%services\redis\redis-server.exe"
  timeout /t 2 /nobreak >nul
  "%PROJECT_DIR%services\redis\redis-cli.exe" ping >nul 2>&1
  if errorlevel 1 (
    echo [错误] Redis 启动失败，请检查 services\redis 目录
    exit /b 1
  )
  echo [依赖检查] Redis 已启动
)

cd /d "%REPO_DIR%\api"
set "PYTHONPATH=%REPO_DIR%;%REPO_DIR%\api;%PYTHONPATH%"
set "UVICORN_ARGS=--host 0.0.0.0 --port 8000"
if /I "%API_RELOAD%"=="1" set "UVICORN_ARGS=%UVICORN_ARGS% --reload"
if exist "%VENV_PYTHON%" (
  set "RUN_PYTHON=%VENV_PYTHON%"
) else (
  set "RUN_PYTHON=%SYSTEM_PYTHON%"
)

"%RUN_PYTHON%" -c "%CHECK_CMD%"
if errorlevel 1 (
  echo Selected interpreter: "%RUN_PYTHON%"
  echo Python environment is incomplete. Install dependencies before starting the API.
  exit /b 1
)

"%RUN_PYTHON%" -m uvicorn app.main:app %UVICORN_ARGS%
