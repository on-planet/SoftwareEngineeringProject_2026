@echo off
setlocal

set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

REM Æô¶¯ Web Ç°¶Ë
cd /d "%PROJECT_DIR%\repo\web"
npm run dev
