#!/usr/bin/env python3
"""Regenerate the checked-in fixtures under `fixtures/`.

Fixtures are deterministic: every family/size pair has a fixed seed, so re-running
this reproduces the byte-identical files. See `fixtures/README.md` for the schema
and for why weights are constrained to multiples of 4.

    python3 genfixtures.py            # rewrite fixtures/
    python3 genfixtures.py --check    # fail if fixtures/ is stale
"""

import argparse
import json
import pathlib
import random
import sys

import bench  # for MiniMiner, to enforce the ancestors-need-bumping invariant

OUT_DIR = pathlib.Path(__file__).parent / "fixtures"

# Input weights in weight units, rounded up to a multiple of 4 (see fixtures/README.md).
# Base txin (outpoint 36B + nSequence 4B + scriptSig len 1B) = 164 WU.
TXIN_BASE_WEIGHT = 164
INPUT_TYPES = {
    # name:          (weight WU, is_segwit)
    "p2wpkh": (272, True),  # 164 + 107 witness, rounded 271 -> 272
    "p2tr": (232, True),  # 164 + 66 keyspend witness, rounded 230 -> 232
    "p2sh_p2wpkh": (364, True),  # 164 + 92 scriptSig + 107 witness, 363 -> 364
    "p2pkh": (592, False),  # 164 + 4 * 107 scriptSig
}

TXOUT_P2TR_WEIGHT = 172  # (8 value + 1 spk len + 34 spk) * 4
TXOUT_P2WPKH_WEIGHT = 124  # (8 + 1 + 22) * 4
TX_FIXED_FIELD_WEIGHT = 32  # nVersion + nLockTime
WITNESS_MARKER_WEIGHT = 2  # segwit marker + flag

CHANGE_OUTPUT_WEIGHT = TXOUT_P2TR_WEIGHT
CHANGE_SPEND_WEIGHT = INPUT_TYPES["p2tr"][0]

SIZES = [20, 50, 100, 200]

# Families that override the default feerates. CoinGrinder only runs in Core's portfolio above
# 3x the long-term feerate, and at feerate == long_term_feerate Core's waste degenerates
# (`coin.fee - coin.long_term_fee` is 0 for every input, leaving only excess), so one family
# deliberately sits in the high-feerate regime.
FEERATE_OVERRIDES = {"high_feerate": {"feerate_sat_per_vb": 40, "long_term_feerate_sat_per_vb": 10}}
SEARCH_BUDGET = 100_000

FEERATE = 10  # sat/vB, integer so both fee models agree exactly
LONG_TERM_FEERATE = 10
DISCARD_FEERATE = 3
DUST_RELAY_FEERATE = 3


def varint_size(v: int) -> int:
    if v <= 0xFC:
        return 1
    if v <= 0xFFFF:
        return 3
    if v <= 0xFFFF_FFFF:
        return 5
    return 9


