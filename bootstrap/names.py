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
        "makeDir": "fs_mkdir", "delete": "fs_delete", "copy": "fs_copy",
        "move": "fs_move", "read": "fs_read", "write": "fs_write",
    },
    "path": {
        "join": "path_join", "base": "path_basename",
        "dir": "path_dirname", "ext": "path_extension",
    },
    "env": {"get": "env_get", "set": "env_set", "args": "env_args", "platform": "env_platform"},
    "process": {"run": "process_run", "shell": "process_shell", "exit": "process_exit"},
    "time": {"now": "time_now", "ticks": "time_ticks_ms"},
    "json": {
        "stringify": "json_stringify", "parse": "json_parse", "kind": "json_kind",
        "asInt": "json_as_int", "asString": "json_as_string", "asBool": "json_as_bool",
        "size": "json_size", "at": "json_at", "get": "json_get", "has": "json_has",
        "keyAt": "json_key_at",
    },
    "text": {
        "toInt": "text_to_int", "trim": "text_trim", "startsWith": "text_starts_with",
        "endsWith": "text_ends_with", "indexOf": "text_index_of", "contains": "text_contains",
        "replace": "text_replace", "split": "text_split", "join": "text_join",
        "repeat": "text_repeat", "upper": "text_upper", "lower": "text_lower",
        "words": "text_words", "lines": "text_lines", "padLeft": "text_pad_left",
        "padRight": "text_pad_right", "count": "text_count", "capitalize": "text_capitalize",
    },
}

# camelCase member (method or pointer suffix) -> internal snake_case name
MEMBER_ALIASES = {
    "asList": "as_list",
    "valueByte": "value_byte",
    "valueWord": "value_word",
    "valueDword": "value_dword",
    "valueQword": "value_qword",
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


def is_public_module(name):
    return name in MODULE_FUNCS
