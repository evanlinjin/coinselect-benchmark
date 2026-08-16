"""When does coin-select first hold an answer better than Core's finished one?

`ran` compares two searches given different budgets in different units, so it says as much about
budget policy as about the engines. This asks the question a wallet actually cares about: from a
standing start, how long until coin-select is ahead — and how long did Core need to get where it got?
"""
import json, subprocess, sys, glob, pathlib
sys.path.insert(0, "/home/evanlinjin/Git/coinselect-benchmark")
import bench

CORE = ".build/core-runner/core-runner"
RUNNERS = [(a.split("=", 1)[0], a.split("=", 1)[1]) for a in sys.argv[1:]]


def run(binary, fx, args=()):
    o = subprocess.run([binary, "--fixture", fx, "--track", "wallet", "--repeat", "5",
                        "--warmup", "2", *args], capture_output=True, text=True)
    if o.returncode:
        raise SystemExit(f"{fx}\n{o.stderr[-1200:]}")
    return json.loads(o.stdout)


rows = []
for fx in sorted(glob.glob("fixtures/*.json")):
    name = pathlib.Path(fx).stem
    f = bench.load_fixture(fx)
    core = run(CORE, fx)
    core_fee = bench.evaluate(f, core["selected"], bench.change_value_of(core))["package_fee"]
    core_ms = core["timing"]["wall_ns_median"] / 1e6
    row = {"name": name, "core_fee": core_fee, "core_ms": core_ms,
           "core_nodes": core["rounds"], "arms": {}}
    for label, binary in RUNNERS:
        r = run(binary, fx)
        beat_ms = beat_round = None
        for e in r.get("trajectory", []):
            if bench.evaluate(f, e["selected"], e["drain_value"])["package_fee"] < core_fee:
                beat_ms, beat_round = e["ns"] / 1e6, e["round"]
                break
        final = bench.evaluate(f, r["selected"], bench.change_value_of(r))["package_fee"]
        row["arms"][label] = {"beat_ms": beat_ms, "beat_round": beat_round, "fee": final}
    rows.append(row)

W = max(len(r["name"]) for r in rows)
labels = [l for l, _ in RUNNERS]
head = f"{'fixture':{W}s} {'core ms':>8} {'core fee':>9}"
for l in labels:
    head += f" | {l[:20]:>20}"
print(head)
print("-" * len(head))
won = {l: 0 for l in labels}
never = {l: [] for l in labels}
slower = {l: [] for l in labels}
for r in rows:
    line = f"{r['name']:{W}s} {r['core_ms']:8.2f} {r['core_fee']:9,}"
    for l in labels:
        a = r["arms"][l]
        if a["beat_ms"] is None:
            line += f" | {'never beats it':>20}"
            never[l].append(r["name"])
        else:
            ok = a["beat_ms"] < r["core_ms"]
            line += f" | {a['beat_ms']:>13.3f} ms {'OK' if ok else '..'}"
            if ok:
                won[l] += 1
            else:
                slower[l].append(r["name"])
    print(line)

print(f"\n{'arm':24s} {'ahead of Core sooner than Core finished':>44}")
for l in labels:
    print(f"{l:24s} {won[l]:>3} of {len(rows)}")
    # Same question in rounds rather than milliseconds, where Core reports a node count at all.
    cmp = [(r["name"], r["arms"][l]["beat_round"], r["core_nodes"]) for r in rows
           if r["core_nodes"] is not None and r["arms"][l]["beat_round"] is not None]
    lost_work = [n for n, a, b in cmp if a >= b]
    print(f"    on work: ahead within fewer rounds than Core spent nodes on "
          f"{len(cmp) - len(lost_work)} of {len(cmp)} comparable"
          + (f"; still behind on {', '.join(lost_work)}" if lost_work else ""))
    if never[l]:
        print(f"    never gets ahead on fee: {', '.join(never[l])}")
    if slower[l]:
        print(f"    gets ahead, but later:   {', '.join(slower[l])}")
