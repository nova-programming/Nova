/* =============================================================================
   Nova Style Sheet (NSS) — Live Text Input & Display Demo
   Catppuccin Mocha themed stylesheet for examples/gui_input_demo.nv
   ============================================================================= */

#window {
    bg: #181825;
}

.app-root {
    bg: #181825;
    p: 24;
    gap: 14;
}

/* ── Header ───────────────────────────────────────────────────────────────── */
.header-row {
    align: center;
    gap: 12;
}

.brand-badge {
    bg: #313244;
    color: #cba6f7;
    r: 10;
    px: 8;
    py: 3;
    bold;
    size: 11;
}

.app-title {
    color: #cdd6f4;
    size: 20;
    bold;
}

.badge-live {
    bg: #1e2e3e;
    color: #89b4fa;
    r: 10;
    px: 8;
    py: 3;
    bold;
    size: 11;
}

.divider {
    bg: #313244;
    h: 1;
}

/* ── Input Card Section ───────────────────────────────────────────────────── */
.card-section {
    bg: #1e1e2e;
    border: 1;
    border_color: #313244;
    r: 8;
    p: 16;
    gap: 10;
}

.section-label {
    color: #89b4fa;
    size: 11;
    bold;
}

.section-title {
    color: #ffffff;
    size: 15;
    bold;
}

.section-description {
    color: #a6adc8;
    size: 12;
}

.text-input {
    w: 440;
    h: 42;
    bg: #181825;
    border: 1;
    border_color: #45475a;
    focus-border-color: #89b4fa;
    color: #6c7086;
    text-color: #cdd6f4;
    size: 14;
    r: 4;
    px: 12;
    py: 8;
}

.button-row {
    align: center;
    gap: 8;
}

.btn-primary {
    w: 180;
    h: 42;
    bg: #89b4fa;
    color: #11111b;
    size: 14;
    bold;
    r: 4;
}

.btn-primary:hover {
    bg: #b4befe;
}

.btn-primary:active {
    bg: #74c7ec;
}

.btn-secondary {
    w: 130;
    h: 42;
    bg: #313244;
    color: #cdd6f4;
    size: 13;
    r: 4;
}

.btn-secondary:hover {
    bg: #45475a;
}

.btn-secondary:active {
    bg: #181825;
}

/* ── UI Screen Monitor Card ──────────────────────────────────────────────── */
.monitor-badge {
    bg: #1e2e28;
    color: #a6e3a1;
    r: 10;
    px: 8;
    py: 3;
    bold;
    size: 11;
}

.monitor-status {
    color: #6c7086;
    size: 11;
}

.monitor-box {
    bg: #11111b;
    border: 1;
    border_color: #313244;
    r: 6;
    p: 16;
}

.monitor-text {
    color: #a6e3a1;
    size: 16;
    bold;
}
