"""Can the repair pass ever make an answer worse, on pools the fixture set does not contain?

The 42 checked-in fixtures are one seed per family/size pair. A previous change in this stack was
reviewed and found to regress thousands of randomly generated pools that the fixture set could not
see, so "it improves 10 of 52 and worsens none" is not on its own an answer.

This regenerates each family at each small size under many *different* seeds, runs the pinned runner
with the repair pass off and on under a fixed round budget, and reports any pool where turning it on
cost fee. Every fixture is also handed to the harness's own verifier, so a repaired selection that
does not actually fund its package is caught rather than scored.

Usage: python3 tools/randomsweep.py [draws per family/size] [sizes...]
"""
import json, pathlib, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import bench, genfixtures

CS = "rust-runner/target/release/coinselect-bench-runner"

draws = int(sys.argv[1]) if len(sys.argv) > 1 else 25
sizes = [int(a) for a in sys.argv[2:]] or [20, 50, 100, 200]

# Ancestry families only: with nothing shared the pass returns immediately, which the crate tests
# already cover. These are the shapes where it actually runs.
families = [f for f in genfixtures.FAMILIES if "ancestry" in f or "shared" in f or "mixed" in f]

original = genfixtures.seed_for
tmp = pathlib.Path(tempfile.mkdtemp(prefix="randomsweep-"))
regressions, ran, skipped, invalid = [], 0, 0, []

for family in families:
    for size in sizes:
        for draw in range(draws):
            genfixtures.seed_for = lambda f, n, _d=draw: (original(f, n) ^ (_d * 2654435761)) & 0xFFFFFFFF
            try:
                fixture = genfixtures.build(family, size)
            except Exception:
                skipped += 1
                continue
            path = tmp / f"{family}_{size}_{draw}.json"
            path.write_text(json.dumps(fixture))
            loaded = bench.load_fixture(str(path))

            fees = []
            for repair in ("0", "1000"):
                proc = subprocess.run(
                    # A *round* budget, not a wall-clock one. Under a deadline the round count
                    # varies with background load, so the two arms search different amounts and
                    # the comparison measures the scheduler: a first version of this reported five
                    # regressions in 700 pools, all five of which vanished here, including one on
                    # a fixture with no shared ancestors at all, where the pass returns immediately.
                    [CS, "--fixture", str(path), "--track", "wallet", "--repeat", "1",
                     "--warmup", "0", "--budget", "100000", "--repair", repair],
                    capture_output=True, text=True)
                if proc.returncode:
                    raise SystemExit(f"{path}\n{proc.stderr[-1500:]}")
                raw = json.loads(proc.stdout)
                if not raw.get("selected"):
                    fees.append(None)
                    continue
                metrics = bench.evaluate(loaded, raw["selected"], bench.change_value_of(raw))
                if repair == "1000" and not (metrics["package_meets_target"]
                                             and metrics["covers_union_bump"]
                                             and metrics["within_max_weight"]):
                    invalid.append(str(path))
                fees.append(metrics["package_fee"])

            off, on = fees
            if off is None or on is None:
                if off is None and on is not None:
                    regressions.append((family, size, draw, "no solution", on))
                skipped += 1
                continue
            ran += 1
            if on > off:
                regressions.append((family, size, draw, off, on))

genfixtures.seed_for = original
print(f"\n{ran} pools compared across {len(families)} families and {len(sizes)} sizes "
      f"({skipped} skipped, could not be generated or funded)")
print(f"selections the repair returned that fail verification: {len(invalid)}")
print(f"pools where turning the repair on cost fee: {len(regressions)}")
for family, size, draw, off, on in regressions:
    print(f"  {family}_{size} draw {draw}: {off} -> {on}")
