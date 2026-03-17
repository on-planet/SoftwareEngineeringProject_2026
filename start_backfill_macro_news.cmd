@echo off
setlocal EnableDelayedExpansion

set "PROJECT_DIR=%~dp0"
set "REPO_DIR=%PROJECT_DIR%repo"
set "ENV_FILE=%PROJECT_DIR%.env.local"
set "VENV_PYTHON=%PROJECT_DIR%.venv\Scripts\python.exe"
set "SYSTEM_PYTHON=C:\Users\123\AppData\Local\Programs\Python\Python312\python.exe"
set "CHECK_CMD=import importlib.util,sys;mods='sqlalchemy,psycopg2,pydantic,yaml,redis,akshare'.split(',');missing=[m for m in mods if importlib.util.find_spec(m) is None];print('Missing Python modules: ' + ', '.join(missing)) if missing else None;sys.exit(1 if missing else 0)"
set "MACRO_START=2024-01-01"
set "NEWS_START=2026-03-01"
set "WORLDBANK_START=2024-01-01"
set "INCLUDE_WORLDBANK=0"
set "SKIP_MACRO=0"
set "SKIP_NEWS=0"
set "DRY_RUN=0"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--dry-run" (
  set "DRY_RUN=1"
  shift
  goto parse_args
)
if /I "%~1"=="--macro-start" (
  set "MACRO_START=%~2"
  shift
  shift
  goto parse_args
)
if /I "%~1"=="--news-start" (
  set "NEWS_START=%~2"
  shift
  shift
  goto parse_args
)
if /I "%~1"=="--worldbank-start" (
  set "WORLDBANK_START=%~2"
  shift
  shift
  goto parse_args
)
if /I "%~1"=="--include-worldbank" (
  set "INCLUDE_WORLDBANK=1"
  shift
  goto parse_args
)
if /I "%~1"=="--skip-macro" (
  set "SKIP_MACRO=1"
  shift
  goto parse_args
)
if /I "%~1"=="--skip-news" (
  set "SKIP_NEWS=1"
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

if exist "%VENV_PYTHON%" (
  set "RUN_PYTHON=%VENV_PYTHON%"
) else (
  set "RUN_PYTHON=%SYSTEM_PYTHON%"
)

set "PYTHONPATH=%REPO_DIR%;%REPO_DIR%\api;%PYTHONPATH%"
cd /d "%PROJECT_DIR%"

"%RUN_PYTHON%" -c "%CHECK_CMD%"
if errorlevel 1 (
  echo Selected interpreter: "%RUN_PYTHON%"
  echo Python environment is incomplete. Install dependencies before backfilling macro and news data.
  exit /b 1
)

set "CMD=repo\etl\backfill_macro_news.py --macro-start %MACRO_START% --news-start %NEWS_START% --worldbank-start %WORLDBANK_START%"
if "%INCLUDE_WORLDBANK%"=="1" set "CMD=%CMD% --include-worldbank"
if "%SKIP_MACRO%"=="1" set "CMD=%CMD% --skip-macro"
if "%SKIP_NEWS%"=="1" set "CMD=%CMD% --skip-news"

echo.
echo [Macro + News backfill]
if "%DRY_RUN%"=="1" (
  echo Command: "%RUN_PYTHON%" %CMD%
  exit /b 0
)

"%RUN_PYTHON%" %CMD%
exit /b %errorlevel%
