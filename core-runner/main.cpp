// Fixture-driven runner for Bitcoin Core's wallet coin selection.
//
// Reads one fixture (see ../fixtures/README.md), runs one track, and writes a JSON result to
// stdout in the same shape as ../rust-runner, so ../bench.py can score both with one formula.
//
// Tracks:
//   wallet  Core's algorithm portfolio, replicating wallet/spend.cpp's ChooseSelectionResult:
//           BnB, KnapsackSolver, CoinGrinder (only above 3x the long-term feerate), SRD; then
//           the post-selection shared-ancestry bump discount; then pick the least waste.
//           The only track: the pinned coin-select revision has no changeless metric left, so
//           there is nothing to run SelectCoinsBnB against on its own.
//
// Everything from Core is used as-is at the pinned revision. The adapter's job is only to turn
// the fixture into COutputs and OutputGroups; every conversion it makes is listed in
// ../fixtures/README.md.

#include <wallet/coinselection.h>

#include <consensus/consensus.h>
#include <policy/feerate.h>
#include <policy/policy.h>
#include <primitives/transaction.h>
#include <random.h>
#include <uint256.h>
#include <univalue.h>
#include <util/translation.h>

#include <chrono>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <numeric>
#include <optional>
#include <sstream>
#include <string>
#include <sys/resource.h>
#include <vector>

#include "mini_miner_lite.h"

// util/check.h's internal-bug formatting reaches for this; the runner has no translations.
const TranslateFn G_TRANSLATION_FUN{nullptr};

namespace wallet {
// Published by patches/core-bench-hooks.patch; see patches/README.md.
extern size_t g_bnb_selections_evaluated;
extern bool g_bnb_algo_completed;
extern std::chrono::steady_clock::time_point g_bench_deadline;
} // namespace wallet

using namespace wallet;
using bench::AncestorTx;
using bench::MiniMinerLite;

namespace {

struct Candidate {
    std::string id;
    CAmount value{0};
    int64_t input_weight{0};
    bool is_segwit{false};
    std::string residing_txid; // empty means confirmed
};

struct Fixture {
    std::string name;
    std::string family;
    uint64_t seed{0};
    size_t search_budget{0};
    int64_t feerate_sat_per_vb{0};
    int64_t long_term_feerate_sat_per_vb{0};
    int64_t discard_feerate_sat_per_vb{0};
    int64_t dust_relay_feerate_sat_per_vb{0};
    CAmount target_value{0};
    int target_n_outputs{0};
    int64_t target_non_input_weight{0};
    int64_t change_output_weight{0};
    int64_t change_spend_weight{0};
    std::optional<int64_t> max_weight;
    std::vector<Candidate> candidates;
    std::vector<AncestorTx> ancestors;
};

[[noreturn]] void Die(const std::string& msg)
{
    std::cerr << "core-runner: " << msg << "\n";
    std::exit(1);
}

int64_t RequireMultipleOfFour(int64_t weight, const std::string& what)
{
    if (weight % 4 != 0) {
        Die(what + " must be a multiple of 4 weight units so Core's vbyte pricing and "
                   "coin-select's weight-unit pricing agree exactly (got " +
            std::to_string(weight) + ")");
    }
    return weight / 4;
}

Fixture LoadFixture(const std::string& path)
{
    std::ifstream in(path);
    if (!in) Die("cannot read fixture " + path);
    std::stringstream buffer;
    buffer << in.rdbuf();

    UniValue root;
    if (!root.read(buffer.str())) Die("cannot parse fixture " + path);

    Fixture f;
    f.name = root["name"].get_str();
    f.family = root["family"].get_str();
    f.seed = static_cast<uint64_t>(root["seed"].getInt<int64_t>());
    f.search_budget = static_cast<size_t>(root["search_budget"].getInt<int64_t>());
    f.feerate_sat_per_vb = root["feerate_sat_per_vb"].getInt<int64_t>();
    f.long_term_feerate_sat_per_vb = root["long_term_feerate_sat_per_vb"].getInt<int64_t>();
    f.discard_feerate_sat_per_vb = root["discard_feerate_sat_per_vb"].getInt<int64_t>();
    f.dust_relay_feerate_sat_per_vb = root["dust_relay_feerate_sat_per_vb"].getInt<int64_t>();

    const UniValue& target = root["target"];
    f.target_value = target["value"].getInt<int64_t>();
    f.target_n_outputs = static_cast<int>(target["n_outputs"].getInt<int64_t>());
    f.target_non_input_weight = target["non_input_weight"].getInt<int64_t>();

    const UniValue& change = root["change"];
    f.change_output_weight = change["output_weight"].getInt<int64_t>();
    f.change_spend_weight = change["spend_weight"].getInt<int64_t>();

    if (!root["max_weight"].isNull()) f.max_weight = root["max_weight"].getInt<int64_t>();

    for (const UniValue& c : root["candidates"].getValues()) {
        Candidate cand;
        cand.id = c["id"].get_str();
        cand.value = c["value"].getInt<int64_t>();
        cand.input_weight = c["input_weight"].getInt<int64_t>();
        cand.is_segwit = c["is_segwit"].get_bool();
        if (!c["residing_txid"].isNull()) cand.residing_txid = c["residing_txid"].get_str();
        f.candidates.push_back(cand);
    }
    for (const UniValue& a : root["ancestors"].getValues()) {
        AncestorTx tx;
        tx.txid = a["txid"].get_str();
        tx.vsize = RequireMultipleOfFour(a["weight"].getInt<int64_t>(), "ancestor weight");
        tx.fee = a["fee"].getInt<int64_t>();
        for (const UniValue& p : a["parents"].getValues()) tx.parents.push_back(p.get_str());
        f.ancestors.push_back(tx);
    }
    return f;
}

/// Everything the adapter derives from the fixture once, before any timed work.
struct Problem {
    CoinSelectionParams params;
    CAmount selection_target{0};   // recipient value plus the non-input fee
    int max_selection_weight{0};   // cap on the weight of the selected inputs
    std::vector<OutputGroup> all_groups;
    std::vector<OutputGroup> positive_groups;
    std::vector<std::shared_ptr<COutput>> outputs; // indexed like fixture.candidates
    std::unique_ptr<MiniMinerLite> mini_miner;

