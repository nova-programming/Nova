# Shared Value ABI

Nova currently passes immediate integers and booleans as machine values, while
strings, lists, and dictionaries use pointers. The first shared-ABI milestone
defines stable kind identifiers without changing those existing calling
conventions:

| Kind | ID | Current representation |
|---|---:|---|
| `none` | 0 | VM sentinel; native representation pending |
| `list` | 1 | ARC-managed list pointer |
| `dict` | 2 | ARC-managed dictionary pointer |
| `string` | 3 | ARC-managed/string pointer |
| `bool` | 4 | Immediate VM/native value; boxing pending |
| `int` | 5 | Immediate VM/native value; boxing pending |
| `float` | 6 | Immediate VM/native value; boxing pending |

The native runtime exposes `_nova_value_kind(pointer)` as an internal ABI
probe, along with scalar boxing/accessor helpers:

- `_value_box_none()`
- `_value_box_bool(value)` / `_value_unbox_bool(pointer)`
- `_value_box_int(value)` / `_value_unbox_int(pointer)`
- `_value_box_float(value)` / `_value_unbox_float(pointer)`
- `_value_box_string(value)` / `_value_unbox_string(pointer)`
- `_value_box_list(value)` / `_value_box_dict(value)`

The `value_box_*` and `value_unbox_*` names are the only public names for
these scalar and collection boxing helpers.

Collection traversal helpers validate the ARC kind before reading:
`_nova_value_list_count`, `_nova_value_list_item`, `_nova_value_dict_count`,
`_nova_value_dict_keys`, `_nova_value_dict_values`, and
`_nova_value_dict_items`. The item helper returns a flattened ordered
key/value list so recursive consumers preserve key/value pairing.

`_nova_value_retain` increments the ARC count for a managed collection or
string and returns the same pointer. `_nova_value_is_list`,
`_nova_value_is_dict`, and `_nova_value_is_string` provide checked kind
predicates.

`_nova_value_release` is the matching decrement operation for temporary
references acquired through `_nova_value_retain`. VM release is intentionally
a no-op because VM values are managed by the Python object lifetime.

Invalid accessor kinds return a zero value. `_nova_value_kind(pointer)` returns
the kind for an ARC-managed pointer and `0` for null, non-managed pointers,
or the current unboxed scalar representations.

This is deliberately additive. Existing programs continue to use the current
ABI while later milestones add boxed scalar constructors and recursive
VM/native JSON conversion. The first JSON milestone adds native/VM
`json_stringify`; boxed scalar values preserve types that native immediate
values cannot carry by themselves.
