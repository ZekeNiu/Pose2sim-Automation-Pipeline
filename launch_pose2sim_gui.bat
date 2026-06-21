@echo off
setlocal
set "ROOT=%~dp0"
if not defined POSE2SIM_GUI_PYTHON (
  set "POSE2SIM_GUI_PYTHON=D:\Application\Anaconda\envs\sports3d\python.exe"
)
set "PYTHON=%POSE2SIM_GUI_PYTHON%"
if not exist "%PYTHON%" (
  echo Could not find Python: %PYTHON%
  echo You can set POSE2SIM_GUI_PYTHON to another python.exe before launching.
  pause
  exit /b 1
)
cd /d "%ROOT%"
"%PYTHON%" -m pose2sim_pipeline_gui
if errorlevel 1 pause
