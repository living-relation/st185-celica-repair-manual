@echo off
REM Launches the ST185 Celica repair manual app with a local server so the
REM embedded PDF viewer and thumbnails work in any browser.
REM Serves the package root (contains index.html, manuals\, celica-manual\, electrical\).
REM Prefer CelicaManual.exe - it adds the in-app "Add manuals" feature.
cd /d "%~dp0.."
start "" http://localhost:8765/index.html
where python >nul 2>nul && (python -m http.server 8765) || (py -m http.server 8765)
