@echo off
"%~dp0..\runtime_vendor\windows-py312\python.exe" -I -B -X utf8 "%~dp0stable_updater.py" %*
exit /b %errorlevel%
