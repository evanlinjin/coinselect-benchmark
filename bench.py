#!/usr/bin/env python3
"""Build both pinned revisions, run the fixture matrix, and write the report.

    python3 bench.py all          # setup + run + report
    python3 bench.py setup        # clone and build both pinned revisions
    python3 bench.py run          # run the matrix into results/raw/
    python3 bench.py report       # score results/raw/ into CSV, JSON and Markdown
    python3 bench.py smoke        # setup + the CI-sized fixture only + report

Both runners emit their own numbers, but nothing in the comparison trusts them: `report`
recomputes every package-quality figure from the fixture and the selected candidate ids, with
one implementation of each formula, and cross-checks the runners' own figures against it.

Stdlib only, on purpose: the harness has to run wherever the two toolchains do.
"""

import argparse
import csv
import glob
import json
import os
import pathlib
import platform
import subprocess
import sys

ROOT = pathlib.Path(__file__).parent.resolve()
BUILD = ROOT / ".build"
RESULTS = ROOT / "results"
RAW = RESULTS / "raw"
FIXTURES = ROOT / "fixtures"
PINS = json.loads((ROOT / "pins.json").read_text())

TRACKS = ["kernel", "wallet"]
RUNNERS = ["coin-select", "bitcoin-core"]

# Core targets the runner links against. Building these instead of all of Core keeps setup at
# well under a minute and avoids the node's storage dependencies.
CORE_LIB_TARGETS = ["bitcoin_util", "bitcoin_crypto", "bitcoin_consensus", "bitcoin_clientversion", "univalue"]

WITNESS_SCALE_FACTOR = 4
TX_FIXED_FIELD_WEIGHT = 32


# --- shared fee model -------------------------------------------------------
# One implementation, applied to whatever each runner selected. See fixtures/README.md.


def varint_size(v):
    if v <= 0xFC:
        return 1
    if v <= 0xFFFF:
        return 3
    if v <= 0xFFFF_FFFF:
        return 5
    return 9


def child_weight(fixture, selected, with_change):
    """Weight of the child transaction implied by `selected`, in weight units."""
    cands = [fixture["_by_id"][i] for i in selected]
    n_inputs = len(cands)
    weight = fixture["target"]["non_input_weight"] - (0 if any(c["is_segwit"] for c in cands) else 2)
    weight += 4 * varint_size(n_inputs)
    weight += sum(c["input_weight"] for c in cands)
    # A legacy input serialises an empty witness once the transaction has a witness section.
    if any(c["is_segwit"] for c in cands):
        weight += sum(1 for c in cands if not c["is_segwit"])
    if with_change:
        n_out = fixture["target"]["n_outputs"]
        weight += fixture["change"]["output_weight"]
        weight += 4 * (varint_size(n_out + 1) - varint_size(n_out))
    return weight


def ancestor_union(fixture, selected):
    """Transitive unconfirmed ancestors of `selected`, each counted once."""
    parents = {a["txid"]: a["parents"] for a in fixture["ancestors"]}
    union = set()
    stack = [fixture["_by_id"][i]["residing_txid"] for i in selected]
    while stack:
        txid = stack.pop()
        if txid is None or txid not in parents or txid in union:
            continue
        union.add(txid)
        stack.extend(parents[txid])
    return union


