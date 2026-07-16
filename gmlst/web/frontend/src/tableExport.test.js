import test from "node:test";
import assert from "node:assert/strict";

import {
  buildGraphJsonPayload,
  buildSessionJsonPayload,
  buildNewickString,
  newickBlob,
} from "./tableExport.js";

test("buildGraphJsonPayload wraps graph with schema and source", () => {
  const graph = { nodes: [{ id: 1 }], edges: [] };
  const result = buildGraphJsonPayload("v2", graph);
  assert.equal(result.schema_version, "v2");
  assert.equal(result.exported_from, "gmlst visual");
  assert.equal(result.graph, graph);
});

test("buildGraphJsonPayload uses default schema version", () => {
  const result = buildGraphJsonPayload(null, {});
  assert.equal(result.schema_version, "gmlst-visual-v1");
});

test("buildGraphJsonPayload accepts custom source", () => {
  const result = buildGraphJsonPayload(null, {}, "custom");
  assert.equal(result.exported_from, "custom");
});

test("buildSessionJsonPayload extracts state fields", () => {
  const state = {
    tsvText: "tsv",
    metadataText: "meta",
    analysisView: "matrix",
    includeMissing: true,
    aggregateProfiles: false,
    overlapRelief: true,
    layoutMode: "radial",
    edgeLengthMode: "log",
    edgeLengthScale: 50,
    longBranchMode: "normal",
    longBranchThreshold: 0,
    colorBy: "country",
    maxWeight: "",
    collapsedNodes: {},
    collapseThreshold: 0,
    hiddenLegendValues: {},
    nodeSearchQuery: "",
    showEdgeLabels: false,
    scaleNodeSize: true,
    aggregateNodes: false,
    correctnessOverlay: true,
    manualRootId: null,
    viewFilterMode: "all",
    clusterFilter: "",
    nodePositionOverrides: {},
    hiddenNodeIds: {},
    customNodeColors: {},
    lastData: { export: { schema_version: "v3" } },
  };
  const result = buildSessionJsonPayload(state);
  assert.equal(result.schema_version, "v3");
  assert.equal(result.inputs.tsv, "tsv");
  assert.equal(result.inputs.metadata_tsv, "meta");
  assert.equal(result.options.analysis_view, "matrix");
  assert.equal(result.options.include_missing, true);
  assert.equal(result.options.aggregate_profiles, false);
});

test("buildSessionJsonPayload uses default schema when lastData missing", () => {
  const result = buildSessionJsonPayload({ lastData: null });
  assert.equal(result.schema_version, "gmlst-visual-v1");
});

test("buildNewickString returns null for empty parent map", () => {
  const layout = { parent: new Map() };
  const graph = { nodes: [], edges: [] };
  assert.equal(buildNewickString(layout, graph), null);
});

test("buildNewickString builds tree from single root", () => {
  const parent = new Map([
    [0, -1],
    [1, 0],
    [2, 0],
  ]);
  const layout = { parent };
  const graph = {
    nodes: [
      { id: 0, label: "root" },
      { id: 1, label: "a" },
      { id: 2, label: "b" },
    ],
    edges: [
      { source: 1, target: 0, weight: 3 },
      { source: 2, target: 0, weight: 5 },
    ],
  };
  const result = buildNewickString(layout, graph);
  assert.ok(result);
  assert.ok(result.endsWith(";"));
});

test("newickBlob creates a text/plain blob", () => {
  const blob = newickBlob("(A,B);");
  assert.equal(blob.type, "text/plain;charset=utf-8");
});
