@echo off
REM Baut die Debug-APK der Heritage-App und injiziert die API-Keys aus der .env
REM als --dart-define (die Keys bleiben aus Code und Repo heraus):
REM   OPENROUTESERVICE_API_KEY -> ORS_API_KEY  (Routing)
REM   MAPTILER_API_KEY         -> MAPTILER_KEY  (Hintergrundkarte)
REM Aufruf aus der Repo-Wurzel: build_app.bat  (Git-Bash: cmd //c build_app.bat)
setlocal

set "ORS_KEY="
set "MAPTILER_KEY="
for /f "usebackq tokens=1,* delims==" %%a in ("%~dp0.env") do (
    if /i "%%a"=="OPENROUTESERVICE_API_KEY" set "ORS_KEY=%%b"
    if /i "%%a"=="MAPTILER_API_KEY" set "MAPTILER_KEY=%%b"
)

if "%ORS_KEY%"=="" (
    echo [build_app] Hinweis: OPENROUTESERVICE_API_KEY in .env ist leer -^> Routing bleibt in der APK deaktiviert.
) else (
    echo [build_app] ORS-Key aus .env uebernommen.
)

if "%MAPTILER_KEY%"=="" (
    echo [build_app] Hinweis: MAPTILER_API_KEY in .env ist leer -^> Basemap faellt auf CARTO Positron zurueck.
) else (
    echo [build_app] MapTiler-Key aus .env uebernommen.
)

cd /d "%~dp0app"
call C:\Users\sebas\heritage_win_env.bat flutter.bat build apk --debug --dart-define=ORS_API_KEY=%ORS_KEY% --dart-define=MAPTILER_KEY=%MAPTILER_KEY%
