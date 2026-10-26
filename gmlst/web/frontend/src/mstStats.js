/**
 * Pure aggregate statistics for the current MST payload.
 *
 * Extracted from App.vue so empty/single-node graphs and histogram
 * semantics are testable without mounting Vue.
 */

export function buildGraphStats(nodes, edges, options = {}) {
  if (!Array.isArray(nodes) || nodes.length === 0) {
    return null;
  }
  const safeEdges = Array.isArray(edges) ? edges : [];
  const weights = safeEdges
    .map((edge) => Number(edge.weight) || 0)
    .sort((left, right) => left - right);
  const n = weights.length;
  const q = (p) => (n === 0 ? 0 : weights[Math.min(n - 1, Math.floor(p * n))] || 0);
  const degreeMap = {};
  for (const edge of safeEdges) {
    degreeMap[edge.source] = (degreeMap[edge.source] || 0) + 1;
    degreeMap[edge.target] = (degreeMap[edge.target] || 0) + 1;
  }
  const nodeMap = new Map(nodes.map((node) => [String(node.id), node]));
  const topDegree = Object.entries(degreeMap)
    .sort((left, right) => right[1] - left[1])
    .slice(0, 10)
    .map(([id, degree]) => ({
      label: nodeMap.get(String(id))?.label || id,
      degree,
    }));

  const min = n > 0 ? weights[0] : 0;
  const max = n > 0 ? weights[n - 1] : 0;
  const bins = 20;
  const step = max === min ? 1 : (max - min) / bins;
  const counts = new Array(bins).fill(0);
  for (const weight of weights) {
    counts[Math.min(bins - 1, Math.floor((weight - min) / step))] += 1;
  }
  const histogram = counts
    .map((count, index) => ({
      label: `${Math.round(min + index * step)}–${Math.round(min + (index + 1) * step)}`,
      count,
      pct: n > 0 ? Math.round((count / n) * 100) : 0,
    }))
    .filter((bin) => bin.count > 0);
  const outliers = safeEdges
    .filter((edge) => (Number(edge.weight) || 0) > 50)
    .sort((left, right) => right.weight - left.weight)
    .slice(0, 5)
    .map((edge) => ({
      source: edge.source_label,
      target: edge.target_label,
      weight: edge.weight,
    }));

  return {
    nodeCount: nodes.length,
    edgeCount: safeEdges.length,
    weightMin: min,
    weightQ25: q(0.25),
    weightMedian: q(0.5),
    weightQ75: q(0.75),
    weightMax: max,
    zeroWeightCount: weights.filter((weight) => weight === 0).length,
    histogram,
    topDegree,
    outliers,
    clusterCount: Number(options.clusterCount) || 0,
    metadataFields: Array.isArray(options.metadataFields) ? options.metadataFields : [],
  };
}
