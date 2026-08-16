"""The goal's scoreboard: does coin-select beat Core on fee, on work, and on wall clock, everywhere?

Usage: scoreboard.py [--runner PATH] [--label NAME] [extra runner args...]

Runs both engines on all 42 fixtures and scores three verdicts per fixture:

  fee    package fee, from the harness's shared model, lower wins
  work   rounds spent to *find* the returned answer (`best_round`) against Core's node count.
         Different units — Core counts depth-first nodes, coin-select counts iterator rounds —
         so this is a rough comparison and is labelled as one.
  time   median wall clock over the timed region only.
"""
import json, subprocess, sys, glob, pathlib, statistics
sys.path.insert(0, "/home/evanlinjin/Git/coinselect-benchmark")
import bench

CORE = ".build/core-runner/core-runner"
CS = "rust-runner/target/release/coinselect-bench-runner"

argv = sys.argv[1:]
runner, label, extra = CS, "coin-select", []
while argv:
    if argv[0] == "--runner":
        runner = argv[1]; argv = argv[2:]
    elif argv[0] == "--label":
        label = argv[1]; argv = argv[2:]
    else:
        extra = argv; break


def run(binary, fx, args):
    o = subprocess.run([binary, "--fixture", fx, "--track", "wallet",
                        "--repeat", "5", "--warmup", "2"] + args, capture_output=True, text=True)
    if o.returncode:
        raise SystemExit(f"{fx} {binary}\n{o.stderr[-1500:]}")
    return json.loads(o.stdout)


rows = []
for fx in sorted(glob.glob("fixtures/*.json")):
    name = pathlib.Path(fx).stem
    f = bench.load_fixture(fx)
    a = run(runner, fx, extra)
    b = run(CORE, fx, [])
    ma = bench.evaluate(f, a["selected"], bench.change_value_of(a)) if a["selected"] else None
    mb = bench.evaluate(f, b["selected"], bench.change_value_of(b)) if b["selected"] else None
    rows.append(dict(
        name=name, n=len(f["candidates"]),
        fee_a=ma and ma["package_fee"], fee_b=mb and mb["package_fee"],
        work_a=a.get("best_round", a["rounds"]), work_b=b["rounds"],
        rounds_a=a["rounds"], exh_a=a["exhausted"],
        ms_a=a["timing"]["wall_ns_median"] / 1e6, ms_b=b["timing"]["wall_ns_median"] / 1e6,
        found_ms=a.get("best_ns", 0) / 1e6,
        oracle=a.get("oracle", {}),
    ))

W = max(len(r["name"]) for r in rows)
print(f"\n### {label} vs bitcoin-core, 42 fixtures, 100,000-round budget\n")
print(f"{'fixture':{W}s} {'n':>5} | {'pkg fee':>9} {'core':>9} {'':2} | "
      f"{'found@':>8} {'core':>8} {'':2} | {'found ms':>9} {'ran ms':>9} {'core ms':>9} {'':2}{'':2} | done")
print("-" * (W + 90))
lost = {"fee": [], "work": [], "found": [], "ran": []}
for r in rows:
    fee_ok = r["fee_a"] is not None and (r["fee_b"] is None or r["fee_a"] < r["fee_b"])
    work_ok = r["work_b"] is None or r["work_a"] < r["work_b"]
    found_ok = r["found_ms"] < r["ms_b"]
    ran_ok = r["ms_a"] < r["ms_b"]
    for k, ok in (("fee", fee_ok), ("work", work_ok), ("found", found_ok), ("ran", ran_ok)):
        if not ok:
            lost[k].append(r["name"])
    m = lambda ok: "OK" if ok else ".."
    wb = "-" if r["work_b"] is None else f"{r['work_b']:,}"
    print(f"{r['name']:{W}s} {r['n']:5,} | {r['fee_a']:>9,} {r['fee_b']:>9,} {m(fee_ok):2} | "
          f"{r['work_a']:>8,} {wb:>8} {m(work_ok):2} | {r['found_ms']:>9.2f} {r['ms_a']:>9.2f} "
          f"{r['ms_b']:>9.2f} {m(found_ok):2}{m(ran_ok):2} | {'yes' if r['exh_a'] else 'BUDGET'}")

n = len(rows)
print(f"\n{'axis':6s} {'won':>8}   fixtures still lost")
for k in ("fee", "work", "found", "ran"):
    names = lost[k]
    print(f"{k:6s} {n - len(names):>3} of {n}   {', '.join(names) if names else '— clean sweep —'}")
budget = [r["name"] for r in rows if not r["exh_a"]]
print(f"\nhit the round budget: {len(budget)} of {n}  {', '.join(budget)}")
missed = [r["name"] for r in rows if r["oracle"].get("ran") and r["oracle"].get("matches") is False]
json.dump(rows, open("/home/evanlinjin/.claude/jobs/cbe24b0f/tmp/scoreboard.json", "w"), indent=1)
