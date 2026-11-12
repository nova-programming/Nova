"""Public API names for Nova (single source of truth for the Python pipeline).

New code uses module-qualified calls (``import fs`` then ``fs.read(p)``) and
camelCase member names. Every form rewrites at parse time to the existing flat
function names, so the runtime, VM and code generators are unchanged and the
old spellings (``fs_read``, ``value_byte``, ``as_list``) keep working.

The self-hosted pipeline mirrors this table in stdlib/names.nv; tests/test_names.py
checks that both stay in sync.
"""

# module -> {public member -> internal flat function name}
MODULE_FUNCS = {
    "fs": {
        "exists": "fs_exists", "size": "fs_size", "kind": "fs_kind",
        "makeDir": "fs_makeDir", "mkdir": "fs_makeDir", "delete": "fs_delete",
        "copy": "fs_copy", "move": "fs_move", "read": "fs_read",
        "write": "fs_write", "writeAtomic": "fs_writeAtomic",
        "listDir": "fs_listDir",
    },
    "path": {
        "join": "path_join", "base": "path_base", "basename": "path_base",
        "dir": "path_dir", "dirname": "path_dir", "ext": "path_ext",
        "extension": "path_ext", "normalize": "path_normalize",
        "isAbsolute": "path_isAbsolute", "toForward": "path_toForward",
    },
    "env": {"get": "env_get", "set": "env_set", "args": "env_args", "platform": "env_platform"},
    "process": {"run": "process_run", "shell": "process_shell", "exit": "process_exit", "capture": "process_capture", "captureOutput": "process_captureOutput", "captureCode": "process_captureCode"},
    "time": {"now": "time_now", "ticks": "time_ticks", "nowUs": "time_nowUs", "nowMs": "time_nowMs", "sleep": "time_sleep"},
    "json": {
        "stringify": "json_stringify", "parse": "json_parse", "kind": "json_kind",
        "asInt": "json_asInt", "as_int": "json_asInt",
        "asString": "json_asString", "as_string": "json_asString",
        "asBool": "json_asBool", "as_bool": "json_asBool",
        "size": "json_size", "at": "json_at", "get": "json_get", "has": "json_has",
        "keyAt": "json_keyAt", "key_at": "json_keyAt",
    },
    "text": {
        "toInt": "text_toInt", "to_int": "text_toInt",
        "trim": "text_trim",
        "startsWith": "text_startsWith", "starts_with": "text_startsWith",
        "endsWith": "text_endsWith", "ends_with": "text_endsWith",
        "indexOf": "text_indexOf", "index_of": "text_indexOf",
        "contains": "text_contains",
        "replace": "text_replace", "split": "text_split", "join": "text_join",
        "repeat": "text_repeat", "upper": "text_upper", "lower": "text_lower",
        "words": "text_words", "lines": "text_lines",
        "padLeft": "text_padLeft", "pad_left": "text_padLeft",
        "padRight": "text_padRight", "pad_right": "text_padRight",
        "count": "text_count", "capitalize": "text_capitalize",
        "slice": "text_slice",
    },
    "ui": {
        "open": "ui_open", "close": "ui_close", "wait": "wait",
        "window": "window", "quit": "quit",
        "frame": "frame", "endFrame": "endFrame",
        "begin": "begin", "end": "end",
        "poll": "poll", "hit": "hit", "clicked": "clicked",
        "clear": "clear", "rect": "rect", "group": "group",
        "card": "card", "endCard": "endCard",
        "text": "text", "textCenter": "textCenter", "textRight": "textRight",
        "badge": "badge",
        "button": "button", "meter": "meter",
        "divider": "divider", "stack": "stack", "endStack": "endStack", "next": "next",
        "row": "row", "endRow": "endRow", "colX": "colX", "colW": "colW",
        "stackX": "stackX", "stackW": "stackW",
        "width": "width", "height": "height",
        "padding": "padding", "gap": "gap", "buttonHeight": "buttonHeight",
        "setPadding": "setPadding", "setGap": "setGap",
        "setRadius": "setRadius", "setButtonHeight": "setButtonHeight",
        "theme": "theme",
        "eventX": "eventX", "eventY": "eventY", "eventKey": "eventKey",
        "left": "left", "center": "center", "right": "right",
        "rgb": "rgb",
    },
    "audio": {
        "beep": "audio_beep", "click": "audio_click",
        "success": "audio_success", "error": "audio_error",
        "playNote": "audio_playNote", "play_note": "audio_playNote",
        "sampleSine": "audio_sampleSine", "sample_sine": "audio_sampleSine",
        "sampleSquare": "audio_sampleSquare", "sample_square": "audio_sampleSquare",
        "sampleTriangle": "audio_sampleTriangle", "sample_triangle": "audio_sampleTriangle",
        "sampleNoise": "audio_sampleNoise", "sample_noise": "audio_sampleNoise",
    },
    "net": {
        "init": "net_init", "listen": "net_listen",
        "connect": "net_connect", "setTimeout": "net_setTimeout",
    },
    "buffer": {
        "alloc": "buffer_alloc", "new": "buffer_alloc",
    },
}

# camelCase member (method or pointer suffix) -> internal snake_case name
MEMBER_ALIASES = {
    "asList": "as_list",
    "valueByte": "value_byte",
    "valueWord": "value_word",
    "valueDword": "value_dword",
    "valueQword": "value_qword",
    "getU8": "get_u8",
    "setU8": "set_u8",
    "getU16": "get_u16",
    "setU16": "set_u16",
    "getI32": "get_i32",
    "setI32": "set_i32",
    "copyFrom": "copy_from",
    "fillI32": "fill_i32",
}


def canonical_member(name):
    return MEMBER_ALIASES.get(name, name)


def module_function(module, member):
    """Internal function name for ``module.member`` or None if unknown."""
    return MODULE_FUNCS.get(module, {}).get(member)


def suggest(module, member):
    """Closest public member of module, for error messages."""
    import difflib
    close = difflib.get_close_matches(member, list(MODULE_FUNCS.get(module, {})), n=1)
    return close[0] if close else None


MODULE_CONSTS = {
    "align": {"left": 0, "center": 1, "right": 2, "top": 0, "middle": 1, "bottom": 2},
    "size": {"fit": -1, "fill": -2},
    "style": {"plain": 0, "hover": 1, "primary": 2},
    "ui": {
        "left": 0, "center": 1, "right": 2,
        "top": 0, "middle": 1, "bottom": 2,
        "plain": 0, "hover": 1, "primary": 2,
        "default": 0, "text": 1, "secondary": 2, "muted": 3,
        "accent": 4, "ok": 5, "warn": 6, "err": 7,
        "fit": -1, "fill": -2,
    },
}

def is_public_const(module, name):
    return module in MODULE_CONSTS and name in MODULE_CONSTS[module]

def module_const(module, name):
    return MODULE_CONSTS.get(module, {}).get(name)

def is_public_module(name):
    return name in MODULE_FUNCS or name in MODULE_CONSTS
