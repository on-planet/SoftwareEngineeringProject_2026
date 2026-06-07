@echo off
REM 启动本地 Redis（需先下载并解压到 services\redis）
cd /d %~dp0\services\redis
start /b redis-server.exe
echo Redis started on localhost:6379
