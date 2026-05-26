@echo off
setlocal EnableDelayedExpansion

:: ---------------------------------------------------------------------------
:: SplatLib demo -- start
::
:: Starts the FastAPI server and waits until it responds on the health-check
:: endpoint before opening the browser.  No PID files -- uses HTTP polling
:: to detect whether the server is already running.
::
:: Default port: 8765  (avoids IIS / common local service conflicts)
:: Override:  set PORT=9000 && start_demo.bat
:: ---------------------------------------------------------------------------

if not defined PORT set "PORT=8765"
set "DEMO_DIR=%~dp0demo"
set "URL=http://localhost:%PORT%"
set "HEALTH=%URL%/api/capabilities"

echo.
echo  SplatLib RF Demo
echo  ================

:: ---------------------------------------------------------------------------
:: Is the server already running on this port?
:: ---------------------------------------------------------------------------
powershell -NoProfile -Command ^
    "try { Invoke-WebRequest '%HEALTH%' -TimeoutSec 2 -UseBasicParsing -EA Stop | Out-Null; exit 0 } catch { exit 1 }" ^
    >nul 2>&1
if not errorlevel 1 (
    echo  Server already running at %URL%
    echo.
    start %URL%
    exit /b 0
)

:: ---------------------------------------------------------------------------
:: Is the port taken by something else?
:: ---------------------------------------------------------------------------
netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo  ERROR: Port %PORT% is already in use by another process.
    echo  Stop that process first, or run:  set PORT=9000 ^&^& start_demo.bat
    echo.
    pause
    exit /b 1
)

:: ---------------------------------------------------------------------------
:: Launch the server in a new console window.
:: ---------------------------------------------------------------------------
echo  Starting server at %URL% ...
cd /d "%DEMO_DIR%"
start "SplatLib Demo" python main.py

:: ---------------------------------------------------------------------------
:: Poll until the server responds (up to 30 s) then open the browser.
:: ---------------------------------------------------------------------------
echo  Waiting for server
set /a TRIES=0
:poll
timeout /t 1 /nobreak >nul
set /a TRIES+=1
<nul set /p "=."
powershell -NoProfile -Command ^
    "try { Invoke-WebRequest '%HEALTH%' -TimeoutSec 1 -UseBasicParsing -EA Stop | Out-Null; exit 0 } catch { exit 1 }" ^
    >nul 2>&1
if not errorlevel 1 goto :ready
if !TRIES! lss 30 goto :poll

echo.
echo  WARNING: Server did not respond after 30 s.
echo  Check the "SplatLib Demo" console window for errors.
echo.
pause
exit /b 1

:ready
echo.
echo  Ready at %URL%
echo.
start %URL%
