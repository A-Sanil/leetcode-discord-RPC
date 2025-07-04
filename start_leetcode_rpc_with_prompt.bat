@echo off
set CHROME_PATH="C:\Program Files\Google\Chrome\Application\chrome.exe"

REM Check if Chrome exists at default path
if exist %CHROME_PATH% (
    echo Chrome found at default path.
) else (
    echo Chrome not found at %CHROME_PATH%
    echo Please locate chrome.exe manually.
    timeout /t 2
    explorer .
    pause
    exit /b
)

echo Launching Chrome in debug mode...
start "" %CHROME_PATH% --remote-debugging-port=9222 --user-data-dir="chrome_debug_profile"
timeout /t 3 >nul

echo Starting LeetCode RPC GUI...
start python leetcode_rpc_gui.py
pause
