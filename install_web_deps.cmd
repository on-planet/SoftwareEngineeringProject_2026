@echo off
setlocal

REM 安装前端依赖
cd /d %~dp0\repo\web
npm install
