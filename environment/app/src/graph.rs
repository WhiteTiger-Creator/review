//! Generic directed-graph helpers (neutral infrastructure; no policy semantics).

#![allow(dead_code)]

use std::collections::{BTreeMap, BTreeSet, VecDeque};

/// Return one directed cycle as sorted unique node IDs, or `None` if acyclic.
///
/// Edge meaning is caller-defined. Detection walks adjacency built from
/// `(from, to)` pairs. When multiple cycles exist, the first cycle discovered
/// by DFS discovery order is returned after unique-member UTF-8 sort.
pub fn find_directed_cycle(edges: &[(String, String)]) -> Option<Vec<String>> {
    let mut adj: BTreeMap<String, Vec<String>> = BTreeMap::new();
    let mut nodes: BTreeSet<String> = BTreeSet::new();
    for (a, b) in edges {
        nodes.insert(a.clone());
        nodes.insert(b.clone());
        adj.entry(a.clone()).or_default().push(b.clone());
    }
    for n in &nodes {
        adj.entry(n.clone()).or_default();
    }

    let mut visited: BTreeSet<String> = BTreeSet::new();
    let mut stack: BTreeSet<String> = BTreeSet::new();
    let mut path: Vec<String> = Vec::new();

    fn dfs(
        node: &str,
        adj: &BTreeMap<String, Vec<String>>,
        visited: &mut BTreeSet<String>,
        stack: &mut BTreeSet<String>,
        path: &mut Vec<String>,
    ) -> Option<Vec<String>> {
        if stack.contains(node) {
            let start = path.iter().position(|x| x == node).unwrap_or(0);
            let mut cycle: Vec<String> = path[start..].to_vec();
            cycle.sort();
            cycle.dedup();
            return Some(cycle);
        }
        if visited.contains(node) {
            return None;
        }
        visited.insert(node.to_string());
        stack.insert(node.to_string());
        path.push(node.to_string());
        if let Some(nexts) = adj.get(node) {
            for nxt in nexts {
                if let Some(c) = dfs(nxt, adj, visited, stack, path) {
                    return Some(c);
                }
            }
        }
        path.pop();
        stack.remove(node);
        None
    }

    for n in &nodes {
        if let Some(c) = dfs(n, &adj, &mut visited, &mut stack, &mut path) {
            return Some(c);
        }
    }
    None
}

/// Deterministic Kahn topological order.
///
/// Among ready nodes, the caller-supplied `cmp` decides which node is selected
/// next. Returns `Ok(order)` or `Err(sorted_remaining)` when a cycle remains.
pub fn topo_sort_with<F>(
    nodes: &[String],
    edges: &[(String, String)],
    mut cmp: F,
) -> Result<Vec<String>, Vec<String>>
where
    F: FnMut(&str, &str) -> std::cmp::Ordering,
{
    let mut indeg: BTreeMap<String, usize> = BTreeMap::new();
    let mut adj: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for n in nodes {
        indeg.entry(n.clone()).or_insert(0);
        adj.entry(n.clone()).or_default();
    }
    for (a, b) in edges {
        indeg.entry(b.clone()).or_insert(0);
        indeg.entry(a.clone()).or_insert(0);
        *indeg.get_mut(b).unwrap() += 1;
        adj.entry(a.clone()).or_default().push(b.clone());
    }

    let mut ready: Vec<String> = indeg
        .iter()
        .filter(|(_, d)| **d == 0)
        .map(|(k, _)| k.clone())
        .collect();
    ready.sort_by(|a, b| cmp(a, b));

    let mut order = Vec::new();
    let mut queue: VecDeque<String> = ready.into();
    while let Some(n) = queue.pop_front() {
        order.push(n.clone());
        let mut unlocked = Vec::new();
        if let Some(nexts) = adj.get(&n) {
            for nxt in nexts {
                let d = indeg.get_mut(nxt).unwrap();
                *d -= 1;
                if *d == 0 {
                    unlocked.push(nxt.clone());
                }
            }
        }
        unlocked.sort_by(|a, b| cmp(a, b));
        // merge unlocked into queue keeping relative order via re-sort of ready set
        let mut rest: Vec<String> = queue.drain(..).collect();
        rest.extend(unlocked);
        rest.sort_by(|a, b| cmp(a, b));
        queue = rest.into();
    }

    if order.len() != indeg.len() {
        let mut remaining: Vec<String> = indeg
            .keys()
            .filter(|k| !order.contains(k))
            .cloned()
            .collect();
        remaining.sort();
        return Err(remaining);
    }
    Ok(order)
}
