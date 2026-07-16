import test from "node:test";
import assert from "node:assert/strict";

import {
  fetchMst,
  fetchDistanceMatrix,
  fetchAlleleHeatmap,
  fetchCompareResults,
  fetchCompareLoci,
} from "./mstApi.js";

function mockFetch(responseData, ok = true) {
  const calls = [];
  global.fetch = async (endpoint, options) => {
    calls.push({ endpoint, options });
    return {
      ok,
      json: async () => responseData,
    };
  };
  return calls;
}

test("fetchMst posts to /api/mst with correct payload", async () => {
  const calls = mockFetch({ nodes: [], edges: [] });
  await fetchMst({
    tsv: "data",
    metadataTsv: "",
    includeMissing: false,
    aggregateProfiles: true,
  });
  assert.equal(calls[0].endpoint, "/api/mst");
  assert.equal(calls[0].options.method, "POST");
  const body = JSON.parse(calls[0].options.body);
  assert.equal(body.tsv, "data");
  assert.equal(body.include_missing, false);
  assert.equal(body.aggregate_profiles, true);
});

test("fetchMst returns parsed response on success", async () => {
  mockFetch({ nodes: [{ id: 1 }], edges: [] });
  const result = await fetchMst({ tsv: "x" });
  assert.equal(result.nodes.length, 1);
});

test("fetchMst throws on non-ok response", async () => {
  mockFetch({ error: "bad data" }, false);
  await assert.rejects(
    () => fetchMst({ tsv: "x" }),
    /bad data/,
  );
});

test("fetchMst throws with default message when error field missing", async () => {
  mockFetch({}, false);
  await assert.rejects(
    () => fetchMst({ tsv: "x" }),
    /request failed/,
  );
});

test("fetchDistanceMatrix posts to correct endpoint", async () => {
  const calls = mockFetch({ labels: [], matrix: [] });
  await fetchDistanceMatrix({ tsv: "d" });
  assert.equal(calls[0].endpoint, "/api/distance-matrix");
});

test("fetchAlleleHeatmap posts to correct endpoint", async () => {
  const calls = mockFetch({ labels: [], loci: [], cells: [] });
  await fetchAlleleHeatmap({ tsv: "d" });
  assert.equal(calls[0].endpoint, "/api/allele-heatmap");
});

test("fetchCompareResults sends left and right TSV", async () => {
  const calls = mockFetch({ summary: {}, rows: [] });
  await fetchCompareResults({ leftTsv: "a", rightTsv: "b" });
  const body = JSON.parse(calls[0].options.body);
  assert.equal(body.left_tsv, "a");
  assert.equal(body.right_tsv, "b");
});

test("fetchCompareLoci sends labels", async () => {
  const calls = mockFetch({ differences: [] });
  await fetchCompareLoci({ tsv: "d", leftLabel: "s1", rightLabel: "s2" });
  const body = JSON.parse(calls[0].options.body);
  assert.equal(body.left_label, "s1");
  assert.equal(body.right_label, "s2");
});
