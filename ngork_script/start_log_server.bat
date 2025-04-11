@echo off
setlocal

REM Holiday check
set "HOLIDAY_FILE=C:\Kani_Personal\Automate_Trading\AlgoTrading\nifty_expiry_holidays.txt"
for /f %%a in ('powershell -NoProfile -Command "(Get-Date).ToString('ddMMMyy')"') do set "TODAY=%%a"
findstr /i "%TODAY%" "%HOLIDAY_FILE%" > nul
if %errorlevel%==0 (
    echo [%TODAY%] is a trading holiday. Skipping log server startup.
    exit /b
)

@echo off
cd /d C:\Kani_Personal\Automate_Trading\AlgoTrading\job_logs

REM Start Python HTTP server
start "" python -m http.server 8081

REM Wait for server to start
timeout /t 10 > NUL

REM Start ngrok using full path
start "" C:\Kani_Personal\ngrok-v3-stable-windows-amd64\ngrok.exe http 8081

REM Wait a bit to ensure ngrok is ready
timeout /t 10 > NUL

REM Call the WhatsApp sender
python C:\Kani_Personal\Automate_Trading\AlgoTrading\ngork_script\send_ngrok_whatsapp.py

endlocal
