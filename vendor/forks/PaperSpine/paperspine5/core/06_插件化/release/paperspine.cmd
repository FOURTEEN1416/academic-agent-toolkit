@echo off
"%~dp0runtime_vendor\windows-py312\python.exe" -I -B -X utf8 "%~dp0release\product_launcher.py" %*
exit /b %errorlevel%
