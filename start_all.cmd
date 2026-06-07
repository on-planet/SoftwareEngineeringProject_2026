@echo off
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

echo ==========================================
echo  QuantPulse 一键启动
echo ==========================================
echo.

REM 1. PostgreSQL
echo [1/4] 启动 PostgreSQL...
call start_postgres.cmd
if errorlevel 1 (
  echo       警告: PostgreSQL 可能已在运行或启动失败
) else (
  echo       OK
)

REM 2. Redis + API
echo [2/4] 启动 API（含 Redis）...
start "QuantPulse API" cmd /k "cd /d "%PROJECT_DIR%" && call start_api.cmd"

REM 3. ETL
echo [3/4] 启动 ETL...
call start_etl.cmd
if errorlevel 1 (
  echo       警告: ETL 可能已在运行或启动失败
) else (
  echo       OK
)

REM 4. Web
echo [4/4] 启动 Web 前端...
start "QuantPulse Web" cmd /k "cd /d "%PROJECT_DIR%" && call start_web.cmd"

echo.
echo ==========================================
echo  所有服务已启动
echo ==========================================
echo.
echo 访问地址:
echo   API:  http://localhost:8000
echo   Web:  http://localhost:3000
echo.
pause
