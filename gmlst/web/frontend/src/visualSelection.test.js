import test from "node:test";
import assert from "node:assert/strict";

import {
  availableClusterOptions,
  buildNodeInspection,
  compareStatusOptions,
  comparePayloadToJson,
  compareRequestFromSelection,
  compareSelectionFromPair,
  filterCompareRows,
  filterAlleleHeatmap,
  filterAlleleHeatmapLoci,
  filterDistanceMatrix,
  filterTableRows,
  filterRowsForSelection,
  filterRowsByCluster,
  heatmapPayloadToJson,
  heatmapToTsv,
  heatmapAnnotations,
  heatmapCellClass,
  matrixCellTitle,
  nextCompareSelection,
  selectedNodeId,
  sortTableRows,
  tableRowsToTsv,
  visibleTableColumns,
} from "./visualSelection.js";

test("selectedNodeId returns node id for node inspections", () => {
  assert.equal(selectedNodeId({ kind: "node", nodeId: 7 }), 7);
  assert.equal(selectedNodeId({ kind: "edge" }), null);
  assert.equal(selectedNodeId(null), null);
});

test("buildNodeInspection includes member and metadata details", () => {
  const inspection = buildNodeInspection({
    id: 3,
    label: "s1",
    member_count: 2,
    members: ["s1", "s2"],
    meta: { ST: "11", Country: "CN" },
  });

  assert.deepEqual(inspection, {
    kind: "node",
    title: "s1",
    lines: ["members: 2", "samples: s1, s2", "ST: 11", "Country: CN"],
    nodeId: 3,
  });
});

test("filterTableRows matches sample id, ST, member names, and metadata", () => {
  const rows = [
    {
      id: 1,
      sample_id: "sampleA",
      label: "sampleA",
      member_count: 1,
      members: ["sampleA"],
      profile_key: "1|1",
      meta: { ST: "11", Country: "CN" },
    },
    {
      id: 2,
      sample_id: "sampleB",
      label: "clusterB",
      member_count: 2,
      members: ["sampleB", "sampleC"],
      profile_key: "1|2",
      meta: { ST: "22", Country: "JP" },
    },
  ];

  assert.deepEqual(filterTableRows(rows, "samplea"), [rows[0]]);
  assert.deepEqual(filterTableRows(rows, "22"), [rows[1]]);
  assert.deepEqual(filterTableRows(rows, "samplec"), [rows[1]]);
  assert.deepEqual(filterTableRows(rows, "jp"), [rows[1]]);
  assert.deepEqual(filterTableRows(rows, ""), rows);
});

test("sortTableRows sorts string and numeric-like fields stably", () => {
  const rows = [
    { id: 1, sample_id: "sampleB", member_count: 2, meta: { ST: "12" } },
    { id: 2, sample_id: "sampleA", member_count: 1, meta: { ST: "2" } },
    { id: 3, sample_id: "sampleC", member_count: 3, meta: { ST: "11" } },
  ];

  assert.deepEqual(
    sortTableRows(rows, "sample_id", "asc").map((row) => row.id),
    [2, 1, 3],
  );
  assert.deepEqual(
    sortTableRows(rows, "member_count", "desc").map((row) => row.id),
    [3, 1, 2],
  );
  assert.deepEqual(
    sortTableRows(rows, "ST", "asc").map((row) => row.id),
    [2, 3, 1],
  );
});

test("visibleTableColumns includes base and metadata-derived columns", () => {
  assert.deepEqual(visibleTableColumns(["SCHEME", "ST", "Country", "Source"]), [
    { key: "sample_id", label: "Sample" },
    { key: "ST", label: "ST" },
    { key: "cluster_id", label: "Cluster" },
    { key: "member_count", label: "Members" },
    { key: "profile_key", label: "Profile" },
    { key: "SCHEME", label: "SCHEME" },
    { key: "Country", label: "Country" },
    { key: "Source", label: "Source" },
  ]);
});

test("filterRowsForSelection keeps only selected row when enabled", () => {
  const rows = [{ id: 1 }, { id: 2 }];
  assert.deepEqual(filterRowsForSelection(rows, 2, true), [{ id: 2 }]);
  assert.deepEqual(filterRowsForSelection(rows, 2, false), rows);
});

test("availableClusterOptions and filterRowsByCluster use cluster summary and row ids", () => {
  const summary = [
    { cluster_id: 0, sample_count: 2 },
    { cluster_id: 1, sample_count: 1 },
  ];
  const rows = [
    { id: 1, cluster_id: 0 },
    { id: 2, cluster_id: 1 },
  ];

  assert.deepEqual(availableClusterOptions(summary), [
    { value: "0", label: "Cluster 0 (2)" },
    { value: "1", label: "Cluster 1 (1)" },
  ]);
  assert.deepEqual(filterRowsByCluster(rows, "1"), [{ id: 2, cluster_id: 1 }]);
  assert.deepEqual(filterRowsByCluster(rows, ""), rows);
});

test("tableRowsToTsv exports visible columns and rows", () => {
  const rows = [
    {
      id: 1,
      sample_id: "sampleA",
      member_count: 1,
      profile_key: "1|1",
      meta: { ST: "11", Country: "CN" },
    },
  ];
  const columns = [
    { key: "sample_id", label: "Sample" },
    { key: "ST", label: "ST" },
    { key: "Country", label: "Country" },
  ];
  assert.equal(tableRowsToTsv(rows, columns), "Sample\tST\tCountry\nsampleA\t11\tCN\n");
});

