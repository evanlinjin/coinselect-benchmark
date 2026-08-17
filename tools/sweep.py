"""Package fee for every fixture at one budget, as JSON on stdout.

A comparison harness for questions of the form "does this crate change move any answer". Run it
against two builds and diff the two files; `bench.py report` is the full matrix and this is the one
column that settles most of these.

Usage: python3 tools/sweep.py OUT.json [--repair N] [--deadline-us N]
"""
import glob, json, pathlib, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import bench

CS = "rust-runner/target/release/coinselect-bench-runner"

out_path = sys.argv[1]
extra = sys.argv[2:]
deadline = "100000"
if "--deadline-us" in extra:
    deadline = extra[extra.index("--deadline-us") + 1]
    i = extra.index("--deadline-us")
    extra = extra[:i] + extra[i + 2:]

results = {}
for path in sorted(glob.glob("fixtures/*.json") + glob.glob("fixtures/scale/*.json")):
    if pathlib.Path(path).stem == "smoke":
        continue
    fixture = bench.load_fixture(path)
    proc = subprocess.run([CS, "--fixture", path, "--track", "wallet", "--repeat", "1",
                           "--warmup", "0", "--deadline-us", deadline,
                           "--budget", "4000000000", *extra],
                          capture_output=True, text=True)
    if proc.returncode:
        raise SystemExit(f"{path}\n{proc.stderr[-1500:]}")
    raw = json.loads(proc.stdout)
    name = pathlib.Path(path).stem
    results[name] = (bench.evaluate(fixture, raw["selected"], bench.change_value_of(raw))["package_fee"]
                     if raw.get("selected") else None)
    print(f"{name:30s} {results[name]}", file=sys.stderr)

pathlib.Path(out_path).write_text(json.dumps(results, indent=1))
print(f"wrote {out_path}: {len(results)} fixtures")