def round4(w: int) -> int:
    return ((w + 3) // 4) * 4


def non_input_weight(n_outputs: int, output_weight_sum: int) -> int:
    """Everything in the child tx that is not an input, incl. the segwit marker.

    Kept a multiple of 4 so Core's vbyte pricing and coin-select's weight-unit
    pricing land on the same number of satoshis.
    """
    return round4(
        TX_FIXED_FIELD_WEIGHT
        + 4 * varint_size(n_outputs)
        + output_weight_sum
        + WITNESS_MARKER_WEIGHT
    )


def anc(txid, weight, fee, parents=()):
    assert weight % 4 == 0, weight
    return {"txid": txid, "weight": weight, "fee": fee, "parents": list(parents)}


def underpaying_fee(weight: int, sat_per_vb: int = 1) -> int:
    """Fee of an ancestor that pays `sat_per_vb`, i.e. needs bumping to FEERATE."""
    return (weight // 4) * sat_per_vb


def cand(i, value, itype, residing=None):
    weight, is_segwit = INPUT_TYPES[itype]
    return {
        "id": f"c{i:03d}",
        "value": value,
        "input_weight": weight,
        "input_type": itype,
        "is_segwit": is_segwit,
        "residing_txid": residing,
    }


def wallet_values(rng, n):
    """A wallet-shaped value mix: many small coins, a few large ones."""
    out = []
    for _ in range(n):
        bucket = rng.random()
        if bucket < 0.55:
            out.append(rng.randrange(5_000, 60_000, 1))
        elif bucket < 0.9:
            out.append(rng.randrange(60_000, 500_000, 1))
        else:
            out.append(rng.randrange(500_000, 5_000_000, 1))
    return out


# --- families ---------------------------------------------------------------
# Each returns (candidates, ancestors). `rng` is already seeded.


def fam_no_ancestry(rng, n):
    return [cand(i, v, "p2wpkh") for i, v in enumerate(wallet_values(rng, n))], []


def fam_private_ancestry(rng, n):
    """Every third coin sits on an unconfirmed parent nothing else can reach."""
    cands, ancs = [], []
    for i, v in enumerate(wallet_values(rng, n)):
        if i % 3 == 0:
            txid = f"p{i:03d}"
            w = round4(rng.randrange(400, 1600))
            ancs.append(anc(txid, w, underpaying_fee(w, rng.choice([1, 2, 3]))))
            cands.append(cand(i, v, "p2wpkh", txid))
        else:
            cands.append(cand(i, v, "p2wpkh"))
    return cands, ancs


def fam_shared_ancestry(rng, n):
    """A few unconfirmed parents, each hosting several coins."""
    n_parents = max(2, n // 8)
    ancs = []
    for j in range(n_parents):
        w = round4(rng.randrange(800, 3200))
        ancs.append(anc(f"s{j:02d}", w, underpaying_fee(w, rng.choice([1, 2]))))
    cands = []
    for i, v in enumerate(wallet_values(rng, n)):
        # ~60% of coins sit on one of the shared parents.
        residing = f"s{rng.randrange(n_parents):02d}" if rng.random() < 0.6 else None
        cands.append(cand(i, v, "p2wpkh", residing))
    return cands, ancs


def fam_nested_ancestry(rng, n):
    """Chains of depth 3-4 that share a common root: transitive + shared."""
    n_chains = max(2, n // 12)
    ancs = [anc("root", 1600, underpaying_fee(1600, 1))]
    tips = []
    for j in range(n_chains):
        parent = "root"
        depth = rng.choice([3, 4])
        for d in range(depth):
            txid = f"n{j:02d}_{d}"
            w = round4(rng.randrange(400, 1200))
            ancs.append(anc(txid, w, underpaying_fee(w, rng.choice([1, 2])), [parent]))
            parent = txid
        tips.append(parent)
    cands = []
    for i, v in enumerate(wallet_values(rng, n)):
        residing = rng.choice(tips) if rng.random() < 0.5 else None
        cands.append(cand(i, v, "p2wpkh", residing))
    return cands, ancs


def fam_subsidizing_ancestry(rng, n):
    """An overpaying ancestor inside a package that still, as a whole, needs bumping.

    Every ancestor here belongs in the ancestors-to-bump set: a fat underpaying root
    drags each package's ancestor feerate below the target, so a miner takes none of
    them — not even the child paying four times the target rate on its own.

    That child's surplus is what the two engines account for differently. coin-select
    nets weight and fee over the whole union, so the surplus cancels a deficit
    elsewhere in the same selection. Core charges each UTXO
    `max(individual shortfall, ancestor-set shortfall)` while it searches and refunds
    the overlap only once a result is chosen, so during the search it cannot see that
    two coins on the same root would share the cost.
    """
    n_groups = max(2, n // 10)
    ancs = []
    tips = []
    for j in range(n_groups):
        # A fat, badly underpaying root, spent by a child paying 4x the target rate and
        # by a sibling paying a tenth of it. Both packages stay below target.
        root_w = round4(rng.randrange(6000, 10000))
        rich_w = round4(rng.randrange(800, 2000))
        poor_w = round4(rng.randrange(800, 2000))
        root, rich, poor = f"root{j:02d}", f"rich{j:02d}", f"poor{j:02d}"
        ancs.append(anc(root, root_w, underpaying_fee(root_w, 1)))
        ancs.append(anc(rich, rich_w, (rich_w // 4) * FEERATE * 4, [root]))
        ancs.append(anc(poor, poor_w, underpaying_fee(poor_w, 1), [root]))
        tips += [rich, poor]
    cands = []
    for i, v in enumerate(wallet_values(rng, n)):
        residing = rng.choice(tips) if rng.random() < 0.6 else None
        cands.append(cand(i, v, "p2wpkh", residing))
    return cands, ancs


def fam_wallet_mixed(rng, n):
    """Mixed script types and values, a third of the coins unconfirmed."""
    types = ["p2wpkh", "p2tr", "p2sh_p2wpkh", "p2pkh"]
    weights = [0.5, 0.3, 0.12, 0.08]
    n_parents = max(2, n // 10)
    ancs = []
    for j in range(n_parents):
        w = round4(rng.randrange(600, 2400))
        ancs.append(anc(f"m{j:02d}", w, underpaying_fee(w, rng.choice([1, 2, 5]))))
    # A couple of two-deep chains for good measure.
    for j in range(max(1, n_parents // 3)):
        w = round4(rng.randrange(600, 1600))
        ancs.append(anc(f"mc{j:02d}", w, underpaying_fee(w, 1), [f"m{j:02d}"]))
    tips = [a["txid"] for a in ancs]
    cands = []
    for i, v in enumerate(wallet_values(rng, n)):
        itype = rng.choices(types, weights)[0]
        residing = rng.choice(tips) if rng.random() < 0.33 else None
        cands.append(cand(i, v, itype, residing))
    return cands, ancs


def fam_adversarial_shared(rng, n):
    """Summing individual bump fees hides a good selection.

    One fat, badly underpaying ancestor hosts a block of small coins. Charged the
    whole bump each, every one of them has negative effective value and Core drops
    them from the BnB pool entirely. Taken together they clear the target and pay
    the bump once, which is what coin-select's union accounting sees.
    """
    fat_w = round4(rng.randrange(8_000, 16_000))
    ancs = [anc("fat", fat_w, underpaying_fee(fat_w, 1))]
    bump = (fat_w // 4) * (FEERATE - 1)
    n_on_fat = max(4, n // 3)
    cands = []
    # Coins on the fat ancestor: each worth clearly less than the full bump.
    for i in range(n_on_fat):
        cands.append(cand(i, int(bump * rng.uniform(0.25, 0.7)), "p2wpkh", "fat"))
    # Confirmed coins that are individually fine but collectively wasteful.
    for i, v in enumerate(wallet_values(rng, n - n_on_fat), start=n_on_fat):
        cands.append(cand(i, v, "p2wpkh"))
    rng.shuffle(cands)
    for i, c in enumerate(cands):
        c["id"] = f"c{i:03d}"
    return cands, ancs


FAMILIES = {
    "no_ancestry": fam_no_ancestry,
    "high_feerate": fam_wallet_mixed,
    "private_ancestry": fam_private_ancestry,
    "shared_ancestry": fam_shared_ancestry,
    "nested_ancestry": fam_nested_ancestry,
    "subsidizing_ancestry": fam_subsidizing_ancestry,
    "wallet_mixed": fam_wallet_mixed,
    "adversarial_shared": fam_adversarial_shared,
}


def seed_for(family: str, size: int) -> int:
    # Stable across Python versions (hash() is not).
    h = 2166136261
    for ch in f"{family}/{size}":
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h


def build(family: str, size: int) -> dict:
    overrides = FEERATE_OVERRIDES.get(family, {})
    rng = random.Random(seed_for(family, size))
    cands, ancs = FAMILIES[family](rng, size)
    total = sum(c["value"] for c in cands)
    # Aim at roughly half the pool so the search has real work to do, and quantise
    # so the target does not accidentally coincide with a single coin.
    target_value = int(total * 0.45) // 1000 * 1000

    max_weight = None
    if family == "wallet_mixed":
        # A cap that admits solutions but bites on input-heavy ones.
        widest = sorted((c["input_weight"] for c in cands), reverse=True)[: max(1, size // 4)]
        max_weight = non_input_weight(1, TXOUT_P2TR_WEIGHT) + sum(widest)

    return {
        "name": f"{family}_{size}",
        "family": family,
        "size": size,
        "seed": seed_for(family, size),
        "search_budget": SEARCH_BUDGET,
        "feerate_sat_per_vb": overrides.get("feerate_sat_per_vb", FEERATE),
        "long_term_feerate_sat_per_vb": overrides.get("long_term_feerate_sat_per_vb", LONG_TERM_FEERATE),
        "discard_feerate_sat_per_vb": DISCARD_FEERATE,
        "dust_relay_feerate_sat_per_vb": DUST_RELAY_FEERATE,
        "target": {
            "value": target_value,
            "n_outputs": 1,
            "non_input_weight": non_input_weight(1, TXOUT_P2TR_WEIGHT),
        },
        "change": {
            "output_weight": CHANGE_OUTPUT_WEIGHT,
            "spend_weight": CHANGE_SPEND_WEIGHT,
        },
        "max_weight": max_weight,
        "candidates": cands,
        "ancestors": ancs,
    }


def build_smoke() -> dict:
    """Tiny fixture for CI: shared + subsidizing ancestry, small enough to brute force."""
    f = {
        "name": "smoke",
        "family": "smoke",
        "size": 8,
        "seed": 1,
        "search_budget": SEARCH_BUDGET,
        "feerate_sat_per_vb": FEERATE,
        "long_term_feerate_sat_per_vb": LONG_TERM_FEERATE,
        "discard_feerate_sat_per_vb": DISCARD_FEERATE,
        "dust_relay_feerate_sat_per_vb": DUST_RELAY_FEERATE,
        "target": {
            "value": 300_000,
            "n_outputs": 1,
            "non_input_weight": non_input_weight(1, TXOUT_P2TR_WEIGHT),
        },
        "change": {
            "output_weight": CHANGE_OUTPUT_WEIGHT,
            "spend_weight": CHANGE_SPEND_WEIGHT,
        },
        "max_weight": None,
        "candidates": [
            cand(0, 120_000, "p2wpkh", "sh"),
            cand(1, 90_000, "p2wpkh", "sh"),
            cand(2, 75_000, "p2tr", "sh"),
            cand(3, 210_000, "p2wpkh"),
            cand(4, 41_000, "p2pkh"),
            cand(5, 305_000, "p2wpkh", "rich"),
            cand(6, 60_000, "p2tr", "poor"),
            cand(7, 33_000, "p2wpkh"),
        ],
        # `rich` pays 4x the target rate on its own but hangs off an underpaying root, so its
        # package is still below target and it legitimately needs bumping.
        "ancestors": [
            anc("sh", 1200, underpaying_fee(1200, 1)),
            anc("root", 8000, underpaying_fee(8000, 1)),
            anc("rich", 800, (800 // 4) * FEERATE * 4, ["root"]),
            anc("poor", 1600, underpaying_fee(1600, 1), ["root"]),
        ],
    }
    return f


def validate(f: dict) -> None:
    name = f["name"]
    assert f["target"]["non_input_weight"] % 4 == 0, name
    assert f["change"]["output_weight"] % 4 == 0, name
    assert f["change"]["spend_weight"] % 4 == 0, name
    ids = set()
    txids = {a["txid"] for a in f["ancestors"]}
    assert len(txids) == len(f["ancestors"]), f"duplicate ancestor txid in {name}"
    for a in f["ancestors"]:
        assert a["weight"] % 4 == 0 and a["weight"] > 0, name
        assert a["fee"] >= 0, name
        for p in a["parents"]:
            assert p in txids, f"{name}: parent {p} not in ancestor set"
    # No cycles: a topological sort must consume everything.
    pending = {a["txid"]: set(a["parents"]) for a in f["ancestors"]}
    done = set()
    while pending:
        ready = [t for t, ps in pending.items() if ps <= done]
        assert ready, f"{name}: cycle in ancestor graph"
        for t in ready:
            done.add(t)
            del pending[t]
    for c in f["candidates"]:
        assert c["id"] not in ids, f"{name}: duplicate candidate id {c['id']}"
        ids.add(c["id"])
        assert c["input_weight"] % 4 == 0, name
        assert c["value"] > 0, name
        assert c["residing_txid"] is None or c["residing_txid"] in txids, name
    assert f["target"]["value"] > 0, name
    assert sum(c["value"] for c in f["candidates"]) > f["target"]["value"], (
        f"{name}: pool cannot cover the target"
    )
    # `AncestorToBump` means what it says: the caller passes the ancestors that still require
    # bumping, having already worked out which ones a miner would take anyway. An ancestor whose
    # package already clears the target feerate does not belong in the list, and putting one there
    # would credit the child with a surplus no miner is waiting on. Same determination Core's
    # `node::MiniMiner` makes, so both adapters see the same ancestor set.
    mined = bench.MiniMiner(f).in_block
    assert not mined, (
        f"{name}: {sorted(mined)} already meet the target feerate and must not be listed as "
        "needing a bump"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify fixtures/ is up to date")
    args = ap.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    fixtures = [build_smoke()]
    fixtures += [build(fam, n) for fam in FAMILIES for n in SIZES]

    stale = []
    for f in fixtures:
        validate(f)
        path = OUT_DIR / f"{f['name']}.json"
        blob = json.dumps(f, indent=1) + "\n"
        if args.check:
            if not path.exists() or path.read_text() != blob:
                stale.append(path.name)
        else:
            path.write_text(blob)

    if args.check:
        if stale:
            print("stale fixtures: " + ", ".join(stale), file=sys.stderr)
            return 1
        print(f"{len(fixtures)} fixtures up to date")
    else:
        print(f"wrote {len(fixtures)} fixtures to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
