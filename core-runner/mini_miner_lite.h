// Ancestor bump fees, computed the way Bitcoin Core's node::MiniMiner computes them.
//
// Core's wallet never asks "what does this ancestor set owe at the target feerate?" directly.
// It builds a mock block template over the relevant mempool cluster, ancestor-feerate greedy,
// and stops at the target feerate. Anything that made it into the template is free; anything
// left over is charged. That is *not* the same as `max(0, rate * weight - fee)` over the set,
// which is what bdk_coin_select's `CoinSelector::ancestor_bump` computes.
//
// This is a port of src/node/mini_miner.cpp from the pinned Core revision, restricted to what
// the benchmark needs and driven by the fixture's ancestor graph instead of a live CTxMemPool.
// Deviations from Core, all forced by not having a mempool:
//
//   - The fixture's ancestor list *is* the mempool. Core would also pull in unrelated
//     descendants that share a cluster; a fixture has no such transactions.
//   - Entries are keyed by fixture txid string, not by Txid. Core breaks ancestor-feerate ties
//     on txid; we break them on the fixture txid, so ties resolve by fixture order rather than
//     by hash order. Ties only arise between exactly equal feerates.
//   - No to-be-replaced transactions: a fixture ancestor is never conflicted.
//
// Cross-checked two ways: `bench.py` reimplements this independently in Python and asserts the
// numbers agree, and `--self-check` runs the worked example from Core's own source comment.

#ifndef COINSELECT_BENCH_MINI_MINER_LITE_H
#define COINSELECT_BENCH_MINI_MINER_LITE_H

#include <policy/feerate.h>

#include <algorithm>
#include <cstdint>
#include <map>
#include <set>
#include <string>
#include <vector>

namespace bench {

struct AncestorTx {
    std::string txid;
    int64_t vsize{0};
    CAmount fee{0};
    std::vector<std::string> parents;
};

/// Core's FeeFrac ordering: compare fee1/size1 against fee2/size2 without dividing.
inline bool FeerateLess(CAmount fee_a, int64_t size_a, CAmount fee_b, int64_t size_b)
{
    return static_cast<__int128>(fee_a) * size_b < static_cast<__int128>(fee_b) * size_a;
}

class MiniMinerLite
{
public:
    /// Build the mock block template for `target_feerate` over the whole ancestor set.
    ///
    /// One template answers every later question, exactly as in Core: the individual bump fee
    /// of a transaction and the combined bump fee of a set are both read off the same template.
    MiniMinerLite(const std::vector<AncestorTx>& txs, const CFeeRate& target_feerate)
        : m_target_feerate(target_feerate)
    {
        for (const auto& tx : txs) {
            Entry entry;
            entry.vsize = tx.vsize;
            entry.fee = tx.fee;
            entry.parents = tx.parents;
            m_entries.emplace(tx.txid, entry);
        }
        // Transitive ancestor totals (inclusive), and the inclusive descendant sets that
        // DeleteAncestorPackage decrements.
        for (auto& [txid, entry] : m_entries) {
            const std::set<std::string> ancestors = Closure(txid, /*upwards=*/true);
            for (const auto& a : ancestors) {
                entry.anc_vsize += m_entries.at(a).vsize;
                entry.anc_fee += m_entries.at(a).fee;
                m_descendants[a].insert(txid);
            }
        }
        BuildMockTemplate();
    }

    /// Whether `txid` made it into the mock template, i.e. owes nothing.
    bool InBlock(const std::string& txid) const { return m_in_block.count(txid) > 0; }

    /// The bump fee Core would charge a single UTXO residing in `txid`.
    ///
    /// `max` of the individual and ancestor-set shortfalls: a transaction has to clear the
    /// target feerate both on its own and together with everything it depends on.
    CAmount IndividualBumpFee(const std::string& txid) const
    {
        if (InBlock(txid)) return 0;
        auto it = m_entries.find(txid);
        if (it == m_entries.end()) return 0; // confirmed, or not in the fixture's mempool
        const CAmount with_ancestors = m_target_feerate.GetFee(it->second.anc_vsize) - it->second.anc_fee;
        const CAmount individual = m_target_feerate.GetFee(it->second.vsize) - it->second.fee;
        return std::max<CAmount>(std::max(with_ancestors, individual), 0);
    }

