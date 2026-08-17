"""Does the in-crate repair pass — hill-climbing on the metric's own score — beat Core?

`tools/repair.py` answered the same question in Python against the *harness's* package fee, which
is what both engines are scored on but not what `LowestFee` minimises: the metric also charges for
spending the change output later. This drives the real thing, `--repair` in the runner, so the
climb happens on the score the crate would actually use.

Usage: python3 tools/repairbench.py [swap budget] [fixture ...]
"""
import json, pathlib, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import bench

CS = "rust-runner/target/release/coinselect-bench-runner"
CORE = ".build/core-runner/core-runner"
DEADLINE = "100000"


def run(binary, path, extra=()):
    out = subprocess.run([binary, "--fixture", path, "--track", "wallet", "--repeat", "1",
                          "--warmup", "0", "--deadline-us", DEADLINE, *extra],
                         capture_output=True, text=True)
    if out.returncode:
        raise SystemExit(f"{path}\n{out.stderr[-2000:]}")
    return json.loads(out.stdout), out.stderr


def fee(fixture, raw):
    return bench.evaluate(fixture, raw["selected"], bench.change_value_of(raw))["package_fee"]


budget = sys.argv[1] if len(sys.argv) > 1 else "4000"
names = sys.argv[2:] or ["shared_ancestry_20000", "nested_ancestry_20000", "shared_ancestry_200000",
                         "private_ancestry_20000", "subsidizing_ancestry_20000",
                         "adversarial_shared_20000", "wallet_mixed_20000"]

print(f"swap budget {budget}, {DEADLINE} us search deadline\n")
print(f"{'fixture':30s} {'core':>11} {'coin-select':>12} {'+repair':>12} {'change':>8}  verdict")
for name in names:
    path = f"fixtures/scale/{name}.json"
    fixture = bench.load_fixture(path)
    core, _ = run(CORE, path)
    # `--repair` now defaults to what `run_bnb` gives it, so the baseline has to ask for zero.
    plain, _ = run(CS, path, ["--budget", "4000000000", "--repair", "0"])
    fixed, log = run(CS, path, ["--budget", "4000000000", "--repair", budget])
    c, a, b = fee(fixture, core), fee(fixture, plain), fee(fixture, fixed)
    swaps = log.strip().splitlines()[-1] if "repair:" in log else "no swap taken"
    verdict = "BEATS CORE" if b < c else ("tie" if b == c else f"short by {b - c:,}")
    print(f"{name:30s} {c:>11,} {a:>12,} {b:>12,} {100 * (b - a) / a:>7.2f}%  {verdict}   [{swaps}]")
