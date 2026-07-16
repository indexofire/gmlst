import test from "node:test";
import assert from "node:assert/strict";

import { parseSessionState } from "./sessionPersistence.js";

test("parseSessionState returns defaults for empty payload", () => {
  const state = parseSessionState({});
  assert.equal(state.tsvText, "");
  assert.equal(state.metadataText, "");
  assert.equal(state.layoutMode, "tree");
  assert.equal(state.edgeLengthMode, "linear");
  assert.equal(state.edgeLengthScale, 50);
  assert.equal(state.showEdgeLabels, true);
  assert.equal(state.lastData, null);
});

test("parseSessionState extracts inputs from payload", () => {
  const state = parseSessionState({
    inputs: { tsv: "data", metadata_tsv: "meta" },
  });
  assert.equal(state.tsvText, "data");
  assert.equal(state.metadataText, "meta");
});

test("parseSessionState maps snake_case options to camelCase state", () => {
  const state = parseSessionState({
    options: {
      include_missing: true,
      aggregate_profiles: false,
      layout_mode: "radial",
      edge_length_scale: 75,
      color_by: "species",
      max_weight: "100",
    },
  });
  assert.equal(state.includeMissing, true);
  assert.equal(state.aggregateProfiles, false);
  assert.equal(state.layoutMode, "radial");
  assert.equal(state.edgeLengthScale, 75);
  assert.equal(state.colorBy, "species");
  assert.equal(state.edgeWeightThreshold, 100);
});

test("parseSessionState extracts response data", () => {
  const state = parseSessionState({
    response: {
      metadata_fields: ["country"],
      matrix: [[0, 5], [5, 0]],
      labels: ["s1", "s2"],
      loci: ["abc", "def"],
      cells: [[{ value: "1" }, { value: "2" }]],
    },
  });
  assert.deepEqual(state.metadataFields, ["country"]);
  assert.deepEqual(state.matrixLabels, ["s1", "s2"]);
  assert.deepEqual(state.distanceMatrix, [[0, 5], [5, 0]]);
  assert.deepEqual(state.heatmapLoci, ["abc", "def"]);
  assert.equal(state.heatmapCells.length, 1);
});

test("parseSessionState handles null response gracefully", () => {
  const state = parseSessionState({ response: null });
  assert.deepEqual(state.metadataFields, []);
  assert.deepEqual(state.tableRows, []);
  assert.equal(state.lastData, null);
});
