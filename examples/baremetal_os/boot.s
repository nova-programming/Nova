/* Multiboot 1 Trampoline: 32-bit Protected Mode -> 64-bit Long Mode -> kmain */
.set ALIGN,    1<<0
.set MEMINFO,  1<<1
.set FLAGS,    ALIGN | MEMINFO
.set MAGIC,    0x1BADB002
.set CHECKSUM, -(MAGIC + FLAGS)

.section .multiboot
.align 4
.long MAGIC
.long FLAGS
.long CHECKSUM

.section .bss
.align 4096
pml4:
    .skip 4096
pdpt:
    .skip 4096
pdt:
    .skip 4096
stack_bottom:
    .skip 16384
stack_top:

.section .rodata
gdt64:
    .quad 0                          /* Null descriptor */
gdt64_code:
    .quad (1<<43) | (1<<44) | (1<<47) | (1<<53) /* 64-bit code segment */
gdt64_pointer:
    .word . - gdt64 - 1
    .quad gdt64

.section .text
.code32
.global _start
_start:
    mov $stack_top, %esp

    /* 1. Identity map the first 1GB using 2MB huge pages */
    /* pml4[0] -> pdpt */
    mov $pdpt, %eax
    or $0x3, %eax                    /* present + writable */
    mov %eax, (pml4)

    /* pdpt[0] -> pdt */
    mov $pdt, %eax
    or $0x3, %eax
    mov %eax, (pdpt)

    /* Map first 512 entries of pdt with 2MB huge pages */
    mov $0, %ecx
1:
    mov %ecx, %eax
    shl $21, %eax
    or $0x83, %eax                   /* present + writable + 2MB huge */
    mov %eax, pdt(,%ecx,8)
    inc %ecx
    cmp $512, %ecx
    jne 1b

    /* 2. Enable PAE (Physical Address Extension) in CR4 */
    mov %cr4, %eax
    or $1<<5, %eax
    mov %eax, %cr4

    /* 3. Load CR3 with PML4 */
    mov $pml4, %eax
    mov %eax, %cr3

    /* 4. Enable Long Mode in EFER MSR (0xC0000080, bit 8) */
    mov $0xC0000080, %ecx
    rdmsr
    or $1<<8, %eax
    wrmsr

    /* 5. Enable Paging & Protected Mode in CR0 (bit 31 | bit 0) */
    mov %cr0, %eax
    or $(1<<31) | 1, %eax
    mov %eax, %cr0

    /* 6. Load 64-bit GDT and jump to 64-bit Long Mode */
    lgdt (gdt64_pointer)
    ljmp $0x08, $long_mode_start

.code64
.weak kmain
.weak _kmain
long_mode_start:
    mov $0, %ax
    mov %ax, %ss
    mov %ax, %ds
    mov %ax, %es
    mov %ax, %fs
    mov %ax, %gs
    mov $stack_top, %rsp

    /* Call Nova Kernel entry point */
    mov $kmain, %rax
    test %rax, %rax
    jnz 2f
    mov $_kmain, %rax
2:
    call *%rax

    /* Fallback halt loop */
halt_loop:
    hlt
    jmp halt_loop
