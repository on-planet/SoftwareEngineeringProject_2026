@echo off
setlocal EnableDelayedExpansion

set "PROJECT_DIR=%~dp0"
set "REPO_DIR=%PROJECT_DIR%repo"
set "PYTHON_EXE=C:\Users\123\AppData\Local\Programs\Python\Python312\python.exe"
set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "ENV_FILE=%PROJECT_DIR%.env.local"
set "ETL_WORKDIR=%REPO_DIR%\etl"
set "LOCK_FILE=%REPO_DIR%\state\etl.lock"
set "CHECK_CMD=import importlib.util,sys;mods='fastapi,uvicorn,sqlalchemy,psycopg2,pydantic,redis,yaml,pysnowball,baostock'.split(',');missing=[m for m in mods if importlib.util.find_spec(m) is None];print('Missing Python modules: ' + ', '.join(missing)) if missing else None;sys.exit(1 if missing else 0)"

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

set "PYTHONPATH=%REPO_DIR%;%REPO_DIR%\api;%PYTHONPATH%"
if not exist "%ETL_WORKDIR%" (
  echo ETL workdir not found: "%ETL_WORKDIR%"
  exit /b 1
)

"%PYTHON_EXE%" -c "%CHECK_CMD%"
if errorlevel 1 (
  echo Selected interpreter: "%PYTHON_EXE%"
  echo Python environment is incomplete. Install dependencies before starting ETL.
  exit /b 1
)

if exist "%LOCK_FILE%" (
  "%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -Command "$lockPath = '%LOCK_FILE%'; try { $payload = Get-Content -Path $lockPath -Raw | ConvertFrom-Json } catch { $payload = $null }; $etlPid = 0; if ($payload -and $payload.pid) { $etlPid = [int]$payload.pid }; if ($etlPid -gt 0 -and (Get-Process -Id $etlPid -ErrorAction SilentlyContinue)) { Write-Host ('ETL is already running with PID ' + $etlPid); exit 10 } else { Remove-Item -Path $lockPath -Force -ErrorAction SilentlyContinue; exit 0 }"
  if errorlevel 10 exit /b 0
)

"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -Command ^
  "Start-Process -FilePath '%PYTHON_EXE%' -ArgumentList '-m','etl.scheduler' -WorkingDirectory '%ETL_WORKDIR%' -WindowStyle Hidden"
if errorlevel 1 exit /b %errorlevel%

echo ETL started in background. Logs: "%REPO_DIR%\logs\etl.log"

endlocal
exit /b 0
