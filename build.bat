@echo off
rem Build to a temp output first so a broken build never overwrites the working compiler,
rem and so nova.exe is never asked to overwrite its own file while it is still running
rem (both of which the old move/copy/del dance here used to risk). Mirrors build.sh.
echo Building nova using self-hosted compiler...
.\nova.exe build nova.nv -o nova_new.exe
if %ERRORLEVEL% equ 0 (
    move /y nova_new.exe nova.exe >nul
    echo Build successful!
) else (
    del nova_new.exe >nul 2>nul
    echo Build failed! Existing nova.exe left untouched.
    exit /b 1
)
