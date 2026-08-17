"""Why does one engine win a scale-tier fixture? Decompose the fee difference.

At 20,000 candidates the two engines land within a fraction of a percent of each other, so the
interesting question stops being "who wins" and becomes "what is the win made of". This splits the
package-fee gap into the three things that can produce it: how many inputs were taken, how much
child weight they cost, and how much unconfirmed-ancestor bumping they dragged in.

Usage: python3 tools/whyscale.py [fixture ...]   (default: every fixture in fixtures/scale/)
"""
import glob, json, pathlib, subprocess, sys

sys.path.insert(0, "/home/evanlinjin/Git/coinselect-benchmark")
import bench

CS = "rust-runner/target/release/coinselect-bench-runner"
CORE = ".build/core-runner/core-runner"
DEADLINE = "100000"


def run(binary, path, extra=()):
    out = subprocess.run([binary, "--fixture", path, "--track", "wallet", "--repeat", "1",
                          "--warmup", "0", "--deadline-us", DEADLINE, *extra],
                         capture_output=True, text=True)
    if out.returncode:
        raise SystemExit(f"{path}\n{out.stderr[-1200:]}")
    return json.loads(out.stdout)


def describe(path):
    name = pathlib.Path(path).stem
    fixture = bench.load_fixture(path)
    by_id = fixture["_by_id"]

    arms = {}
    for label, binary, extra in (("coin-select", CS, ["--budget", "4000000000"]),
                                 ("bitcoin-core", CORE, [])):
        raw = run(binary, path, extra)
        if not raw["selected"]:
            print(f"{name}: {label} returned no solution")
            return
        metrics = bench.evaluate(fixture, raw["selected"], bench.change_value_of(raw))
        arms[label] = dict(
            raw=raw, m=metrics,
            parentless=sum(1 for i in raw["selected"] if not by_id[i]["residing_txid"]),
        )

    a, b = arms["coin-select"], arms["bitcoin-core"]
    gap = a["m"]["package_fee"] - b["m"]["package_fee"]
    verdict = "coin-select" if gap < 0 else ("tie" if gap == 0 else "BITCOIN CORE")
    print(f"\n=== {name}  ({len(fixture['candidates']):,} candidates)   winner: {verdict}"
          f"   gap {abs(gap):,} sat ({abs(gap) * 100 / min(a['m']['package_fee'], b['m']['package_fee']):.2f}%)")
    rows = [
        ("inputs", "n_inputs"),
        ("child weight", "child_weight"),
        ("parents dragged in", "ancestors_in_union"),
        ("ancestor bump", "union_bump"),
        ("child fee", "child_fee"),
        ("package fee", "package_fee"),
    ]
    print(f"  {'':22s} {'coin-select':>14} {'bitcoin-core':>14} {'difference':>14}")
    for label, key in rows:
        x, y = a["m"][key], b["m"][key]
        print(f"  {label:22s} {x:>14,} {y:>14,} {x - y:>+14,}")
    print(f"  {'inputs with no parent':22s} {a['parentless']:>14,} {b['parentless']:>14,} "
          f"{a['parentless'] - b['parentless']:>+14,}")

    # What share of the gap is ancestry rather than the transaction itself?
    bump_delta = a["m"]["union_bump"] - b["m"]["union_bump"]
    if gap:
        print(f"  -> the ancestor bump accounts for {bump_delta * 100 / gap:.0f}% of the gap")

    # Did the search contribute anything, or is this the greedy seed?
    probe = run(CS, path, ["--budget", "4000000000", "--seed-probe"])
    seed = probe.get("lowest_fee_seed_score")
    got = (a["raw"].get("native") or {}).get("score")
    print(f"  -> coin-select ran {a['raw']['rounds']:,} rounds; its answer is "
          f"{'the greedy seed, unimproved' if seed == got else f'an improvement on the seed ({seed} -> {got})'}")


for target in (sys.argv[1:] or sorted(glob.glob("fixtures/scale/*.json"))):
    describe(target if target.endswith(".json") else f"fixtures/scale/{target}.json")
