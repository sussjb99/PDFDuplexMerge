@echo off
setlocal

cd /d "%~dp0.."
set ROOT=%CD%
set DIST=%ROOT%\dist\PDFDuplexMerge

rem ---------- preflight: always build from the project venv ----------
rem A bare "pyinstaller" on PATH may resolve to a global Python install,
rem which silently produces an executable missing PySide6 and friends.
if not exist "%ROOT%\venv314\Scripts\pyinstaller.exe" (
  echo ERROR: venv314 is missing or has no pyinstaller.
  echo Create it on THIS machine with:
  echo     py -3.14 -m venv venv314
  echo ^(use "python" instead of "py" if the launcher is not installed^)
  echo Then install the dependencies:
  echo     venv314\Scripts\pip install -r requirements.txt pyinstaller
  exit /b 1
)

"%ROOT%\venv314\Scripts\python.exe" -c "import PySide6.QtWidgets, pypdf, PIL, numpy, cv2, pdf2image; print('Dependencies OK - PySide6 ' + PySide6.__version__)"
if errorlevel 1 (
  echo ERROR: required packages are not installed in venv314.
  echo Run:   venv314\Scripts\pip install -r requirements.txt pyinstaller
  exit /b 1
)

rem ---------- build ----------
if exist "%DIST%\PDFDuplexMerge.exe" del "%DIST%\PDFDuplexMerge.exe"

"%ROOT%\venv314\Scripts\pyinstaller.exe" --clean --noconfirm ^
  --onedir ^
  --noconsole ^
  --name PDFDuplexMerge ^
  --distpath "%ROOT%\dist" ^
  --workpath "%ROOT%\dist\work" ^
  --specpath "%ROOT%\dist" ^
  --add-data "%ROOT%\LICENSE.txt;." ^
  --add-data "%ROOT%\README.txt;." ^
  --add-data "%ROOT%\THIRD-PARTY-NOTICES.txt;." ^
  --exclude-module qt_material ^
  --exclude-module PySide6.QtWebEngineWidgets ^
  --exclude-module PySide6.QtWebEngineCore ^
  --exclude-module PySide6.QtQuick ^
  --exclude-module PySide6.QtQml ^
  --exclude-module PySide6.Qt3DRender ^
  --exclude-module PySide6.QtCharts ^
  --exclude-module PySide6.QtMultimedia ^
  --exclude-module PySide6.QtTest ^
  pdf_duplex_merge_gui.py

if not exist "%DIST%\PDFDuplexMerge.exe" (
  echo Build failed.
  exit /b 1
)

rem ---------- poppler binaries ----------
xcopy /E /I /Y "%ROOT%\tools\poppler\Library\bin" "%DIST%\tools\poppler\Library\bin"

rem ---------- poppler data (CJK only; delete these four if you never deskew CJK) ----------
if exist "%ROOT%\tools\poppler\share\poppler\cMap"        xcopy /E /I /Y "%ROOT%\tools\poppler\share\poppler\cMap"        "%DIST%\tools\poppler\share\poppler\cMap"
if exist "%ROOT%\tools\poppler\share\poppler\cidToUnicode" xcopy /E /I /Y "%ROOT%\tools\poppler\share\poppler\cidToUnicode" "%DIST%\tools\poppler\share\poppler\cidToUnicode"
if exist "%ROOT%\tools\poppler\share\poppler\nameToUnicode" xcopy /E /I /Y "%ROOT%\tools\poppler\share\poppler\nameToUnicode" "%DIST%\tools\poppler\share\poppler\nameToUnicode"
if exist "%ROOT%\tools\poppler\share\poppler\unicodeMap"   xcopy /E /I /Y "%ROOT%\tools\poppler\share\poppler\unicodeMap"   "%DIST%\tools\poppler\share\poppler\unicodeMap"

rem ---------- trim unused native binaries from the bundle ----------
rem OpenCV's video codec backend: this app only rotates images, never reads
rem or writes video, so the ffmpeg DLL is dead weight.
if exist "%DIST%\_internal\cv2\opencv_videoio_ffmpeg500_64.dll" del "%DIST%\_internal\cv2\opencv_videoio_ffmpeg500_64.dll"

rem Pillow's AVIF codec: pdf2image hands Pillow PNG/PPM data only.
if exist "%DIST%\_internal\PIL\_avif.cp314-win_amd64.pyd" del "%DIST%\_internal\PIL\_avif.cp314-win_amd64.pyd"

rem Qt QML/Quick engine: the GUI uses QtCore/QtGui/QtWidgets only.
for %%f in (Qt6Quick.dll Qt6Qml.dll Qt6QmlModels.dll Qt6QmlMeta.dll Qt6QmlWorkerScript.dll) do (
  if exist "%DIST%\_internal\PySide6\%%f" del "%DIST%\_internal\PySide6\%%f"
)

rem ---------- licence, readme and third-party notices visible next to the exe ----------
copy /Y "%ROOT%\LICENSE.txt" "%DIST%\LICENSE.txt"
copy /Y "%ROOT%\README.txt"  "%DIST%\README.txt"
copy /Y "%ROOT%\THIRD-PARTY-NOTICES.txt" "%DIST%\THIRD-PARTY-NOTICES.txt"

rem ---------- optional zip ----------
powershell -NoProfile -Command "Compress-Archive -Path '%DIST%' -DestinationPath '%ROOT%\dist\PDFDuplexMerge-1.2-portable.zip' -Force"

echo.
echo Portable app: %DIST%