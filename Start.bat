@echo off
rem Double-click to start local-proton-mail. Opens http://127.0.0.1:7861 in your browser.
rem Close this window to stop it. Agents can use "pmail start" / "pmail stop" instead.
call "%~dp0pmail.cmd" serve
pause
