@echo off
setlocal

REM 启动 Web 前端
cd /d %~dp0\repo\web
npm run dev
