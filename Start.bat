@echo off
rem Double-click to start local-proton-mail. Opens http://127.0.0.1:7861 in your browser.
cd /d "%~dp0"
call :find_uv
if not defined UV (
  echo uv isn't installed. Install it from https://docs.astral.sh/uv/ and run this again.
  pause
  exit /b 1
)
"%UV%" sync --quiet
"%UV%" run python -m pmail serve
pause
exit /b

:find_uv
rem uv on PATH, or where its installers put it ("pip install --user uv" and the standalone installer).
for /f "delims=" %%U in ('where uv 2^>nul') do (set "UV=%%U" & exit /b)
for %%U in ("%USERPROFILE%\.local\bin\uv.exe" "%USERPROFILE%\.cargo\bin\uv.exe") do if exist %%U (set "UV=%%~U" & exit /b)
for /d %%D in ("%APPDATA%\Python\Python3*") do if exist "%%D\Scripts\uv.exe" (set "UV=%%D\Scripts\uv.exe" & exit /b)
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\Scripts\uv.exe" (set "UV=%%D\Scripts\uv.exe" & exit /b)
exit /b
