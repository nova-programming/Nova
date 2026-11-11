# Nova Bare-Metal 64-bit Operating System Kernel

This example demonstrates a complete, bootable 64-bit operating system kernel written in **100% Pure Nova** with **zero inline assembly** in user code.

---

## 1. What This Kernel Does
1. **CPU Privileges**: Runs in CPU Ring 0 64-bit Long Mode.
2. **Interrupt Control**: Disables interrupts during startup (`cpu.cli()`) and re-enables them for the idle loop (`cpu.sti()`).
3. **VGA Graphics & Console**: Uses hardware memory access (`poke.u16`) to directly clear and render colorful text and boxes to VGA video buffer `0xB8000`.
4. **Serial I/O Driver**: Uses CPU port intrinsics (`cpu.outb` and `cpu.inb`) to initialize COM1 UART (`0x3F8`) and stream kernel logs to the serial console.
5. **Power-Efficient Idle**: Enters a CPU halt loop (`cpu.hlt()`) waiting for hardware timer interrupts without spinning or burning power.

---

## 2. Kernel Code Highlight (`kernel.nv`)
```nova
# No assembly required! Pure, clean Nova code.

def kmain() {
    # 1. Disable hardware interrupts during setup
    cpu.cli()

    # 2. Initialize COM1 serial port at 0x3F8
    serial_init()
    serial_print("[NOVA-OS] Booting Nova Bare-Metal Kernel...\r\n")

    # 3. Write directly to VGA display memory at 0xB8000
    vga_clear(0x1F) # Blue background, white text
    vga_print(24, 5, "|       NOVA OPERATING SYSTEM    |", 0x1F)
    vga_print(24, 6, "|     Pure Native 64-bit Kernel  |", 0x1A)

    # 4. Idle loop - halt CPU until interrupt wakes it up
    cpu.sti()
    while 1 == 1 {
        cpu.hlt()
    }
}
```

---

## 3. How to Build & Run in QEMU
Run the automated PowerShell build script:
```powershell
.\build.ps1
```

Or run directly in QEMU:
```bash
qemu-system-x86_64 -kernel kernel.elf -serial stdio
```