def union_bump(fixture, union):
    """What coin-select charges: net the whole union, saturate at zero."""
    by_txid = {a["txid"]: a for a in fixture["ancestors"]}
    weight = sum(by_txid[t]["weight"] for t in union)
    fee = sum(by_txid[t]["fee"] for t in union)
    # FeeRate::implied_fee_wu, i.e. ceil(weight * sat_per_vb / 4).
    return max(0, -(-weight * fixture["feerate_sat_per_vb"] // 4) - fee)


class MiniMiner:
    """Core's node::MiniMiner bump-fee semantics, reimplemented from the pinned source.

    Deliberately a second, independent implementation of core-runner/mini_miner_lite.h: `report`
    asserts the two agree on every selection, so a mistake in either shows up as a harness
    failure rather than as a silent difference in the results.
    """

    def __init__(self, fixture):
        self.rate = fixture["feerate_sat_per_vb"]
        self.tx = {a["txid"]: dict(vsize=a["weight"] // 4, fee=a["fee"], parents=a["parents"]) for a in fixture["ancestors"]}
        self.in_block = set()
        self._build_template()

    def _closure(self, txid):
        seen, stack = set(), [txid]
        while stack:
            cur = stack.pop()
            if cur not in self.tx or cur in seen:
                continue
            seen.add(cur)
            stack.extend(self.tx[cur]["parents"])
        return seen

    def _fee(self, vsize):
        return (self.rate * 1000 * vsize + 999) // 1000  # CFeeRate::GetFee, rounding up

    def _build_template(self):
        live = dict(self.tx)
        anc = {t: self._closure(t) for t in self.tx}

        def package(txid):
            rest = [a for a in anc[txid] if a in live]
            return sum(live[a]["fee"] for a in rest), sum(live[a]["vsize"] for a in rest)

        def min_feerate(txid):
            """min(own feerate, ancestor-set feerate) as a (fee, vsize) pair."""
            own = (live[txid]["fee"], live[txid]["vsize"])
            pkg = package(txid)
            return own if own[0] * pkg[1] < pkg[0] * own[1] else pkg

        while live:
            # Highest min-feerate first, compared by cross-multiplication so equal ratios really
            # tie; Core breaks those ties on txid and so do we (`live` is iterated sorted).
            best = None
            for txid in sorted(live):
                if best is None:
                    best = txid
                    continue
                a, b = min_feerate(txid), min_feerate(best)
                if a[0] * b[1] > b[0] * a[1]:
                    best = txid
            pkg_fee, pkg_vsize = package(best)
            if pkg_fee < self._fee(pkg_vsize):
                break
            for txid in [a for a in anc[best] if a in live]:
                self.in_block.add(txid)
                del live[txid]

    def individual_bump(self, txid):
        if txid is None or txid not in self.tx or txid in self.in_block:
            return 0
        rest = [a for a in self._closure(txid) if a not in self.in_block]
        with_anc = self._fee(sum(self.tx[a]["vsize"] for a in rest)) - sum(self.tx[a]["fee"] for a in rest)
        own = self._fee(self.tx[txid]["vsize"]) - self.tx[txid]["fee"]
        return max(with_anc, own, 0)

    def combined_bump(self, txids):
        unmined = set()
        for txid in txids:
            if txid is None or txid not in self.tx or txid in self.in_block:
                continue
            unmined |= {a for a in self._closure(txid) if a not in self.in_block}
        if not unmined:
            return 0
        return self._fee(sum(self.tx[a]["vsize"] for a in unmined)) - sum(self.tx[a]["fee"] for a in unmined)


def core_waste(fixture, selected, summed_individual, combined):
    """Core's waste metric for an arbitrary selection, as `SelectionResult::RecalculateWaste`
    computes it with the wallet flow's parameters.

    Having this here lets the report score coin-select's selections on Core's objective and vice
    versa, which is the only way to compare two searches that minimise different things. The
    report also checks it against the waste the Core runner reported for its own selection, so a
    misreading of Core's accounting shows up as a harness failure.
    """
    by_id = fixture["_by_id"]
    rate = fixture["feerate_sat_per_vb"]
    long_term = fixture["long_term_feerate_sat_per_vb"]
    discard = fixture["discard_feerate_sat_per_vb"]
    dust_rate = fixture["dust_relay_feerate_sat_per_vb"]

    change_out_vb = fixture["change"]["output_weight"] // 4
    change_spend_vb = fixture["change"]["spend_weight"] // 4
    change_fee = rate * change_out_vb
    cost_of_change = discard * change_spend_vb + change_fee
    min_viable_change = max(discard * change_spend_vb + 1, dust_rate * (change_out_vb + change_spend_vb))

    # Core's tx_noinputs_size, i.e. the same conversion core-runner makes.
    selection_target = fixture["target"]["value"] + rate * ((fixture["target"]["non_input_weight"] + 4) // 4)

    input_vb = sum(by_id[i]["input_weight"] // 4 for i in selected)
    coin_fee = rate * input_vb + summed_individual
    coin_long_term_fee = long_term * input_vb
    discount = max(0, summed_individual - combined)
    effective_value = sum(by_id[i]["value"] for i in selected) - coin_fee + discount

    waste = coin_fee - coin_long_term_fee - discount
    change = effective_value - selection_target - change_fee
    if change < min_viable_change:
        waste += effective_value - selection_target  # excess burned to fees
    else:
        waste += cost_of_change
    return waste


def evaluate(fixture, selected, change_value):
    """Package-quality metrics for one selection, computed only from the fixture."""
    if not selected:
        return None
    by_id = fixture["_by_id"]
    rate = fixture["feerate_sat_per_vb"]
    selected_value = sum(by_id[i]["value"] for i in selected)
    weight = child_weight(fixture, selected, with_change=change_value > 0)
    fee = selected_value - fixture["target"]["value"] - change_value

    union = ancestor_union(fixture, selected)
    by_txid = {a["txid"]: a for a in fixture["ancestors"]}
    anc_weight = sum(by_txid[t]["weight"] for t in union)
    anc_fee = sum(by_txid[t]["fee"] for t in union)

    miner = fixture["_mini_miner"]
    residing = [by_id[i]["residing_txid"] for i in selected]
    summed_individual = sum(miner.individual_bump(t) for t in residing)
    combined = miner.combined_bump(residing)

    package_weight = weight + anc_weight
    package_fee = fee + anc_fee
    child_vsize = -(-weight // 4)
    package_vsize = -(-package_weight // 4)
    n_legacy = sum(1 for i in selected if not by_id[i]["is_segwit"])
    # What the child pays over its own feerate obligation, i.e. what is left over to bump
    # ancestors with. The two engines disagree about how much that has to be.
    surplus = fee - rate * child_vsize
    owed = union_bump(fixture, union)
    return {
        "n_inputs": len(selected),
        "n_legacy_inputs": n_legacy,
        "selected_value": selected_value,
        "child_weight": weight,
        "child_fee": fee,
        "child_feerate_sat_per_vb": round(fee / child_vsize, 4),
        "change_value": change_value,
        "ancestors_in_union": len(union),
        "ancestor_weight": anc_weight,
        "ancestor_fee": anc_fee,
        "union_bump": owed,
        "core_summed_individual_bump": summed_individual,
        "core_combined_bump": combined,
        "core_bump_discount": max(0, summed_individual - combined),
        # Both objectives, for both engines' selections, so the two searches can be compared on
        # each other's terms rather than only on their own.
        "core_waste": core_waste(fixture, selected, summed_individual, combined),
        "package_fee": package_fee,
        "package_weight": package_weight,
        "package_feerate_sat_per_vb": round(package_fee / package_vsize, 4),
        "child_surplus": surplus,
        "covers_union_bump": surplus >= owed,
        # Core's stricter demand: every ancestor the mini-miner did not already mine has to be
        # lifted to the target feerate on its own, with no credit for a sibling that overpays.
        "covers_core_bump": surplus >= combined,
        # The engine-neutral verdict: does the package as a whole reach the target feerate once
        # the ancestors it drags in are counted?
        "package_meets_target": package_fee >= rate * package_vsize,
        "child_meets_target": fee >= rate * child_vsize,
        "target_shortfall": max(0, rate * package_vsize - package_fee),
        # Core prices a legacy input at its scriptSig weight only, so it does not fund the empty
        # witness that input still serialises once the transaction has a witness section. That is
        # `n_legacy` weight units, which is up to `ceil(n_legacy / 4)` vbytes once rounded. A
        # shortfall no larger than this is that known gap, not a selection that missed the target.
        "explainable_shortfall": rate * -(-n_legacy // 4),
        "within_max_weight": fixture["max_weight"] is None or weight <= fixture["max_weight"],
    }


def load_fixture(path):
    f = json.loads(pathlib.Path(path).read_text())
    f["_path"] = str(path)
    f["_by_id"] = {c["id"]: c for c in f["candidates"]}
    f["_mini_miner"] = MiniMiner(f)
    return f


# --- setup ------------------------------------------------------------------


def run(cmd, **kwargs):
    print("$ " + " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True, **kwargs)


def capture(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def compile_flags(build_dir, target):
    """The flags the compiler was actually invoked with.

    Read from the generated build rules rather than from CMakeCache.txt: the cache still holds
    the unmodified `CMAKE_CXX_FLAGS_RELEASE`, while `core-runner/CMakeLists.txt` strips `-DNDEBUG`
    from it, so the cache would misreport the build.
    """
    rules = pathlib.Path(build_dir) / "CMakeFiles" / f"{target}.dir" / "flags.make"
    if not rules.exists():
        return None
    for line in rules.read_text().splitlines():
        if line.startswith("CXX_FLAGS"):
            return " ".join(line.partition("=")[2].split())
    return None


def clone_pinned(name, dest, patches=()):
    """Check out exactly `rev` and re-apply `patches` from scratch every time.

    `--force` discards any previous patching, so setup is idempotent and patches can never
    stack up on an already-patched tree.
    """
    pin = PINS[name]
    if not (dest / ".git").exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "init", "-q", str(dest)])
        run(["git", "-C", str(dest), "remote", "add", "origin", pin["repo"]])
    run(["git", "-C", str(dest), "fetch", "-q", "--depth", "1", "origin", pin["rev"]])
    run(["git", "-C", str(dest), "checkout", "-q", "--force", pin["rev"]])
    for patch in patches:
        run(["git", "-C", str(dest), "apply", str(patch)])
    return pin["rev"]


def cmd_setup(args):
    BUILD.mkdir(exist_ok=True)
    RESULTS.mkdir(exist_ok=True)

    core = BUILD / "core"
    clone_pinned("bitcoin_core", core, patches=sorted((ROOT / "patches").glob("*.patch")))
    core_build = core / "build"
    if not (core_build / "src" / "bitcoin-build-config.h").exists():
        run([
            "cmake", "-S", str(core), "-B", str(core_build),
            "-DCMAKE_BUILD_TYPE=Release",
            # Nothing but the coin-selection primitives is needed, and turning the rest off keeps
            # the wallet's storage backends out of the dependency set.
            "-DBUILD_DAEMON=OFF", "-DBUILD_CLI=OFF", "-DBUILD_TX=OFF", "-DBUILD_UTIL=OFF",
            "-DBUILD_UTIL_CHAINSTATE=OFF", "-DBUILD_WALLET_TOOL=OFF", "-DBUILD_TESTS=OFF",
            "-DBUILD_BENCH=OFF", "-DBUILD_FUZZ_BINARY=OFF", "-DWITH_ZMQ=OFF", "-DENABLE_IPC=OFF",
        ])
    run(["cmake", "--build", str(core_build), f"-j{os.cpu_count()}", "--target", *CORE_LIB_TARGETS])

    runner_build = BUILD / "core-runner"
    run([
        "cmake", "-S", str(ROOT / "core-runner"), "-B", str(runner_build),
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCORE_SOURCE_DIR={core}", f"-DCORE_BUILD_DIR={core_build}",
    ])
    run(["cmake", "--build", str(runner_build), f"-j{os.cpu_count()}"])
    run([str(runner_build / "core-runner"), "--self-check"])

    # The Rust runner pins the coin-select revision in its own manifest so `cargo build` alone
    # is reproducible; check the two pins have not drifted apart.
    manifest = (ROOT / "rust-runner" / "Cargo.toml").read_text()
    want = PINS["coin_select"]["rev"]
    if want not in manifest:
        sys.exit(f"rust-runner/Cargo.toml does not pin {want}; update it or pins.json")
    run(["cargo", "build", "--release", "--manifest-path", str(ROOT / "rust-runner" / "Cargo.toml")])

    env = {
        "host": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "cpu_count": os.cpu_count(),
        "cxx": capture(["c++", "--version"]).splitlines()[0],
        "cargo": capture(["cargo", "--version"]),
        "rustc": capture(["rustc", "--version"]),
        "cmake": capture(["cmake", "--version"]).splitlines()[0],
        "core_rev": capture(["git", "-C", str(core), "rev-parse", "HEAD"]),
        # The flags the runner (and Core's own coinselection.cpp inside it) is actually built
        # with. NDEBUG is absent on purpose: Core refuses to compile with assertions off.
        "core_runner_cxx_flags": compile_flags(runner_build, "core-runner"),
        "rust_runner_profile": "release, codegen-units=1, lto=off, debug=true",
        "core_patches": [p.name for p in sorted((ROOT / "patches").glob("*.patch"))],
        "coin_select_rev": PINS["coin_select"]["rev"],
        "pins": PINS,
    }
    (RESULTS / "environment.json").write_text(json.dumps(env, indent=1) + "\n")
    print("\nsetup complete; environment recorded in results/environment.json")


# --- run --------------------------------------------------------------------


def runner_paths():
    core = BUILD / "core-runner" / "core-runner"
    rust = ROOT / "rust-runner" / "target" / "release" / "coinselect-bench-runner"
    for path in (core, rust):
        if not path.exists():
            sys.exit(f"{path} is missing; run `python3 bench.py setup` first")
    return {"bitcoin-core": core, "coin-select": rust}


def cmd_run(args):
    RAW.mkdir(parents=True, exist_ok=True)
    if args.clean:
        for stale in RAW.glob("*.json"):
            stale.unlink()
    paths = runner_paths()
    fixtures = sorted(glob.glob(str(FIXTURES / args.fixtures)))
    if not fixtures:
        sys.exit(f"no fixtures match {args.fixtures}")

    for fixture_path in fixtures:
        name = pathlib.Path(fixture_path).stem
        for track in args.tracks:
            for runner, binary in paths.items():
                cmd = [
                    str(binary), "--fixture", fixture_path, "--track", track,
                    "--repeat", str(args.repeat), "--warmup", str(args.warmup),
                ]
                if args.oracle:
                    cmd.append("--oracle")
                print(f"  {name:28s} {track:7s} {runner}", flush=True)
                out = subprocess.run(cmd, capture_output=True, text=True)
                if out.returncode != 0:
                    sys.exit(f"{runner} failed on {name}/{track}:\n{out.stderr}")
                (RAW / f"{name}.{track}.{runner}.json").write_text(out.stdout)
    print(f"\nwrote {len(list(RAW.glob('*.json')))} raw results to {RAW}")


# --- report -----------------------------------------------------------------


CSV_COLUMNS = [
    "fixture", "family", "size", "track", "runner", "algorithm", "ok",
    "wall_ns_median", "rounds", "exhausted", "peak_rss_kb",
    "n_inputs", "n_legacy_inputs", "child_weight", "child_fee", "change_value", "child_surplus",
    "ancestors_in_union", "union_bump", "core_summed_individual_bump", "core_combined_bump",
    "covers_union_bump", "covers_core_bump",
    "package_fee", "package_weight", "package_feerate_sat_per_vb", "package_meets_target",
    "target_shortfall", "within_max_weight", "core_waste", "waste", "score", "matches_oracle",
]


def oracle_verdict(raw):
    """Whether the runner reached its own objective's optimum, `""` when nothing was enumerated.

    Compared on the objective's value, not on the selected set: two different selections can be
    equally good, and calling that a miss would be wrong.
    """
    oracle = raw.get("oracle") or {}
    if not oracle.get("ran"):
        return ""
    best = oracle.get("best_waste", oracle.get("best_score"))
    if not raw["ok"]:
        return "no solution (oracle agrees)" if best is None else "missed a solution"
    native = raw.get("native") or {}
    got = native.get("waste", native.get("score"))
    if best is None or got is None:
        return sorted(oracle.get("best_selected") or []) == sorted(raw["selected"])
    return abs(got - best) <= 1e-3


def change_value_of(raw):
    native = raw.get("native") or {}
    return native.get("change_value", native.get("drain_value", 0)) or 0


def cross_check(fixture, raw, metrics, problems):
    """Confirm each runner's own figures against the harness's independent recomputation."""
    native = raw.get("native") or {}
    tag = f"{raw['fixture']}/{raw['track']}/{raw['runner']}"
    if raw["runner"] == "bitcoin-core":
        for key, mine in (("summed_individual_bump_fees", "core_summed_individual_bump"),
                          ("combined_bump_fee", "core_combined_bump")):
            if key in native and native[key] != metrics[mine]:
                problems.append(f"{tag}: {key} {native[key]} != harness {metrics[mine]}")
        if "waste" in native and native["waste"] != metrics["core_waste"]:
            problems.append(f"{tag}: waste {native['waste']} != harness {metrics['core_waste']}")
        if "input_weight" in native:
            # Core's SelectionResult tracks the summed candidate weights only: no input-count
            # varint and no segwit marker, both of which the shared model puts elsewhere.
            want = sum(fixture["_by_id"][i]["input_weight"] for i in raw["selected"])
            if native["input_weight"] != want:
                problems.append(f"{tag}: input weight {native['input_weight']} != fixture {want}")
    else:
        # The crate computes the child weight itself; the shared model should land on the same
        # number for every selection, which is what makes the two engines' weights comparable.
        if "child_weight" in native and native["child_weight"] != metrics["child_weight"]:
            problems.append(f"{tag}: child weight {native['child_weight']} != harness {metrics['child_weight']}")
        if "ancestor_bump" in native and native["ancestor_bump"] != metrics["union_bump"]:
            problems.append(f"{tag}: ancestor_bump {native['ancestor_bump']} != harness {metrics['union_bump']}")
        if "child_fee" in native and native["child_fee"] != metrics["child_fee"]:
            problems.append(f"{tag}: child_fee {native['child_fee']} != harness {metrics['child_fee']}")


def cmd_report(args):
    raws = sorted(RAW.glob("*.json"))
    if not raws:
        sys.exit("no raw results; run `python3 bench.py run` first")

    fixtures = {}
    rows = []
    records = []
    problems = []
    notes = []

    for path in raws:
        raw = json.loads(path.read_text())
        name = raw["fixture"]
        if name not in fixtures:
            fixtures[name] = load_fixture(FIXTURES / f"{name}.json")
        fixture = fixtures[name]

        metrics = evaluate(fixture, raw["selected"], change_value_of(raw))
        if metrics:
            cross_check(fixture, raw, metrics, problems)
            if metrics["target_shortfall"] > metrics["explainable_shortfall"]:
                problems.append(
                    f"{name}/{raw['track']}/{raw['runner']}: package feerate "
                    f"{metrics['package_feerate_sat_per_vb']} is {metrics['target_shortfall']} sats "
                    f"below the {fixture['feerate_sat_per_vb']} sat/vB target"
                )
            elif metrics["target_shortfall"]:
                notes.append(
                    f"{name}/{raw['track']}/{raw['runner']}: {metrics['target_shortfall']} sats "
                    f"short of the target feerate, within the {metrics['explainable_shortfall']} sats "
                    f"Core leaves unfunded for {metrics['n_legacy_inputs']} legacy input(s)"
                )
            if not metrics["within_max_weight"]:
                problems.append(f"{name}/{raw['track']}/{raw['runner']}: selection exceeds max_weight")

        matches_oracle = oracle_verdict(raw)

        native = raw.get("native") or {}
        rows.append({
            "fixture": name,
            "family": raw["family"],
            "size": raw["size"],
            "track": raw["track"],
            "runner": raw["runner"],
            "algorithm": raw["algorithm"],
            "ok": raw["ok"],
            "wall_ns_median": raw["timing"]["wall_ns_median"],
            "rounds": raw["rounds"],
            "exhausted": raw["exhausted"],
            "peak_rss_kb": raw["peak_rss_kb"],
            "waste": native.get("waste", ""),
            "score": native.get("score", ""),
            "matches_oracle": matches_oracle,
            **{k: (metrics or {}).get(k, "") for k in CSV_COLUMNS if k in (metrics or {})},
        })
        records.append({"raw": raw, "metrics": metrics, "matches_oracle": matches_oracle})

    RESULTS.mkdir(exist_ok=True)
    with (RESULTS / "results.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore", restval="")
        writer.writeheader()
        writer.writerows(rows)
    (RESULTS / "results.json").write_text(json.dumps(records, indent=1) + "\n")
    (RESULTS / "SUMMARY.md").write_text(build_summary(fixtures, records, problems, notes))
    print(f"wrote results/results.csv, results/results.json and results/SUMMARY.md")
    if problems:
        print(f"\n{len(problems)} verification problem(s):", file=sys.stderr)
        for p in problems[:20]:
            print("  - " + p, file=sys.stderr)
    return 0


def build_summary(fixtures, records, problems, notes):
    env = {}
    env_path = RESULTS / "environment.json"
    if env_path.exists():
        env = json.loads(env_path.read_text())

    by_key = {}
    for rec in records:
        raw = rec["raw"]
        by_key[(raw["fixture"], raw["track"], raw["runner"])] = rec

    out = []
    w = out.append
    w("# Ancestor-aware coin selection: coin-select vs Bitcoin Core\n")
    w("Generated by `python3 bench.py report`. Every package-quality number below is recomputed")
    w("by the harness from the fixture and the selected candidate ids, not taken from either")
    w("runner, so the two columns are scored by the same formula.\n")

    w("## Revisions and environment\n")
    w(f"- Bitcoin Core: `{PINS['bitcoin_core']['rev']}` ({PINS['bitcoin_core']['describes']})")
    w(f"- coin-select: `{PINS['coin_select']['rev']}` ({PINS['coin_select']['describes']})")
    if env:
        w(f"- host: {env.get('host')} ({env.get('cpu_count')} cpus)")
        w(f"- compilers: {env.get('cxx')} ({env.get('core_runner_cxx_flags')}); {env.get('rustc')}"
          f" ({env.get('rust_runner_profile')})")
        w(f"- Core patches applied: {', '.join(env.get('core_patches') or ['none'])}"
          " (instrumentation only, see patches/README.md)")
    sample = next(iter(fixtures.values()), None)
    if sample:
        w(f"- search budget: {sample['search_budget']} (Core's compile-time `TOTAL_TRIES`;"
          " coin-select is given the same number of branch-and-bound rounds)")
    warmup = next((r["raw"]["timing"]["warmup"] for r in records), 0)
    repeats = next((r["raw"]["timing"]["repeats"] for r in records), 0)
    w(f"- timing: {warmup} warm-up run(s), {repeats} measured run(s), median reported\n")

    w("**The objectives are not identical.** Core's `SelectCoinsBnB` looks for the least-waste")
    w("selection whose effective value lands inside `[target, target + cost_of_change]`;")
    w("coin-select's `Changeless<LowestFee>` minimises the child transaction's fee over every")
    w("changeless selection. Runtime and node counts are therefore compared directly, while")
    w("solution quality is only ever compared through the shared metrics below.\n")

    w("## At a glance\n")
    w(_at_a_glance(fixtures, by_key))
    w("")

    for track in TRACKS:
        w(f"## Track: {track}\n")
        w(_track_table(fixtures, by_key, track))
        w("")

    w("## Objective cross-scores\n")
    w("Each engine's selection scored on **both** objectives by the harness. Core minimises the")
    w("`waste` column, coin-select minimises fee; each is expected to win its own column, so the")
    w("interesting cases are the ones where an engine also wins the other's.\n")
    w(_cross_scores(fixtures, by_key))
    w("")

    w("## Selection differences\n")
    diffs = _selection_differences(fixtures, by_key)
    if diffs:
        w("Cases where both runners produced a selection but chose different packages. The")
        w("`union bump` column is what coin-select charges (the whole ancestor union, netted);")
        w("`Core combined` is what Core's mini-miner charges after discounting shared ancestry.\n")
        w(diffs)
    else:
        w("No fixture produced two different selections from two successful runs.")
    w("")

    w("## Oracle checks\n")
    w(_oracle_section(by_key))
    w("")

    w("## Verification\n")
    if problems:
        w(f"{len(problems)} problem(s) found:\n")
        for p in problems:
            w(f"- {p}")
    else:
        w("Every selection was re-derived from the fixture: each package reaches the target")
        w("feerate once its ancestor union is counted, each stays inside `max_weight`, and each")
        w("runner's own bump-fee figures match the harness's independent recomputation.")
    if notes:
        w("\nKnown fee-model gaps, within tolerance:\n")
        for note in notes:
            w(f"- {note}")
    w("")
    return "\n".join(out) + "\n"


def _at_a_glance(fixtures, by_key):
    """One row per track: how hard each engine worked and how the two objectives came out."""
    lines = [
        "| track | engine | median time | budget exhausted | no solution | wins on fee | wins on waste |",
        "|" + "---|" * 7,
    ]
    for track in TRACKS:
        pairs = [(by_key.get((n, track, "coin-select")), by_key.get((n, track, "bitcoin-core")))
                 for n in sorted(fixtures)]
        pairs = [(a, b) for a, b in pairs if a and b]
        scored = [(a["metrics"], b["metrics"]) for a, b in pairs if a["metrics"] and b["metrics"]]
        fee_wins = [sum(1 for a, b in scored if a["package_fee"] < b["package_fee"]),
                    sum(1 for a, b in scored if b["package_fee"] < a["package_fee"])]
        waste_wins = [sum(1 for a, b in scored if a["core_waste"] < b["core_waste"]),
                      sum(1 for a, b in scored if b["core_waste"] < a["core_waste"])]
        for slot, engine in ((0, "coin-select"), (1, "bitcoin-core")):
            runs = [pair[slot]["raw"] for pair in pairs]
            times = sorted(r["timing"]["wall_ns_median"] for r in runs)
            lines.append(
                f"| {track} | {engine} | {_fmt_us(times[len(times) // 2])} us "
                f"| {sum(1 for r in runs if r['exhausted'] is False)} of {len(runs)} "
                f"| {sum(1 for r in runs if not r['ok'])} "
                f"| {fee_wins[slot]} of {len(scored)} | {waste_wins[slot]} of {len(scored)} |"
            )
    return "\n".join(lines)


def _fmt_us(ns):
    return f"{ns / 1000:.1f}" if ns is not None else "-"


def _fmt_done(exhausted):
    """Whether a search finished its tree, where `None` means the algorithm has no node budget."""
    if exhausted is None:
        return "n/a"
    return "yes" if exhausted else "budget"


def _track_table(fixtures, by_key, track):
    header = (
        "| fixture | n | cs time (us) | core time (us) | cs rounds | core nodes | "
        "cs done | core done | cs pkg fee | core pkg fee | cs bump | core bump | "
        "cs covers core bump | same set |"
    )
    sep = "|" + "---|" * 13 + "---|"
    lines = [header, sep]
    for name in sorted(fixtures):
        cs = by_key.get((name, track, "coin-select"))
        core = by_key.get((name, track, "bitcoin-core"))
        if not cs or not core:
            continue
        cs_m, core_m = cs["metrics"], core["metrics"]
        same = "-"
        if cs["raw"]["ok"] and core["raw"]["ok"]:
            same = "yes" if sorted(cs["raw"]["selected"]) == sorted(core["raw"]["selected"]) else "**no**"
        lines.append(
            f"| {name} | {cs['raw']['size']} "
            f"| {_fmt_us(cs['raw']['timing']['wall_ns_median'])} "
            f"| {_fmt_us(core['raw']['timing']['wall_ns_median'])} "
            f"| {cs['raw']['rounds']} | {core['raw']['rounds'] if core['raw']['rounds'] is not None else '-'} "
            f"| {_fmt_done(cs['raw']['exhausted'])} "
            f"| {_fmt_done(core['raw']['exhausted'])} "
            f"| {cs_m['package_fee'] if cs_m else 'none'} "
            f"| {core_m['package_fee'] if core_m else 'none'} "
            f"| {cs_m['union_bump'] if cs_m else '-'} "
            f"| {core_m['core_combined_bump'] if core_m else '-'} "
            f"| {('yes' if cs_m['covers_core_bump'] else '**no**') if cs_m else '-'} "
            f"| {same} |"
        )
    return "\n".join(lines)


def _cross_scores(fixtures, by_key):
    lines = [
        "| fixture | track | cs waste | core waste | waste winner | cs pkg fee | core pkg fee | fee winner |",
        "|" + "---|" * 8,
    ]
    for name in sorted(fixtures):
        for track in TRACKS:
            cs = by_key.get((name, track, "coin-select"))
            core = by_key.get((name, track, "bitcoin-core"))
            if not cs or not core or not cs["metrics"] or not core["metrics"]:
                continue
            a, b = cs["metrics"], core["metrics"]
            waste_winner = _winner(a["core_waste"], b["core_waste"])
            fee_winner = _winner(a["package_fee"], b["package_fee"])
            lines.append(
                f"| {name} | {track} | {a['core_waste']} | {b['core_waste']} | {waste_winner} "
                f"| {a['package_fee']} | {b['package_fee']} | {fee_winner} |"
            )
    return "\n".join(lines)


def _winner(coin_select, core):
    """Which engine scored lower on a metric where lower is better."""
    if coin_select == core:
        return "tie"
    return "coin-select" if coin_select < core else "core"


def _selection_differences(fixtures, by_key):
    lines = [
        "| fixture | track | cs inputs | core inputs | cs pkg fee | core pkg fee | "
        "cs union bump | core combined | cs pkg feerate | core pkg feerate |",
        "|" + "---|" * 10,
    ]
    any_row = False
    for name in sorted(fixtures):
        for track in TRACKS:
            cs = by_key.get((name, track, "coin-select"))
            core = by_key.get((name, track, "bitcoin-core"))
            if not cs or not core or not (cs["raw"]["ok"] and core["raw"]["ok"]):
                continue
            if sorted(cs["raw"]["selected"]) == sorted(core["raw"]["selected"]):
                continue
            any_row = True
            a, b = cs["metrics"], core["metrics"]
            lines.append(
                f"| {name} | {track} | {a['n_inputs']} | {b['n_inputs']} "
                f"| {a['package_fee']} | {b['package_fee']} "
                f"| {a['union_bump']} | {b['core_combined_bump']} "
                f"| {a['package_feerate_sat_per_vb']} | {b['package_feerate_sat_per_vb']} |"
            )
    return "\n".join(lines) if any_row else ""


def _oracle_section(by_key):
    ran = [(k, r) for k, r in by_key.items() if (r["raw"].get("oracle") or {}).get("ran")]
    if not ran:
        return ("No exhaustive check was run. Pass `--oracle` to `bench.py run`; fixtures with at"
                " most 20 candidates are then brute forced against each runner's own objective.")
    lines = ["Fixtures small enough to enumerate are brute forced against the runner's own",
             "objective, so a disagreement can be attributed rather than just observed.\n",
             "| fixture | track | runner | found optimum |", "|---|---|---|---|"]
    for (name, track, runner), rec in sorted(ran):
        verdict = rec["matches_oracle"]
        if isinstance(verdict, bool):
            verdict = "yes" if verdict else "**no**"
        elif verdict == "missed a solution":
            verdict = "**missed a solution**"
        lines.append(f"| {name} | {track} | {runner} | {verdict} |")
    return "\n".join(lines)


# --- self-check -------------------------------------------------------------


def cmd_self_check(args):
    """The worked example from the comment in Core's `node/mini_miner.cpp`.

    Same case `core-runner --self-check` uses, so a divergence between the C++ port and this one
    shows up here rather than as a quiet difference in the results.
    """
    fixture = {
        "feerate_sat_per_vb": 10,
        "ancestors": [
            {"txid": "grandparent", "weight": 6800, "fee": 1700, "parents": []},
            {"txid": "parent1", "weight": 800, "fee": 17000, "parents": ["grandparent"]},
            {"txid": "parent2", "weight": 800, "fee": 3000, "parents": ["grandparent"]},
            {"txid": "child", "weight": 400, "fee": 900, "parents": ["parent1", "parent2"]},
        ],
    }
    miner = MiniMiner(fixture)
    checks = [
        ("nothing mined at 10 sat/vB", miner.in_block, set()),
        # The child's ancestor set is above the target (-600) so its own shortfall binds.
        ("child bump", miner.individual_bump("child"), 10 * 100 - 900),
        ("grandparent bump", miner.individual_bump("grandparent"), 10 * 1700 - 1700),
        # CalculateTotalBumpFees does not clamp, so an already-paid package reports negative.
        ("combined bump", miner.combined_bump(["child"]),
         10 * (1700 + 200 + 200 + 100) - (1700 + 17000 + 3000 + 900)),
    ]
    cheap = MiniMiner(dict(fixture, feerate_sat_per_vb=1))
    checks.append(("everything mined at 1 sat/vB", cheap.in_block,
                   {"grandparent", "parent1", "parent2", "child"}))
    checks.append(("combined bump at 1 sat/vB", cheap.combined_bump(["child", "grandparent"]), 0))

    failures = [f"{what}: expected {want}, got {got}" for what, got, want in checks if got != want]
    for failure in failures:
        print("  " + failure, file=sys.stderr)
    if failures:
        sys.exit(f"{len(failures)} self-check failure(s)")
    print("bench.py mini-miner self-check ok")


# --- entry point ------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("setup", help="clone and build both pinned revisions")

    def add_run_flags(p):
        p.add_argument("--fixtures", default="*.json", help="glob within fixtures/ (default: all)")
        p.add_argument("--tracks", nargs="+", default=TRACKS, choices=TRACKS)
        p.add_argument("--repeat", type=int, default=5, help="measured runs per case")
        p.add_argument("--warmup", type=int, default=1, help="discarded runs per case")
        p.add_argument("--oracle", action="store_true", help="brute force fixtures of at most 20 candidates")
        p.add_argument("--clean", action="store_true", help="drop existing raw results first")

    add_run_flags(sub.add_parser("run", help="run the matrix into results/raw/"))
    sub.add_parser("report", help="score results/raw/ into CSV, JSON and Markdown")
    sub.add_parser("self-check", help="check this file's mini-miner port against Core's own example")
    add_run_flags(sub.add_parser("all", help="setup, run and report"))
    sub.add_parser("smoke", help="setup, run the CI-sized fixture, report")

    args = ap.parse_args()
    if args.command == "setup":
        return cmd_setup(args)
    if args.command == "run":
        return cmd_run(args)
    if args.command == "report":
        return cmd_report(args)
    if args.command == "self-check":
        return cmd_self_check(args)
    if args.command == "all":
        cmd_setup(args)
        cmd_self_check(args)
        cmd_run(args)
        return cmd_report(args)
    if args.command == "smoke":
        cmd_setup(args)
        smoke = argparse.Namespace(fixtures="smoke.json", tracks=TRACKS, repeat=1, warmup=0,
                                   oracle=True, clean=True)
        cmd_run(smoke)
        return cmd_report(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
