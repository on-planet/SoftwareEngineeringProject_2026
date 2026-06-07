@echo off
REM 启动本地 PostgreSQL（数据目录位于无中文路径下，避免编码兼容性问题）
C:\Users\MR\qp_pg\bin\pg_ctl.exe -D C:\Users\MR\qp_pgdata -l C:\Users\MR\qp_pgdata\logfile start
echo PostgreSQL started on localhost:5432
