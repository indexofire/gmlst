/**
 * Pure MST API client functions for the VisualApp.
 *
 * Each function performs a single HTTP POST to the Flask backend and returns
 * the parsed JSON response. Error handling (status check + message extraction)
 * is included. Vue reactive-state writes remain in App.vue's wrapper methods.
 */

/**
 * @param {string} endpoint
 * @param {object} payload
 * @returns {Promise<object>} parsed JSON response
 * @throws {Error} on network failure or non-2xx status
 */
async function postJson(endpoint, payload) {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "request failed");
  }
  return data;
}

/**
 * Build a minimum spanning tree from profile TSV.
 * @param {object} params
 * @returns {Promise<object>}
 */
export async function fetchMst({ tsv, metadataTsv, includeMissing, aggregateProfiles }) {
  return postJson("/api/mst", {
    tsv,
    metadata_tsv: metadataTsv,
    include_missing: includeMissing,
    aggregate_profiles: aggregateProfiles,
  });
}

/**
 * Build a pairwise distance matrix from profile TSV.
 * @param {object} params
 * @returns {Promise<object>}
 */
export async function fetchDistanceMatrix({ tsv, metadataTsv, includeMissing, aggregateProfiles }) {
  return postJson("/api/distance-matrix", {
    tsv,
    metadata_tsv: metadataTsv,
    include_missing: includeMissing,
    aggregate_profiles: aggregateProfiles,
  });
}

/**
 * Build an allele heatmap from profile TSV.
 * @param {object} params
 * @returns {Promise<object>}
 */
export async function fetchAlleleHeatmap({ tsv, metadataTsv, aggregateProfiles }) {
  return postJson("/api/allele-heatmap", {
    tsv,
    metadata_tsv: metadataTsv,
    aggregate_profiles: aggregateProfiles,
  });
}

/**
 * Compare two profile TSV results.
 * @param {object} params
 * @returns {Promise<object>}
 */
export async function fetchCompareResults({ leftTsv, rightTsv, metadataTsv }) {
  return postJson("/api/compare-results", {
    left_tsv: leftTsv,
    right_tsv: rightTsv,
    metadata_tsv: metadataTsv,
  });
}

/**
 * Compare loci between two samples.
 * @param {object} params
 * @returns {Promise<object>}
 */
export async function fetchCompareLoci({ tsv, metadataTsv, includeMissing, leftLabel, rightLabel }) {
  return postJson("/api/locus-diff", {
    tsv,
    metadata_tsv: metadataTsv,
    include_missing: includeMissing,
    left_label: leftLabel,
    right_label: rightLabel,
  });
}
