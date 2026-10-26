import test from "node:test";
import assert from "node:assert/strict";

import { buildGraphStats } from "./mstStats.js";

test("buildGraphStats returns null for an empty graph", () => {
  assert.equal(buildGraphStats([], []), null);
});

test("buildGraphStats supports a single-node MST", () => {
  const stats = buildGraphStats(
    [{ id: 0, label: "only", member_count: 1 }],
    [],
    { clusterCount: 1, metadataFields: ["Country"] },
  );
  assert.equal(stats.nodeCount, 1);
  assert.equal(stats.edgeCount, 0);
  assert.equal(stats.weightMin, 0);
  assert.equal(stats.weightMedian, 0);
  assert.deepEqual(stats.histogram, []);
  assert.equal(stats.clusterCount, 1);
  assert.deepEqual(stats.metadataFields, ["Country"]);
});

test("buildGraphStats computes weights for a two-node tree", () => {
  const stats = buildGraphStats(
    [
      { id: 0, label: "a", member_count: 1 },
      { id: 1, label: "b", member_count: 1 },
    ],
    [{ source: 0, target: 1, weight: 3 }],
  );
  assert.equal(stats.nodeCount, 2);
  assert.equal(stats.edgeCount, 1);
  assert.equal(stats.weightMax, 3);
  assert.equal(stats.zeroWeightCount, 0);
});
