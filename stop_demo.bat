@echo off
setlocal EnableDelayedExpansion

:: ---------------------------------------------------------------------------
:: SplatLib demo -- stop
::
:: Finds and kills every python.exe whose command line contains "main.py".
:: Also closes the "SplatLib Demo" console window if still open.
:: ---------------------------------------------------------------------------

echo.
echo  SplatLib RF Demo -- stopping...

set "FOUND=0"

for /f "skip=1 tokens=1" %%P in (
    'wmic process where "name='python.exe' and commandline like '%%main.py%%'" get processid 2^>nul'
) do (
    if not "%%P"=="" (
        echo  Killing PID %%P
        taskkill /PID %%P /F >nul 2>&1
        set "FOUND=1"
    )
)

:: Close the console window as well (kills cmd.exe + child tree).
taskkill /FI "WINDOWTITLE eq SplatLib Demo" /T /F >nul 2>&1

if "!FOUND!"=="1" (
    echo  Done.
) else (
    echo  No running SplatLib demo found.
)

echo.
