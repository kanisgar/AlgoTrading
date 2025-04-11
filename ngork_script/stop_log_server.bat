@echo off
echo Stopping ngrok and Python HTTP server on port 8081...

REM Kill ngrok
taskkill /f /im ngrok.exe > NUL 2>&1

REM Kill Python HTTP server running with "http.server 8081"
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*http.server*8081*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

echo Done.
