@echo off
setlocal

REM 启动 ETL 调度入口（单次执行）
cd /d %~dp0\repo\etl
set PYTHONPATH=%~dp0\repo;%~dp0\repo\api
"C:\Users\123\AppData\Local\Programs\Python\Python312\python.exe" -m etl.scheduler
