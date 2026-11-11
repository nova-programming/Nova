# Build Script for Nova Bare-Metal Kernel
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptDir

$gcc = "$env:LOCALAPPDATA\nova\gcc\bin\gcc.exe"
if (-not (Test-Path $gcc)) {
    $gcc = "gcc"
}

Write-Host ">> Compiling boot.s Multiboot trampoline..." -ForegroundColor Cyan
& $gcc -c boot.s -o boot.o -m64

Write-Host ">> Compiling Nova kernel.nv with Nova compiler..." -ForegroundColor Cyan
$novaExe = Resolve-Path "..\..\nova.exe"
& $novaExe build kernel.nv --os bare -o kernel_stage.exe

Write-Host ">> Assembling kernel assembly..." -ForegroundColor Cyan
& $gcc -c kernel.nv.s -o kernel.o -m64 -ffreestanding -mno-red-zone

Write-Host ">> Linking kernel.elf with linker.ld..." -ForegroundColor Cyan
& $gcc -nostdlib "-Wl,-T,linker.ld" boot.o kernel.o -o kernel.elf

Write-Host ">> Extracting flat raw binary kernel.bin..." -ForegroundColor Cyan
$objcopy = "$env:LOCALAPPDATA\nova\gcc\bin\objcopy.exe"
if (Test-Path $objcopy) {
    & $objcopy -O binary kernel.elf kernel.bin
    Write-Host "Successfully generated kernel.bin (Flat Binary)!" -ForegroundColor Green
}

Write-Host "Successfully generated kernel.elf (Multiboot ELF)!" -ForegroundColor Green
Write-Host "To test in QEMU, run:" -ForegroundColor Yellow
Write-Host "  qemu-system-x86_64 -kernel kernel.elf -serial stdio" -ForegroundColor White