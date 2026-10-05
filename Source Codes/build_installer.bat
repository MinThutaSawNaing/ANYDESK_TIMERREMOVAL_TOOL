@echo off
cd /d "%~dp0"
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss > iscc.log 2>&1
echo ISCC_EXITCODE=%errorlevel% >> iscc.log
exit /b %errorlevel%
