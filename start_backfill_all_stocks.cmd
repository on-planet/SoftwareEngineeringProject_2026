@echo off
setlocal EnableDelayedExpansion

set "PROJECT_DIR=%~dp0"
set "REPO_DIR=%PROJECT_DIR%repo"
set "STATE_DIR=%REPO_DIR%\etl\state"
set "ENV_FILE=%PROJECT_DIR%.env.local"
set "VENV_PYTHON=%PROJECT_DIR%.venv\Scripts\python.exe"
set "SYSTEM_PYTHON=C:\Users\123\AppData\Local\Programs\Python\Python312\python.exe"
set "CHECK_CMD=import importlib.util,sys;mods='fastapi,uvicorn,sqlalchemy,psycopg2,pydantic,redis,yaml,pysnowball,baostock,akshare'.split(',');missing=[m for m in mods if importlib.util.find_spec(m) is None];print('Missing Python modules: ' + ', '.join(missing)) if missing else None;sys.exit(1 if missing else 0)"
set "FINANCIAL_START=2026-01-01"
set "EVENTS_START=2026-03-01"
set "DRY_RUN=0"
set "RESET_PROGRESS=0"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--dry-run" (
  set "DRY_RUN=1"
  shift
  goto parse_args
)
if /I "%~1"=="--financial-start" (
  set "FINANCIAL_START=%~2"
  shift
  shift
  goto parse_args
)
if /I "%~1"=="--events-start" (
  set "EVENTS_START=%~2"
  shift
  shift
  goto parse_args
)
if /I "%~1"=="--reset-progress" (
  set "RESET_PROGRESS=1"
  shift
  goto parse_args
)
echo Unknown argument: %~1
exit /b 1

:args_done
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
set "RUN_SIGNATURE=start_backfill_all_stocks:v2,financial=%FINANCIAL_START%,events=%EVENTS_START%"
set "PROGRESS_FILE=%STATE_DIR%\start_backfill_all_stocks.progress"
set "LAST_COMPLETED_STAGE=0"

if exist "%VENV_PYTHON%" (
  set "RUN_PYTHON=%VENV_PYTHON%"
) else (
  set "RUN_PYTHON=%SYSTEM_PYTHON%"
)

set "PYTHONPATH=%REPO_DIR%;%REPO_DIR%\api;%PYTHONPATH%"
cd /d "%PROJECT_DIR%"

if "%RESET_PROGRESS%"=="1" call :reset_progress

"%RUN_PYTHON%" -c "%CHECK_CMD%"
if errorlevel 1 (
  echo Selected interpreter: "%RUN_PYTHON%"
  echo Python environment is incomplete. Install dependencies before backfilling stock data.
  exit /b 1
)

call :load_progress
set "DETAILS_CMD=repo\etl\backfill_stock_details.py --markets A,HK"
set "BOOTSTRAP_CMD=repo\etl\bootstrap_stock_data.py"
if "%RESET_PROGRESS%"=="1" (
  set "DETAILS_CMD=!DETAILS_CMD! --reset-progress"
  set "BOOTSTRAP_CMD=!BOOTSTRAP_CMD! --reset-progress"
)

call :run_stage_script 1 "Stock basics warmup - HK universe + A-share names/sectors" "repo\etl\backfill_stock_basic_enrichment.py"
if errorlevel 1 exit /b %errorlevel%

call :run_stage_script 2 "Stock detail snapshots/research/intraday" "%DETAILS_CMD%"
if errorlevel 1 exit /b %errorlevel%

call :run_stage_script 3 "Daily history and baseline financials" "%BOOTSTRAP_CMD%"
if errorlevel 1 exit /b %errorlevel%

call :run_stage_inline 4 "Financial incremental refresh" "from datetime import date; from repo.etl.jobs.financial_job import run_financial_job; print(run_financial_job(date.fromisoformat('%FINANCIAL_START%'), date.today()))"
if errorlevel 1 exit /b %errorlevel%

call :run_stage_inline 5 "Events refresh" "from datetime import date; from repo.etl.jobs.events_job import run_events_job; print(run_events_job(date.fromisoformat('%EVENTS_START%'), date.today()))"
if errorlevel 1 exit /b %errorlevel%

call :clear_progress

echo.
echo All stock backfill steps completed.
exit /b 0

:load_progress
if not exist "%PROGRESS_FILE%" exit /b 0
for /f "usebackq tokens=1,2,3 delims=|" %%A in ("%PROGRESS_FILE%") do (
  set "PROGRESS_SIGNATURE=%%A"
  set "LAST_COMPLETED_STAGE=%%B"
  set "LAST_COMPLETED_NAME=%%C"
)
if /I not "!PROGRESS_SIGNATURE!"=="%RUN_SIGNATURE%" (
  set "LAST_COMPLETED_STAGE=0"
  set "LAST_COMPLETED_NAME="
  exit /b 0
)
if not defined LAST_COMPLETED_STAGE set "LAST_COMPLETED_STAGE=0"
if !LAST_COMPLETED_STAGE! GTR 0 (
  echo Resuming from stage !LAST_COMPLETED_STAGE! ^(!LAST_COMPLETED_NAME!^)
)
exit /b 0

:save_progress
if "%DRY_RUN%"=="1" exit /b 0
if not exist "%STATE_DIR%" mkdir "%STATE_DIR%"
> "%PROGRESS_FILE%" echo %RUN_SIGNATURE%^|%~1^|%~2
exit /b 0

:clear_progress
if exist "%PROGRESS_FILE%" del /q "%PROGRESS_FILE%" >nul 2>nul
exit /b 0

:reset_progress
call :clear_progress
exit /b 0

:run_stage_script
set "STAGE_NUM=%~1"
set "STEP_NAME=%~2"
if !LAST_COMPLETED_STAGE! GEQ !STAGE_NUM! (
  echo.
  echo [Skip completed stage !STAGE_NUM!] %STEP_NAME%
  exit /b 0
)
call :run_script "%STEP_NAME%" "%~3"
if errorlevel 1 exit /b %errorlevel%
call :save_progress "%STAGE_NUM%" "%STEP_NAME%"
set "LAST_COMPLETED_STAGE=%STAGE_NUM%"
exit /b 0

:run_stage_inline
set "STAGE_NUM=%~1"
set "STEP_NAME=%~2"
if !LAST_COMPLETED_STAGE! GEQ !STAGE_NUM! (
  echo.
  echo [Skip completed stage !STAGE_NUM!] %STEP_NAME%
  exit /b 0
)
call :run_inline "%STEP_NAME%" "%~3"
if errorlevel 1 exit /b %errorlevel%
call :save_progress "%STAGE_NUM%" "%STEP_NAME%"
set "LAST_COMPLETED_STAGE=%STAGE_NUM%"
exit /b 0

:run_script
set "STEP_NAME=%~1"
echo.
echo [%STEP_NAME%]
if "%DRY_RUN%"=="1" (
  echo Command: "%RUN_PYTHON%" %~2
  exit /b 0
)
"%RUN_PYTHON%" %~2
exit /b %errorlevel%

:run_inline
set "STEP_NAME=%~1"
echo.
echo [%STEP_NAME%]
if "%DRY_RUN%"=="1" (
  echo Command: "%RUN_PYTHON%" -c "%~2"
  exit /b 0
)
"%RUN_PYTHON%" -c "%~2"
exit /b %errorlevel%
