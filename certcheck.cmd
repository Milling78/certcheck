@echo off
REM Thin Windows wrapper — run certcheck from source via Python without typing
REM "python". Put this folder on your PATH to use `certcheck host...` from cmd
REM or PowerShell. (For a Python-free executable, build dist\certcheck.exe with
REM build.ps1.) The script's exit code is propagated for cron/CI/Task Scheduler.
python "%~dp0certcheck.py" %*
exit /b %errorlevel%
