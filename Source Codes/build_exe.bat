@echo off
cd /d "%~dp0"
echo Building "%CD%" (onedir, optimised for size + startup) ... > build.log
python -m PyInstaller --noconfirm --clean app.spec >> build.log 2>&1
echo PYINSTALLER_EXITCODE=%errorlevel% >> build.log
exit /b %errorlevel%
