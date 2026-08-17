"""Would a local repair pass on the returned selection close the scale-tier losses?

Every loss decomposes the same way: coin-select ends one parent heavier than Core, having taken a
coin that scored marginally better on value-per-weight but dragged in an ancestor nobody else was
paying for. That is a one-swap error, so the question is whether one swap fixes it.

Emulates: take the engine's answer, and try replacing each selected coin that carries a *privately*
held parent (one no other selected coin shares) with an unselected coin that carries no new parent.
Keep the swap if the package fee drops. Repeat until nothing improves.
"""
import json, math, subprocess, sys, collections
sys.path.insert(0, "/home/evanlinjin/Git/coinselect-benchmark")
import bench

CS = "rust-runner/target/release/coinselect-bench-runner"
CORE = ".build/core-runner/core-runner"


def closure_map(f):
    by_txid = {a["txid"]: a for a in f["ancestors"]}
    memo = {}

    def closure(t):
        if t in memo:
            return memo[t]
        seen, stack = set(), [t]
        while stack:
            x = stack.pop()
            if x is None or x not in by_txid or x in seen:
                continue
            seen.add(x)
            stack.extend(by_txid[x]["parents"])
        memo[t] = seen
        return seen

    return closure, by_txid


def repair(f, selected, change_value, budget=4000):
    """Hill-climb on single swaps. `budget` caps candidate pairs tried, so this stays cheap."""
    closure, by_txid = closure_map(f)
    by_id = f["_by_id"]
    rate = f["feerate_sat_per_vb"]

    dust = f["change"].get("dust_threshold", 0) if isinstance(f.get("change"), dict) else 0

    def score(sel):
        # Give the trial the change `LowestFee` would give it, rather than the change the
        # original answer happened to carry: everything above the fee the package actually owes
        # goes to change if that clears dust, and to fee otherwise. Holding change fixed instead
        # makes almost every swap look infeasible, which is what a first version of this did.
        value = sum(by_id[i]["value"] for i in sel)
        union = bench.ancestor_union(f, sel)
        bump = bench.union_bump(f, union)
        for cv in (0, None):
            weight = bench.child_weight(f, sel, with_change=cv != 0)
            owed = math.ceil(math.ceil(weight / 4) * rate) + bump
            excess = value - f["target"]["value"] - owed
            if cv == 0 and excess < dust:
                break
            if cv is None and excess >= dust:
                cv = excess
                break
        else:
            cv = 0
        cv = max(0, cv or 0)
        m = bench.evaluate(f, sel, cv)
        ok = (m["package_meets_target"] and m["covers_union_bump"]
              and m["within_max_weight"] and m["child_fee"] >= 0)
        return (m["package_fee"] if ok else math.inf), m

    sel = list(selected)
    best, _ = score(sel)
    tried = 0
    improved = True
    while improved and tried < budget:
        improved = False
        chosen = set(sel)
        # Which ancestors does each selected coin hold alone? Dropping it only refunds those.
        holders = collections.Counter()
        for i in sel:
            for t in closure(by_id[i]["residing_txid"]):
                holders[t] += 1
        private = [i for i in sel
                   if any(holders[t] == 1 for t in closure(by_id[i]["residing_txid"]))]
        # Replacements that add no ancestor the selection is not already paying for.
        covered = set()
        for i in sel:
            covered |= closure(by_id[i]["residing_txid"])
        free = [c["id"] for c in f["candidates"]
                if c["id"] not in chosen and closure(c["residing_txid"]) <= covered]
        free.sort(key=lambda i: -by_id[i]["value"])
        for out in sorted(private, key=lambda i: by_id[i]["value"]):
            for inn in free[:40]:
                tried += 1
                if tried >= budget:
                    break
                trial = [x for x in sel if x != out] + [inn]
                got, _ = score(trial)
                if got < best:
                    sel, best, improved = trial, got, True
                    break
            if improved:
                break
    return sel, best, tried


for name in sys.argv[1:]:
    path = f"fixtures/scale/{name}.json"
    f = bench.load_fixture(path)
    core = json.loads(subprocess.run([CORE, "--fixture", path, "--track", "wallet", "--repeat", "1",
                                      "--warmup", "0", "--deadline-us", "100000"],
                                     capture_output=True, text=True).stdout)
    core_fee = bench.evaluate(f, core["selected"], bench.change_value_of(core))["package_fee"]
    cs = json.loads(subprocess.run([CS, "--fixture", path, "--track", "wallet", "--repeat", "1",
                                    "--warmup", "0", "--deadline-us", "100000",
                                    "--budget", "4000000000"], capture_output=True, text=True).stdout)
    cv = bench.change_value_of(cs)
    before = bench.evaluate(f, cs["selected"], cv)["package_fee"]
    sel, after, tried = repair(f, cs["selected"], cv)
    verdict = "BEATS CORE" if after < core_fee else f"still short by {after - core_fee:,}"
    print(f"{name:28s} core {core_fee:>10,}   cs {before:>10,} -> {after:>10,} "
          f"({100 * (after - before) / before:+.2f}%)  after {tried:,} swaps tried   {verdict}")
