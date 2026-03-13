@echo off
setlocal

REM 启动 FastAPI API 服务（系统 Python）
cd /d %~dp0\repo\api
set PYTHONPATH=%~dp0\repo
"C:\Users\123\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
