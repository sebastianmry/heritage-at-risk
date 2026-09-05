@echo off
REM Builds the debug APK of the Heritage app and injects the API keys from .env
REM as --dart-define (the keys stay out of the code and the repo):
REM   OPENROUTESERVICE_API_KEY -> ORS_API_KEY  (routing)
REM   MAPTILER_API_KEY         -> MAPTILER_KEY  (basemap)
REM Run from the repo root: build_app.bat  (Git Bash: cmd //c build_app.bat)
setlocal

set "ORS_KEY="
set "MAPTILER_KEY="
for /f "usebackq tokens=1,* delims==" %%a in ("%~dp0.env") do (
    if /i "%%a"=="OPENROUTESERVICE_API_KEY" set "ORS_KEY=%%b"
    if /i "%%a"=="MAPTILER_API_KEY" set "MAPTILER_KEY=%%b"
)

if "%ORS_KEY%"=="" (
    echo [build_app] Note: OPENROUTESERVICE_API_KEY in .env is empty -^> routing stays disabled in the APK.
) else (
    echo [build_app] ORS key picked up from .env.
)

if "%MAPTILER_KEY%"=="" (
    echo [build_app] Warning: MAPTILER_API_KEY in .env is empty -^> the basemap has no fallback and will not render.
) else (
    echo [build_app] MapTiler key picked up from .env.
)

cd /d "%~dp0app"

REM tooling\heritage_win_env.bat is an optional local wrapper that pins JAVA_HOME,
REM ANDROID_HOME and a clean PATH against MSYS shadowing. It is machine-specific
REM and stays out of the repo. Without it the build uses the flutter and JDK
REM already on PATH, which is what the manual steps in the README do as well.
set "BUILD_ARGS=build apk --debug --dart-define=ORS_API_KEY=%ORS_KEY% --dart-define=MAPTILER_KEY=%MAPTILER_KEY%"

if exist "%~dp0tooling\heritage_win_env.bat" (
    call "%~dp0tooling\heritage_win_env.bat" flutter.bat %BUILD_ARGS%
) else (
    call flutter.bat %BUILD_ARGS%
)
