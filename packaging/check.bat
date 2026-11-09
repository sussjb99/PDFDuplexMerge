@echo off
setlocal
set DIST=%~dp0..\dist\PDFDuplexMerge

if not exist "%DIST%\PDFDuplexMerge.exe"            echo MISSING: exe
if not exist "%DIST%\LICENSE.txt"                   echo MISSING: LICENSE.txt
if not exist "%DIST%\README.txt"                    echo MISSING: README.txt
if not exist "%DIST%\THIRD-PARTY-NOTICES.txt"       echo MISSING: THIRD-PARTY-NOTICES.txt
if not exist "%DIST%\tools\poppler\Library\bin\pdftoppm.exe" echo MISSING: pdftoppm.exe
if exist "%DIST%\_internal\python314.dll"           echo OK: bundled Python interpreter

rem The most common build failure is a bundle built from a global
rem Python that lacked PySide6, giving "No module named 'PySide6'"
rem at launch. Check for it here.
if exist "%DIST%\_internal\PySide6" (
    echo OK: PySide6 present in _internal
) else (
    echo MISSING: PySide6 in _internal - the build did not use the venv
)

if exist "%DIST%\tools\poppler\share\poppler\COPYING" (
    echo OK: poppler licence texts present
) else (
    echo NOTE: poppler licence texts not found under tools\poppler\share\poppler
)

echo.
echo Top level of %DIST%:
dir /B "%DIST%"