    /// The bump fee Core would charge for spending UTXOs residing in all of `txids` at once.
    ///
    /// The union of their still-unmined ancestors is charged once, netted, with no clamp at
    /// zero — matching `MiniMiner::CalculateTotalBumpFees`.
    CAmount CombinedBumpFee(const std::vector<std::string>& txids) const
    {
        std::set<std::string> unmined;
        for (const auto& txid : txids) {
            if (InBlock(txid) || !m_entries.count(txid)) continue;
            for (const auto& a : Closure(txid, /*upwards=*/true)) {
                if (!InBlock(a)) unmined.insert(a);
            }
        }
        int64_t vsize = 0;
        CAmount fee = 0;
        for (const auto& txid : unmined) {
            vsize += m_entries.at(txid).vsize;
            fee += m_entries.at(txid).fee;
        }
        if (unmined.empty()) return 0;
        return m_target_feerate.GetFee(vsize) - fee;
    }

private:
    struct Entry {
        int64_t vsize{0};
        CAmount fee{0};
        std::vector<std::string> parents;
        int64_t anc_vsize{0};
        CAmount anc_fee{0};
    };

    /// Transitive closure of `txid` over parents (inclusive of `txid` itself).
    ///
    /// `upwards` exists only to keep the direction explicit at the call sites; the graph has no
    /// child edges, so it is always true.
    std::set<std::string> Closure(const std::string& txid, bool upwards) const
    {
        (void)upwards;
        std::set<std::string> seen;
        std::vector<std::string> stack{txid};
        while (!stack.empty()) {
            const std::string current = stack.back();
            stack.pop_back();
            auto it = m_entries.find(current);
            if (it == m_entries.end()) continue; // parent outside the fixture: confirmed
            if (!seen.insert(current).second) continue;
            for (const auto& parent : it->second.parents) stack.push_back(parent);
        }
        return seen;
    }

    /// Same loop as `MiniMiner::BuildMockTemplate`, without the block-size limit Core also
    /// does not apply here.
    void BuildMockTemplate()
    {
        std::map<std::string, Entry> live = m_entries;
        while (!live.empty()) {
            // Pick the entry with the highest min(own feerate, ancestor-set feerate).
            const std::string* best = nullptr;
            for (const auto& [txid, entry] : live) {
                if (best == nullptr) {
                    best = &txid;
                    continue;
                }
                const Entry& b = live.at(*best);
                if (MinFeerateGreater(entry, b)) best = &txid;
            }
            const Entry& best_entry = live.at(*best);
            // Stop as soon as the best remaining package is below the target: everything left
            // over is what needs bumping.
            if (best_entry.anc_fee < m_target_feerate.GetFee(best_entry.anc_vsize)) break;

            // "Mine" the whole ancestor package of the winner.
            std::set<std::string> package;
            for (const auto& a : Closure(*best, true)) {
                if (live.count(a)) package.insert(a);
            }
            for (const auto& txid : package) {
                m_in_block.insert(txid);
                for (const auto& descendant : m_descendants.at(txid)) {
                    auto it = live.find(descendant);
                    if (it == live.end()) continue;
                    it->second.anc_vsize -= live.at(txid).vsize;
                    it->second.anc_fee -= live.at(txid).fee;
                }
            }
            for (const auto& txid : package) live.erase(txid);
        }
        // Keep the residual ancestor totals so IndividualBumpFee reads the same numbers Core's
        // post-template entries hold.
        for (auto& [txid, entry] : m_entries) {
            if (m_in_block.count(txid)) continue;
            entry.anc_vsize = 0;
            entry.anc_fee = 0;
            for (const auto& a : Closure(txid, true)) {
                if (m_in_block.count(a)) continue;
                entry.anc_vsize += m_entries.at(a).vsize;
                entry.anc_fee += m_entries.at(a).fee;
            }
        }
    }

    /// `a` sorts before `b` under Core's AncestorFeerateComparator (higher first, txid tie-break
    /// handled by the caller iterating a std::map in txid order).
    static bool MinFeerateGreater(const Entry& a, const Entry& b)
    {
        auto min_of = [](const Entry& e) -> std::pair<CAmount, int64_t> {
            if (FeerateLess(e.anc_fee, e.anc_vsize, e.fee, e.vsize)) return {e.anc_fee, e.anc_vsize};
            return {e.fee, e.vsize};
        };
        const auto [fee_a, size_a] = min_of(a);
        const auto [fee_b, size_b] = min_of(b);
        return FeerateLess(fee_b, size_b, fee_a, size_a);
    }

    CFeeRate m_target_feerate;
    std::map<std::string, Entry> m_entries;
    std::map<std::string, std::set<std::string>> m_descendants;
    std::set<std::string> m_in_block;
};

} // namespace bench

#endif // COINSELECT_BENCH_MINI_MINER_LITE_H
