"""Would a portfolio of greedy seeds reach a Core-beating answer in one pass?

Core runs four algorithms and keeps the best; coin-select runs one greedy prefix. A greedy pass
costs microseconds, so extra seeds are nearly free — but only if some key actually lands better on
the fixtures where the search needs milliseconds to catch up.

Emulates the prefix for a set of candidate sort keys and scores each with the harness fee model.
"""
import json, math, subprocess, sys, glob, pathlib
sys.path.insert(0, "/home/evanlinjin/Git/coinselect-benchmark")
import bench

CORE = ".build/core-runner/core-runner"


def own_bumps(f):
    by_txid = {a["txid"]: a for a in f["ancestors"]}
    rate = f["feerate_sat_per_vb"]
    memo, out = {}, {}
    for c in f["candidates"]:
        t = c["residing_txid"]
        if not t:
            out[c["id"]] = 0
            continue
        if t not in memo:
            seen, stack = set(), [t]
            while stack:
                x = stack.pop()
                if x is None or x not in by_txid or x in seen:
                    continue
                seen.add(x)
                stack.extend(by_txid[x]["parents"])
            memo[t] = seen
        u = memo[t]
        w = sum(by_txid[x]["weight"] for x in u)
        fee = sum(by_txid[x]["fee"] for x in u)
        out[c["id"]] = max(0, math.ceil(w * rate / 4.0) - fee)
    return out


def prefix(f, order):
    """Take candidates in `order` until the package covers target + fee + ancestor bump."""
    rate = f["feerate_sat_per_vb"]
    by_txid = {a["txid"]: a for a in f["ancestors"]}
    parents = {a["txid"]: a["parents"] for a in f["ancestors"]}
    union, value, sel, aw, af = set(), 0, [], 0, 0
    for c in order:
        sel.append(c["id"])
        value += c["value"]
        stack = [c["residing_txid"]]
        while stack:
            t = stack.pop()
            if t is None or t not in parents or t in union:
                continue
            union.add(t)
            aw += by_txid[t]["weight"]
            af += by_txid[t]["fee"]
            stack.extend(parents[t])
        bump = max(0, math.ceil(aw * rate / 4.0) - af)
        w = bench.child_weight(f, sel, with_change=False)
        if value - f["target"]["value"] - math.ceil(math.ceil(w / 4.0) * rate) - bump >= 0:
            return sel
    return None


def keys(f):
    rate = f["feerate_sat_per_vb"]
    ob = own_bumps(f)
    spwu = rate / 4.0
    return {
        "value/weight (today)": lambda c: c["value"] / c["input_weight"],
        "(value-own bump)/weight": lambda c: (c["value"] - ob[c["id"]]) / c["input_weight"],
        "effective value (Core's)": lambda c: c["value"] - c["input_weight"] * spwu,
        "eff value - own bump": lambda c: c["value"] - c["input_weight"] * spwu - ob[c["id"]],
        "value descending": lambda c: c["value"],
        "weight ascending": lambda c: -c["input_weight"],
    }


for name in sys.argv[1:]:
    p = f"fixtures/{name}.json"
    f = bench.load_fixture(p)
    c = json.loads(subprocess.run([CORE, "--fixture", p, "--track", "wallet", "--repeat", "3",
                                   "--warmup", "1"], capture_output=True, text=True).stdout)
    cf = bench.evaluate(f, c["selected"], bench.change_value_of(c))["package_fee"]
    print(f"\n=== {name}   Core {cf:,}")
    best = None
    for label, k in keys(f).items():
        sel = prefix(f, sorted(f["candidates"], key=k, reverse=True))
        if sel is None:
            print(f"  {label:26s} cannot fund the target")
            continue
        fee = bench.evaluate(f, sel, 0)["package_fee"]
        best = fee if best is None else min(best, fee)
        print(f"  {label:26s} {fee:>10,} {len(sel):>4} inputs {'  BEATS CORE' if fee < cf else ''}")
    print(f"  {'best of the portfolio':26s} {best:>10,} {'  BEATS CORE' if best < cf else '  still short'}")
