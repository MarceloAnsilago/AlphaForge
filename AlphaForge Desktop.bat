@echo off
setlocal

set "ROOT_DIR=%~dp0"
pushd "%ROOT_DIR%" >nul

if exist "%ROOT_DIR%venv\Scripts\pythonw.exe" (
    set "PYTHON_EXE=%ROOT_DIR%venv\Scripts\pythonw.exe"
) else if exist "%ROOT_DIR%venv\Scripts\python.exe" (
    set "PYTHON_EXE=%ROOT_DIR%venv\Scripts\python.exe"
) else (
    echo Ambiente virtual nao encontrado em "%ROOT_DIR%venv".
    echo Rode os comandos de setup antes de abrir o AlphaForge.
    pause
    popd >nul
    exit /b 1
)

"%PYTHON_EXE%" "%ROOT_DIR%desktop_app.py"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Falha ao abrir o AlphaForge Desktop. Codigo: %EXIT_CODE%
    echo Verifique se as dependencias foram instaladas com:
    echo     venv\Scripts\pip install -r requirements.txt
    pause
)

popd >nul
exit /b %EXIT_CODE%