    explicit Problem(FastRandomContext& rng) : params(rng) {}
};

CFeeRate SatPerVb(int64_t sat_per_vb) { return CFeeRate(sat_per_vb * 1000); }

/// Every candidate gets the same dummy funding txid and its fixture index as the output number.
///
/// `COutput::operator<` orders by outpoint, so this also makes Core's `OutputSet` iterate in
/// fixture order, and makes translating a selection back to fixture ids a field read.
COutPoint OutpointFor(size_t index)
{
    return COutPoint{Txid::FromUint256(uint256::ONE), static_cast<uint32_t>(index)};
}

Problem BuildProblem(const Fixture& f, FastRandomContext& rng)
{
    Problem p(rng);
    p.params.m_effective_feerate = SatPerVb(f.feerate_sat_per_vb);
    p.params.m_long_term_feerate = SatPerVb(f.long_term_feerate_sat_per_vb);
    p.params.m_discard_feerate = SatPerVb(f.discard_feerate_sat_per_vb);
    p.params.change_output_size = static_cast<int>(RequireMultipleOfFour(f.change_output_weight, "change.output_weight"));
    p.params.change_spend_size = static_cast<int>(RequireMultipleOfFour(f.change_spend_weight, "change.spend_weight"));
    // Core's tx_noinputs_size carries the input-count varint (it assumes 1 vbyte); the shared
    // model in fixtures/README.md charges 4 WU for it, which is the same thing for any fixture
    // with at most 252 inputs. Adding it here is what makes both engines fund the same target.
    p.params.tx_noinputs_size = static_cast<int>(
        RequireMultipleOfFour(f.target_non_input_weight + 4, "target.non_input_weight"));
    p.params.m_subtract_fee_outputs = false;
    p.params.m_avoid_partial_spends = false; // one fixture candidate == one OutputGroup

    // wallet/spend.cpp CreateTransactionInternal, verbatim apart from the dust threshold, which
    // we take from the fixture's dust relay feerate over the change output plus its future input.
    p.params.m_change_fee = p.params.m_effective_feerate.GetFee(p.params.change_output_size);
    p.params.m_cost_of_change = p.params.m_discard_feerate.GetFee(p.params.change_spend_size) + p.params.m_change_fee;
    p.params.m_min_change_target = GenerateChangeTarget(f.target_value / std::max(1, f.target_n_outputs), p.params.m_change_fee, rng);
    const CAmount change_spend_fee = p.params.m_discard_feerate.GetFee(p.params.change_spend_size);
    const CAmount dust = SatPerVb(f.dust_relay_feerate_sat_per_vb).GetFee(p.params.change_output_size + p.params.change_spend_size);
    p.params.min_viable_change = std::max(change_spend_fee + 1, dust);
    if (f.max_weight) p.params.m_max_tx_weight = static_cast<int>(*f.max_weight);

    const CAmount not_input_fees = p.params.m_effective_feerate.GetFee(p.params.tx_noinputs_size);
    p.selection_target = f.target_value + not_input_fees;

    const int max_transaction_weight = p.params.m_max_tx_weight.value_or(MAX_STANDARD_TX_WEIGHT);
    p.max_selection_weight = max_transaction_weight - p.params.tx_noinputs_size * WITNESS_SCALE_FACTOR;
    if (p.max_selection_weight <= 0) Die("max_weight leaves no room for any input");

    // Individual ancestor bump fees, as wallet/spend.cpp's AvailableCoins would obtain them from
    // Chain::calculateIndividualBumpFees over every available coin at once.
    p.mini_miner = std::make_unique<MiniMinerLite>(f.ancestors, p.params.m_effective_feerate);
    if (!p.mini_miner->Mined().empty()) {
        std::string mined;
        for (const auto& txid : p.mini_miner->Mined()) mined += (mined.empty() ? "" : ", ") + txid;
        Die("fixture lists ancestors that already meet the target feerate and so need no bump: " +
            mined + ". See fixtures/README.md: the ancestor list is the set that requires bumping.");
    }

    for (size_t i = 0; i < f.candidates.size(); ++i) {
        const Candidate& c = f.candidates[i];
        const int input_bytes = static_cast<int>(RequireMultipleOfFour(c.input_weight, "candidate input_weight"));
        auto out = std::make_shared<COutput>(
            OutpointFor(i),
            CTxOut{c.value, CScript{}},
            /*depth=*/c.residing_txid.empty() ? 1 : 0,
            input_bytes,
            /*solvable=*/true,
            /*safe=*/true,
            /*time=*/0,
            /*from_me=*/true,
            p.params.m_effective_feerate);
        out->ApplyBumpFee(c.residing_txid.empty() ? 0 : p.mini_miner->IndividualBumpFee(c.residing_txid));
        p.outputs.push_back(out);

        OutputGroup group(p.params);
        group.Insert(out, /*ancestors=*/c.residing_txid.empty() ? 0 : 1, /*cluster_count=*/1);
        p.all_groups.push_back(group);
        if (group.GetSelectionAmount() > 0) p.positive_groups.push_back(group);
    }
    return p;
}

/// Fixture candidate index, as encoded by OutpointFor.
size_t IndexOf(const COutPoint& outpoint) { return static_cast<size_t>(outpoint.n); }

std::vector<std::string> SelectedIds(const Fixture& f, const SelectionResult& result)
{
    std::vector<size_t> indices;
    for (const auto& coin : result.GetInputSet()) indices.push_back(IndexOf(coin->outpoint));
    std::sort(indices.begin(), indices.end());
    std::vector<std::string> ids;
    for (size_t i : indices) ids.push_back(f.candidates.at(i).id);
    return ids;
}

/// Sum of the individual bump fees the search charged, and what the same ancestry really costs.
struct BumpFees {
    CAmount summed_individual{0};
    CAmount combined{0};
    /// `summed_individual - combined`, floored at zero: Core's `SetBumpFeeDiscount` rejects a
    /// negative discount, which the netting can produce when an unmined ancestor that overpays
    /// on its own is reachable through several selected coins.
    CAmount discount{0};
};

BumpFees BumpFeesFor(const Fixture& f, const Problem& p, const SelectionResult& result)
{
    BumpFees bump;
    std::vector<std::string> txids;
    for (const auto& coin : result.GetInputSet()) {
        if (coin->depth > 0) continue; // bump fees only exist for unconfirmed inputs
        bump.summed_individual += coin->ancestor_bump_fees;
        txids.push_back(f.candidates.at(IndexOf(coin->outpoint)).residing_txid);
    }
    bump.combined = p.mini_miner->CombinedBumpFee(txids);
    bump.discount = std::max<CAmount>(bump.summed_individual - bump.combined, 0);
    return bump;
}

/// Apply the shared-ancestry discount and recompute waste, as ChooseSelectionResult does.
void FinishResult(const Fixture& f, const Problem& p, SelectionResult& result)
{
    const BumpFees bump = BumpFeesFor(f, p, result);
    if (bump.discount > 0) result.SetBumpFeeDiscount(bump.discount);
    result.RecalculateWaste(p.params.min_viable_change, p.params.m_cost_of_change, p.params.m_change_fee);
}

/// Core's portfolio, exactly as wallet/spend.cpp's ChooseSelectionResult orders it.
std::optional<SelectionResult> RunWalletTrack(const Fixture& f, Problem& p)
{
    std::vector<SelectionResult> results;
    int max_selection_weight = p.max_selection_weight;

    auto positive = p.positive_groups;
    if (auto bnb = SelectCoinsBnB(positive, p.selection_target, p.params.m_cost_of_change, max_selection_weight)) {
        results.push_back(*bnb);
    }

    max_selection_weight -= p.params.change_output_size * WITNESS_SCALE_FACTOR;
    if (max_selection_weight < 0 && results.empty()) return std::nullopt;

    auto mixed = p.all_groups;
    if (auto knapsack = KnapsackSolver(mixed, p.selection_target, p.params.m_min_change_target, p.params.rng_fast, max_selection_weight)) {
        results.push_back(*knapsack);
    }

    if (p.params.m_effective_feerate > CFeeRate{3 * p.params.m_long_term_feerate}) {
        auto cg_pool = p.positive_groups;
        if (auto cg = CoinGrinder(cg_pool, p.selection_target, p.params.m_min_change_target, max_selection_weight)) {
            cg->RecalculateWaste(p.params.min_viable_change, p.params.m_cost_of_change, p.params.m_change_fee);
            results.push_back(*cg);
        }
    }

    if (auto srd = SelectCoinsSRD(p.positive_groups, p.selection_target, p.params.m_change_fee, p.params.rng_fast, max_selection_weight)) {
        results.push_back(*srd);
    }

    if (results.empty()) return std::nullopt;
    for (auto& result : results) FinishResult(f, p, result);
    return *std::min_element(results.begin(), results.end());
}

const char* AlgoName(SelectionAlgorithm algo)
{
    switch (algo) {
    case SelectionAlgorithm::BNB: return "bnb";
    case SelectionAlgorithm::KNAPSACK: return "knapsack";
    case SelectionAlgorithm::SRD: return "srd";
    case SelectionAlgorithm::CG: return "coingrinder";
    case SelectionAlgorithm::MANUAL: return "manual";
    }
    return "unknown";
}

int64_t PeakRssKb()
{
    struct rusage usage{};
    if (getrusage(RUSAGE_SELF, &usage) != 0) return -1;
    return usage.ru_maxrss; // Linux reports KiB
}

/// The worked example from the comment in Core's mini_miner.cpp, used to check the port.
///
/// Grandparent 1700 vB / 1700 sat (1 s/vB), parents 1 and 2 spending it at 85 and 15 s/vB, and a
/// child of both at 9 s/vB. Its ancestor-set feerate is 10.27 s/vB while its own is 9, which is
/// the case the `max(individual, ancestor-set)` rule exists for.
void SelfCheck()
{
    const std::vector<AncestorTx> txs{
        {"grandparent", 1700, 1700, {}},
        {"parent1", 200, 17000, {"grandparent"}},
        {"parent2", 200, 3000, {"grandparent"}},
        {"child", 100, 900, {"parent1", "parent2"}},
    };
    auto expect = [](const std::string& what, CAmount got, CAmount want) {
        if (got != want) {
            Die("self-check: " + what + " expected " + std::to_string(want) + ", got " + std::to_string(got));
        }
    };

    // Target 10 s/vB. The best ancestor-set feerate on offer is parent1's 9.84, below the target,
    // so the template is empty and nothing is free.
    MiniMinerLite at_target(txs, CFeeRate(10 * 1000));
    if (at_target.InBlock("grandparent")) Die("self-check: nothing should be mined at 10 sat/vB");
    // Ancestor set is already above the target (-600), so the child's own shortfall is what binds.
    expect("child bump at 10 sat/vB", at_target.IndividualBumpFee("child"), 10 * 100 - 900);
    expect("grandparent bump at 10 sat/vB", at_target.IndividualBumpFee("grandparent"), 10 * 1700 - 1700);
    // CalculateTotalBumpFees does not clamp: a package already above the target reports a
    // negative combined bump, which is what turns into an inflated discount in the wallet flow.
    expect("combined bump at 10 sat/vB", at_target.CombinedBumpFee({"child"}),
           10 * (1700 + 200 + 200 + 100) - (1700 + 17000 + 3000 + 900));

    // Target 20 s/vB: still nothing mined, and now the ancestor-set shortfall is what binds.
    MiniMinerLite steep(txs, CFeeRate(20 * 1000));
    expect("child bump at 20 sat/vB", steep.IndividualBumpFee("child"),
           20 * (1700 + 200 + 200 + 100) - (1700 + 17000 + 3000 + 900));

    // Target 1 s/vB: the grandparent package clears it, so the whole cluster is mined and free.
    MiniMinerLite cheap(txs, CFeeRate(1 * 1000));
    for (const auto& tx : txs) {
        if (!cheap.InBlock(tx.txid)) Die("self-check: " + tx.txid + " should be mined at 1 sat/vB");
        expect(tx.txid + " bump at 1 sat/vB", cheap.IndividualBumpFee(tx.txid), 0);
    }
    expect("combined bump at 1 sat/vB", cheap.CombinedBumpFee({"child", "grandparent"}), 0);

    std::cerr << "core-runner: self-check ok\n";
}

} // namespace

