@echo off
REM ProteoLens launcher -- double-click this file, or run `start.cmd` from a terminal.
REM
REM Starts the API and the web app in production mode and opens a browser.
REM Production mode is intentional: `next dev` paints a floating dev-tools
REM bubble over every page, and `next start` does not.
REM
REM Pass -Rebuild to force a fresh frontend build after changing source:
REM     start.cmd -Rebuild

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch.ps1" %*

REM Keep the window open if launched by double-click and something failed.
if errorlevel 1 (
  echo.
  pause
)
