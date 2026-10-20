# Nova benchmark suite

Measures native codegen quality in isolation (pure execution time, build time excluded),
separately from `tests/benchmark_overall.py`, which times build+run together to compare
Nova against Python/C at a system level.

## Running

```bash
python benches/run_benchmarks.py                       # run, print a table
python benches/run_benchmarks.py --save baseline.json  # run, print, and save
python benches/run_benchmarks.py --compare baseline.json  # run, print, and diff
python benches/run_benchmarks.py fib_recursive.nv      # run just one benchmark
```

`baseline.json` in this directory is the committed baseline — compare against it after a
codegen change with `--compare benches/baseline.json`, and re-save it (`--save`) once a
change is confirmed to be a real improvement worth taking as the new baseline.

## Benchmarks

| File | Exercises |
|---|---|
| `fib_recursive.nv` | Function-call overhead (prologue/epilogue, stack frames) via deep recursion |
| `tight_loop_arith.nv` | Control case: few variables, already fits in available registers |
| `register_pressure.nv` | Many variables where only a few (declared late) are actually hot in a loop — exposes a declaration-order register allocator picking the wrong variables to keep in registers |
| `list_ops.nv` | List append/index — the list header + separately malloc'd, independently resized data array |
| `dict_ops.nv` | Dict set/get — hashing, open-addressing probes, and the resize path |
| `string_building.nv` | Repeated string concatenation — ARC alloc/free churn, and the O(n) copy cost of each `+` |

Each run builds the program once (excluded from timing), discards one warm-up execution
(a freshly-written `.exe`'s first run is dominated by OS-level overhead, e.g. antivirus
scanning the new file, unrelated to codegen quality), then times 5 more runs and reports
the median. A VM run is included for context where it finishes within `VM_TIMEOUT` seconds;
it's expected to be skipped for the heavier native-focused benchmarks, since VM interpretation
is orders of magnitude slower than native execution for tight loops.
