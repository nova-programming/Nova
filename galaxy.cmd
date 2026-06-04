@echo off
REM Galaxy Package Manager for Nova - Windows standalone entry
REM After 'python install.py', the 'galaxy' command is on PATH globally.
REM This wrapper runs directly from the source tree without installation.
python "%~dp0_galaxy.py" %*