int main(int argc, char** argv)
{
    std::string fixture_path;
    std::string track = "wallet";
    int repeat = 5;
    int warmup = 1;
    int deadline_us = 0; // 0 = no deadline, stop on Core's node budget instead

    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        auto next = [&]() -> std::string {
            if (i + 1 >= argc) Die("missing value for " + arg);
            return argv[++i];
        };
        if (arg == "--fixture") fixture_path = next();
        else if (arg == "--track") track = next();
        else if (arg == "--repeat") repeat = std::max(1, std::stoi(next()));
        else if (arg == "--warmup") warmup = std::stoi(next());
        else if (arg == "--deadline-us") deadline_us = std::stoi(next());
        // Accepted and ignored: Core's oracle enumerated the changeless BnB window, which only
        // ever described the kernel track. The wallet portfolio has no single objective to
        // enumerate, and its results may carry change and so fall outside that window.
        else if (arg == "--oracle") {}
        else if (arg == "--self-check") { SelfCheck(); return 0; }
        else Die("unknown argument " + arg);
    }
    if (fixture_path.empty()) Die("--fixture is required");
    if (track != "wallet") Die("unknown track " + track);

    const Fixture f = LoadFixture(fixture_path);
    // Core's branch and bound budget (TOTAL_TRIES) is a compile-time constant. Fixtures state
    // the same number so both runners search under the same budget; refuse anything else rather
    // than silently comparing different budgets.
    if (deadline_us == 0 && f.search_budget != 100000) {
        Die("search_budget must be 100000 to match Core's compile-time TOTAL_TRIES (fixture says " +
            std::to_string(f.search_budget) + ")");
    }

    FastRandomContext rng{/*fDeterministic=*/true};
    Problem problem = BuildProblem(f, rng);

    // Timed region: the search only. Fixture parsing and problem construction sit outside it,
    // matching what the coin-select runner times. The pool is copied per repeat because Core's
    // algorithms sort it in place.
    std::vector<int64_t> samples;
    std::optional<SelectionResult> result;
    size_t bnb_nodes = 0;
    bool bnb_completed = false;
    for (int i = 0; i < warmup + repeat; ++i) {
        // Knapsack and single random draw consume the shared FastRandomContext, so without this
        // every repeat would search from a different random state and the reported selection
        // would depend on --repeat. Reseeding makes each repeat identical.
        rng.Reseed(uint256::ZERO);
        const auto start = std::chrono::steady_clock::now();
        // Give the search a wall-clock budget instead of a node budget when asked, so both
        // engines can be compared on the same termination criterion.
        g_bench_deadline = deadline_us > 0
            ? start + std::chrono::microseconds(deadline_us)
            : std::chrono::steady_clock::time_point{};
        std::optional<SelectionResult> attempt = RunWalletTrack(f, problem);
        const auto elapsed = std::chrono::steady_clock::now() - start;
        if (i >= warmup) samples.push_back(std::chrono::duration_cast<std::chrono::nanoseconds>(elapsed).count());
        // The portfolio starts with SelectCoinsBnB and nothing else writes these, so they still
        // describe this run's branch-and-bound search.
        bnb_nodes = g_bnb_selections_evaluated;
        bnb_completed = g_bnb_algo_completed;
        result = attempt;
    }

    std::sort(samples.begin(), samples.end());

    UniValue out(UniValue::VOBJ);
    out.pushKV("runner", "bitcoin-core");
    out.pushKV("fixture", f.name);
    out.pushKV("family", f.family);
    out.pushKV("size", static_cast<int64_t>(f.candidates.size()));
    out.pushKV("track", track);
    out.pushKV("objective", "least waste across Core's algorithm portfolio (ChooseSelectionResult)");
    out.pushKV("algorithm", result ? AlgoName(result->GetAlgo()) : "none");
    out.pushKV("ok", result.has_value());
    if (result) {
        out.pushKV("error", UniValue{});
    } else {
        out.pushKV("error", std::string{"no solution"});
    }

    UniValue selected(UniValue::VARR);
    if (result) for (const auto& id : SelectedIds(f, *result)) selected.push_back(id);
    out.pushKV("selected", selected);

    // Node counts only mean something for the two searches that have a node budget. Knapsack and
    // single random draw are reported as null rather than as a number that cannot be compared.
    const bool from_bnb = result && result->GetAlgo() == SelectionAlgorithm::BNB;
    if (from_bnb) {
        out.pushKV("rounds", static_cast<int64_t>(bnb_nodes));
        out.pushKV("exhausted", bnb_completed);
    } else if (result && result->GetAlgo() == SelectionAlgorithm::CG) {
        out.pushKV("rounds", static_cast<int64_t>(result->GetSelectionsEvaluated()));
        out.pushKV("exhausted", result->GetAlgoCompleted());
    } else {
        out.pushKV("rounds", UniValue{});
        out.pushKV("exhausted", UniValue{});
    }
    out.pushKV("budget", static_cast<int64_t>(f.search_budget));
    if (deadline_us > 0) out.pushKV("deadline_us", deadline_us); else out.pushKV("deadline_us", UniValue{});

    UniValue timing(UniValue::VOBJ);
    timing.pushKV("repeats", repeat);
    timing.pushKV("warmup", warmup);
    timing.pushKV("wall_ns_min", samples.front());
    timing.pushKV("wall_ns_median", samples[samples.size() / 2]);
    timing.pushKV("wall_ns_max", samples.back());
    out.pushKV("timing", timing);
    out.pushKV("peak_rss_kb", PeakRssKb());

    if (result) {
        const BumpFees bump = BumpFeesFor(f, problem, *result);
        const CAmount change = result->GetChange(problem.params.min_viable_change, problem.params.m_change_fee);
        UniValue native(UniValue::VOBJ);
        native.pushKV("waste", result->GetWaste());
        native.pushKV("selected_value", result->GetSelectedValue());
        native.pushKV("selected_effective_value", result->GetSelectedEffectiveValue());
        native.pushKV("selection_target", problem.selection_target);
        native.pushKV("input_weight", result->GetWeight());
        native.pushKV("change_value", change);
        native.pushKV("summed_individual_bump_fees", bump.summed_individual);
        native.pushKV("combined_bump_fee", bump.combined);
        native.pushKV("bump_fee_group_discount", bump.discount);
        native.pushKV("total_bump_fees", result->GetTotalBumpFees());
        out.pushKV("native", native);
    } else {
        out.pushKV("native", UniValue{});
    }

    // No oracle on this side: see the `--oracle` comment above.
    out.pushKV("oracle", UniValue{});
    std::cout << out.write() << "\n";
    return 0;
}
