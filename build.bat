@echo off
echo Building nova using self-hosted compiler...
.\nova.exe build nova.nv
if %ERRORLEVEL% equ 0 (
    echo Moving new compiler...
    move /y nova.exe nova_new.exe >nul
    copy /y nova_new.exe nova.exe >nul
    del nova_new.exe
    echo Build successful!
) else (
    echo Build failed!
)
