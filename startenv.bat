@echo off
rem Activate the local virtual environment.
rem A venv is not portable: create it on THIS machine, never copy
rem one from another computer. Create it first with:
rem   py -3.14 -m venv venv314
rem   venv314\Scripts\pip install -r requirements.txt pyinstaller
rem ("python" works in place of "py" if the launcher is missing.)

if exist "venv314\Scripts\activate.bat" (
    call venv314\Scripts\activate.bat
) else (
    echo No virtual environment found. Create one on this machine with:
    echo   py -3.14 -m venv venv314
    echo   venv314\Scripts\pip install -r requirements.txt pyinstaller
)
