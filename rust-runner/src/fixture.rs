//! The shared fixture format. See `../../fixtures/README.md` for the schema and semantics.

use std::collections::HashMap;

use serde::Deserialize;

/// `residing_txid` sentinel for a candidate whose funding transaction is confirmed.
///
/// `SelectionProblem::new` treats a txid it has no ancestor entry for as confirmed, so any
/// value outside the ancestor set works; this one is just unmistakable in a debugger.
pub const CONFIRMED: u32 = u32::MAX;

#[derive(Deserialize)]
pub struct Fixture {
    pub name: String,
    pub family: String,
    pub seed: u64,
    pub search_budget: usize,
    pub feerate_sat_per_vb: f64,
    pub long_term_feerate_sat_per_vb: f64,
    pub dust_relay_feerate_sat_per_vb: f64,
    pub target: FixtureTarget,
    pub change: FixtureChange,
    pub max_weight: Option<u64>,
    pub candidates: Vec<FixtureCandidate>,
    pub ancestors: Vec<FixtureAncestor>,
}

#[derive(Deserialize)]
pub struct FixtureTarget {
    pub value: u64,
    pub n_outputs: usize,
    pub non_input_weight: u64,
}

#[derive(Deserialize)]
pub struct FixtureChange {
    pub output_weight: u64,
    pub spend_weight: u64,
}

#[derive(Deserialize)]
pub struct FixtureCandidate {
    pub id: String,
    pub value: u64,
    pub input_weight: u64,
    pub is_segwit: bool,
    pub residing_txid: Option<String>,
}

#[derive(Deserialize)]
pub struct FixtureAncestor {
    pub txid: String,
    pub weight: u64,
    pub fee: u64,
    pub parents: Vec<String>,
}

impl Fixture {
    pub fn load(path: &str) -> Self {
        let blob = std::fs::read_to_string(path)
            .unwrap_or_else(|e| panic!("cannot read fixture {path}: {e}"));
        serde_json::from_str(&blob)
            .unwrap_or_else(|e| panic!("cannot parse fixture {path}: {e}"))
    }

    /// Ancestor txids mapped to the dense indices the crate is keyed by.
    pub fn txid_index(&self) -> HashMap<&str, u32> {
        self.ancestors
            .iter()
            .enumerate()
            .map(|(i, a)| (a.txid.as_str(), i as u32))
            .collect()
    }
}

/// Byte length of the varint encoding `v`, as the crate's own (private) helper computes it.
pub fn varint_size(v: usize) -> u64 {
    if v <= 0xfc {
        1
    } else if v <= 0xffff {
        3
    } else if v <= 0xffff_ffff {
        5
    } else {
        9
    }
}
