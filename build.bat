@echo off
rem Builds "THUG Pro Trick Editor.exe" (needs Python 3 with PyInstaller: pip install pyinstaller)
cd /d "%~dp0"
python -m PyInstaller --noconfirm --onefile --windowed --name "THUG Pro Trick Editor" ^
  --icon "%~dp0icon.ico" --add-data "%~dp0catalog.json;." --add-data "%~dp0icon.ico;." ^
  --exclude-module pygame --exclude-module PIL --exclude-module numpy ^
  --distpath "%~dp0." --workpath "%TEMP%\thugpro-trick-editor-build" --specpath "%TEMP%\thugpro-trick-editor-build" ^
  "%~dp0app.py"
if errorlevel 1 pause
