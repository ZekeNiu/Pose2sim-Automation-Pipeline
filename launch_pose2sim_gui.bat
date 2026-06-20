@echo off
setlocal
set "ROOT=%~dp0"
set "PYTHON=D:\Application\Anaconda\envs\sports3d\python.exe"
if not exist "%PYTHON%" (
  echo Could not find Python: %PYTHON%
  pause
  exit /b 1
)
cd /d "%ROOT%"
"%PYTHON%" -m pose2sim_pipeline_gui
if errorlevel 1 pause