test("filterDistanceMatrix narrows labels and matrix by cluster", () => {
  const labels = ["s1", "s2", "s3"];
  const matrix = [
    [0, 1, 2],
    [1, 0, 2],
    [2, 2, 0],
  ];
  const rows = [
    { cluster_id: 0 },
    { cluster_id: 0 },
    { cluster_id: 1 },
  ];

  assert.deepEqual(filterDistanceMatrix(labels, matrix, rows, "1"), {
    labels: ["s3"],
    matrix: [[0]],
  });
});

test("matrixCellTitle formats row/column/value tooltip text", () => {
  assert.equal(matrixCellTitle("s1", "s2", 3), "s1 ↔ s2: 3");
});

test("filterAlleleHeatmap narrows rows by cluster", () => {
  const labels = ["s1", "s2", "s3"];
  const loci = ["L1", "L2"];
  const cells = [[{ value: "1" }], [{ value: "2" }], [{ value: "3" }]];
  const rows = [
    { cluster_id: 0 },
    { cluster_id: 0 },
    { cluster_id: 1 },
  ];

  assert.deepEqual(filterAlleleHeatmap(labels, loci, cells, rows, "1"), {
    labels: ["s3"],
    loci: ["L1", "L2"],
    cells: [[{ value: "3" }]],
  });
});

test("heatmapCellClass maps state to CSS class", () => {
  assert.equal(heatmapCellClass("present_allele"), "heatmap-cell-present_allele");
  assert.equal(heatmapCellClass("missing_token"), "heatmap-cell-missing_token");
});

test("heatmapAnnotations derives row strip colors from current color mapping", () => {
  const labels = ["s1", "s2"];
  const rows = [
    { sample_id: "s1", cluster_id: 0, meta: { Country: "CN" } },
    { sample_id: "s2", cluster_id: 1, meta: { Country: "JP" } },
  ];
  const colorMap = new Map([
    ["CN", "#111111"],
    ["JP", "#222222"],
  ]);

  assert.deepEqual(heatmapAnnotations(labels, rows, "Country", colorMap), [
    { label: "s1", value: "CN", color: "#111111" },
    { label: "s2", value: "JP", color: "#222222" },
  ]);
});

test("filterAlleleHeatmapLoci narrows loci and cells by locus query", () => {
  const loci = ["L1", "abcZ", "gyrB"];
  const cells = [
    [{ value: "1" }, { value: "2" }, { value: "3" }],
    [{ value: "4" }, { value: "5" }, { value: "6" }],
  ];

  assert.deepEqual(filterAlleleHeatmapLoci(loci, cells, "gyr"), {
    loci: ["gyrB"],
    cells: [[{ value: "3" }], [{ value: "6" }]],
  });
  assert.deepEqual(filterAlleleHeatmapLoci(loci, cells, ""), { loci, cells });
});

test("nextCompareSelection rotates compare labels from current selection", () => {
  assert.deepEqual(nextCompareSelection("", "", "s1"), { left: "s1", right: "" });
  assert.deepEqual(nextCompareSelection("s1", "", "s2"), { left: "s1", right: "s2" });
  assert.deepEqual(nextCompareSelection("s1", "s2", "s3"), { left: "s2", right: "s3" });
});

test("comparePayloadToJson serializes current compare payload", () => {
  assert.equal(
    comparePayloadToJson({ left_label: "s1", right_label: "s2", distance: 2 }),
    '{\n  "left_label": "s1",\n  "right_label": "s2",\n  "distance": 2\n}',
  );
});

test("compareSelectionFromPair fills compare labels from a valid pair", () => {
  assert.deepEqual(compareSelectionFromPair("", "", "s1", "s2"), {
    left: "s1",
    right: "s2",
  });
  assert.deepEqual(compareSelectionFromPair("a", "b", "s1", "s1"), {
    left: "a",
    right: "b",
  });
});

test("compareRequestFromSelection returns null for invalid pairs and payload for valid ones", () => {
  assert.equal(compareRequestFromSelection("", "s2"), null);
  assert.equal(compareRequestFromSelection("s1", "s1"), null);
  assert.deepEqual(compareRequestFromSelection("s1", "s2"), {
    left_label: "s1",
    right_label: "s2",
  });
});

test("compareStatusOptions and filterCompareRows derive status filter state", () => {
  const rows = [
    { status: "same_st" },
    { status: "different_st" },
    { status: "left_only" },
    { status: "different_st" },
  ];

  assert.deepEqual(compareStatusOptions(rows), [
    { value: "different_st", label: "different_st" },
    { value: "left_only", label: "left_only" },
    { value: "same_st", label: "same_st" },
  ]);
  assert.deepEqual(filterCompareRows(rows, "different_st"), [
    { status: "different_st" },
    { status: "different_st" },
  ]);
});

test("heatmapToTsv exports current heatmap view", () => {
  const labels = ["s1", "s2"];
  const loci = ["L1", "L2"];
  const cells = [
    [{ value: "1" }, { value: "LNF" }],
    [{ value: "2" }, { value: "3" }],
  ];
  assert.equal(
    heatmapToTsv(labels, loci, cells),
    "Sample\tL1\tL2\ns1\t1\tLNF\ns2\t2\t3\n",
  );
});

test("heatmapPayloadToJson serializes heatmap payload", () => {
  assert.equal(
    heatmapPayloadToJson({ labels: ["s1"], loci: ["L1"], cells: [[{ value: "1" }]] }),
    '{\n  "labels": [\n    "s1"\n  ],\n  "loci": [\n    "L1"\n  ],\n  "cells": [\n    [\n      {\n        "value": "1"\n      }\n    ]\n  ]\n}',
  );
});
