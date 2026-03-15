@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "REPO_DIR=%PROJECT_DIR%repo"
set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "LOCK_FILE=%REPO_DIR%\state\etl.lock"

if not exist "%LOCK_FILE%" (
  echo ETL is not running. No lock file found.
  exit /b 0
)

"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -Command ^
  "$lockPath = '%LOCK_FILE%';" ^
  "try { $payload = Get-Content -Path $lockPath -Raw | ConvertFrom-Json } catch { Remove-Item -Path $lockPath -Force -ErrorAction SilentlyContinue; Write-Host 'Cleared invalid ETL lock file.'; exit 0 };" ^
  "$etlPid = 0; if ($payload -and $payload.pid) { $etlPid = [int]$payload.pid };" ^
  "if ($etlPid -le 0) { Remove-Item -Path $lockPath -Force -ErrorAction SilentlyContinue; Write-Host 'Cleared ETL lock file without valid PID.'; exit 0 };" ^
  "$proc = Get-Process -Id $etlPid -ErrorAction SilentlyContinue;" ^
  "if (-not $proc) { Remove-Item -Path $lockPath -Force -ErrorAction SilentlyContinue; Write-Host ('Cleared stale ETL lock for PID ' + $etlPid); exit 0 };" ^
  "Stop-Process -Id $etlPid -Force -ErrorAction Stop; Start-Sleep -Milliseconds 300; Remove-Item -Path $lockPath -Force -ErrorAction SilentlyContinue; Write-Host ('Stopped ETL process ' + $etlPid); exit 0"
if errorlevel 1 exit /b %errorlevel%

endlocal
exit /b 0
