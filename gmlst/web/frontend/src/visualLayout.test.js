import test from "node:test";
import assert from "node:assert/strict";

import {
  edgeKey,
  highlightedPathEdges,
  highlightedPathNodes,
  colorValueForNode,
  edgeLength,
  getDescendants,
  parseMaxWeight,
  aggregateGraph,
  resolveCollapsedNodeSet,
  filteredEdges,
  grapetreeGap,
  nodeRadius,
  nodeShapePath,
  legendItemStyle,
  colorMapFor,
  COLOR_SCHEMES,
  PALETTE,
  greedyRadialLayout,
  correctBranchLengths,
  buildNewick,
} from "./visualLayout.js";

test("edgeKey builds an undirected key regardless of argument order", () => {
  assert.equal(edgeKey(1, 2), "1:2");
  assert.equal(edgeKey(2, 1), "1:2");
  assert.equal(edgeKey(10, 5), "5:10");
});

test("highlightedPathEdges collects edge keys along the parent chain", () => {
  const parentMap = new Map([
    [3, 2],
    [2, 1],
    [1, -1],
  ]);
  const keys = highlightedPathEdges(3, parentMap, edgeKey);
  assert.deepEqual(keys, new Set(["2:3", "1:2"]));
  assert.equal(highlightedPathEdges(1, parentMap, edgeKey).size, 0);
});

test("highlightedPathNodes collects node ids along the parent chain", () => {
  const parentMap = new Map([
    [3, 2],
    [2, 1],
    [1, -1],
  ]);
  assert.deepEqual(highlightedPathNodes(3, parentMap), new Set([3, 2, 1]));
  assert.deepEqual(highlightedPathNodes(1, parentMap), new Set([1]));
});

test("colorValueForNode reads cluster_id or metadata fields", () => {
  const node = { cluster_id: 5, meta: { Country: "CN" } };
  assert.equal(colorValueForNode(node, "Country"), "CN");
  assert.equal(colorValueForNode(node, "cluster_id"), "5");
  assert.equal(colorValueForNode(node, ""), "");
  assert.equal(colorValueForNode({ meta: {} }, "Country"), "");
});

test("edgeLength scales weights according to the chosen mode", () => {
  assert.equal(edgeLength(2, "linear", 50), 100);
  assert.equal(edgeLength(0, "linear", 50), 50);
  assert.ok(Math.abs(edgeLength(2, "log", 50) - 50 * Math.log2(3)) < 1e-9);
  assert.ok(Math.abs(edgeLength(4, "sqrt", 50) - 50 * Math.sqrt(4)) < 1e-9);
  assert.equal(edgeLength("3", "linear", 50), 150);
});

test("getDescendants returns all ids under a node", () => {
  const parentMap = new Map([
    [1, 0],
    [2, 1],
    [3, 1],
    [0, -1],
  ]);
  assert.deepEqual(getDescendants(0, parentMap), [1, 2, 3]);
  assert.deepEqual(getDescendants(1, parentMap), [2, 3]);
  assert.deepEqual(getDescendants(3, parentMap), []);
});

test("parseMaxWeight parses non-negative integers from raw input", () => {
  assert.equal(parseMaxWeight("10"), 10);
  assert.equal(parseMaxWeight("  4  "), 4);
  assert.equal(parseMaxWeight(3.7), 3);
  assert.equal(parseMaxWeight(""), null);
  assert.equal(parseMaxWeight("abc"), null);
  assert.equal(parseMaxWeight("-5"), null);
  assert.equal(parseMaxWeight(null), null);
});

test("aggregateGraph groups identical profiles and keeps the lightest edge", () => {
  const nodes = [
    { id: 1, label: "A", profile_key: "p1", meta: {} },
    { id: 2, label: "B", profile_key: "p1", meta: {} },
    { id: 3, label: "C", profile_key: "p2", meta: {} },
  ];
  const edges = [
    { source: 1, target: 3, weight: 5 },
    { source: 2, target: 3, weight: 2 },
  ];
  const aggregated = aggregateGraph(nodes, edges);
  assert.equal(aggregated.nodes.length, 2);
  assert.equal(aggregated.nodes[0].member_count, 2);
  assert.equal(aggregated.nodes[0].label, "A (+1)");
  assert.equal(aggregated.edges.length, 1);
  assert.equal(aggregated.edges[0].weight, 2);
});

test("aggregateGraph ignores self-loops after aggregation", () => {
  const nodes = [
    { id: 1, label: "A", profile_key: "p1", meta: {} },
    { id: 2, label: "B", profile_key: "p1", meta: {} },
  ];
  const edges = [{ source: 1, target: 2, weight: 1 }];
  const aggregated = aggregateGraph(nodes, edges);
  assert.equal(aggregated.nodes.length, 1);
  assert.equal(aggregated.edges.length, 0);
});

test("resolveCollapsedNodeSet returns manual collapses when threshold is off", () => {
  const nodes = [{ id: 1 }, { id: 2 }];
  const edges = [{ source: 1, target: 2, weight: 1 }];
  const parentMap = new Map([[2, 1], [1, -1]]);
  const collapsed = { 2: true };
  const set = resolveCollapsedNodeSet(nodes, edges, parentMap, collapsed, 0, edgeKey);
  assert.deepEqual(set, new Set(["2"]));
});

test("resolveCollapsedNodeSet adds parents whose edge weight exceeds threshold", () => {
  const nodes = [{ id: 1 }, { id: 2 }];
  const edges = [{ source: 1, target: 2, weight: 5 }];
  const parentMap = new Map([[2, 1], [1, -1]]);
  const set = resolveCollapsedNodeSet(nodes, edges, parentMap, {}, 3, edgeKey);
  assert.deepEqual(set, new Set(["1"]));
});

test("resolveCollapsedNodeSet does not auto-collapse when threshold is zero", () => {
  const nodes = [{ id: 1 }, { id: 2 }];
  const edges = [{ source: 1, target: 2, weight: 5 }];
  const parentMap = new Map([[2, 1], [1, -1]]);
  const set = resolveCollapsedNodeSet(nodes, edges, parentMap, {}, 0, edgeKey);
  assert.deepEqual(set, new Set([]));
});

test("filteredEdges passes edges through or filters by max weight", () => {
  const edges = [
    { source: 1, target: 2, weight: 1 },
    { source: 2, target: 3, weight: 3 },
    { source: 3, target: 4, weight: 5 },
  ];
  assert.equal(filteredEdges(edges, null).length, 3);
  assert.equal(filteredEdges(edges, 2).length, 1);
  assert.deepEqual(filteredEdges(edges, 2), [edges[0]]);
  assert.equal(filteredEdges(edges, 0).length, 0);
});

test("nodeRadius respects the scale flag and clamps large counts", () => {
  assert.equal(nodeRadius({ member_count: 1 }, false), 8);
  assert.equal(nodeRadius({ member_count: 2 }, false), 11);
  assert.equal(nodeRadius({ member_count: 1 }, true), 7 + Math.sqrt(1) * 4.5);
  assert.equal(nodeRadius({ member_count: 100 }, true), 26);
});

test("legendItemStyle dims hidden legend values", () => {
  const item = { value: "X", color: "#ff0000" };
  assert.deepEqual(legendItemStyle(item, { X: true }), {
    background: "#e2e8f0",
    borderColor: "#cbd5e1",
    color: "#94a3b8",
    cursor: "pointer",
  });
  assert.deepEqual(legendItemStyle(item, {}), {
    background: "#ff000018",
    borderColor: "#ff000066",
    color: "#1f2937",
    cursor: "pointer",
  });
});

test("colorMapFor assigns colors by frequency and supports schemes", () => {
  const nodes = [
    { meta: { Country: "CN" } },
    { meta: { Country: "CN" } },
    { meta: { Country: "JP" } },
  ];
  const map = colorMapFor(nodes, "Country", "default");
  assert.equal(map.get("CN"), PALETTE[0]);
  assert.equal(map.get("JP"), PALETTE[1]);
});

test("colorMapFor falls back to generated colors for many values", () => {
  const count = PALETTE.length + 1;
  const nodes = Array.from({ length: count }, (_, index) => ({
    meta: { Group: `G${String(index).padStart(2, "0")}` },
  }));
  const map = colorMapFor(nodes, "Group", "default");
  const lastValue = `G${String(PALETTE.length).padStart(2, "0")}`;
  const lastColor = map.get(lastValue);
  assert.ok(lastColor.startsWith("hcl("));
});

test("colorMapFor selects the requested color scheme", () => {
  const nodes = [{ meta: { Country: "CN" } }];
  const map = colorMapFor(nodes, "Country", "pastel");
  assert.equal(map.get("CN"), COLOR_SCHEMES.pastel[0]);
});

test("greedyRadialLayout assigns a position to every node", () => {
  const nodes = [
    { id: 0, member_count: 1 },
    { id: 1, member_count: 1 },
    { id: 2, member_count: 1 },
  ];
  const edges = [
    { source: 0, target: 1, weight: 1 },
    { source: 0, target: 2, weight: 1 },
  ];
  const depthMap = new Map([[0, 0], [1, 1], [2, 1]]);
  const positions = greedyRadialLayout(nodes, edges, 0, depthMap);
  assert.equal(positions.size, 3);
  for (const position of positions.values()) {
    assert.equal(position.length, 2);
  }
  const [rootX, rootY] = positions.get(0);
  assert.equal(rootX, 700);
  assert.equal(rootY, 450);
});

test("correctBranchLengths snaps children to target depth rings", () => {
  const nodes = [
    { id: 0, member_count: 1 },
    { id: 1, member_count: 1 },
  ];
  const edges = [{ source: 0, target: 1, weight: 1 }];
  const depthMap = new Map([[0, 0], [1, 1]]);
  const positions = new Map([
    [0, [700, 450]],
    [1, [700, 500]],
  ]);
  const corrected = correctBranchLengths(nodes, edges, positions, depthMap);
  const [x, y] = corrected.get(1);
  const distance = Math.hypot(x - 700, y - 450);
  assert.equal(distance, 380);
});

test("buildNewick builds a recursive Newick string", () => {
  const nodes = [
    { id: 0, label: "A" },
    { id: 1, label: "B" },
    { id: 2, label: "C" },
  ];
  const childrenMap = new Map([
    [0, [1, 2]],
    [1, []],
    [2, []],
  ]);
  const weightMap = new Map([
    ["1", 2.5],
    ["2", 3.5],
  ]);
  const newick = buildNewick(0, null, weightMap, childrenMap, new Set(), nodes);
  assert.equal(newick, "(B:2.50,C:3.50)A");
});

test("buildNewick sanitizes labels and handles leaf nodes", () => {
  const nodes = [{ id: 0, label: "sample 1" }];
  const childrenMap = new Map([[0, []]]);
  const weightMap = new Map();
  const leaf = buildNewick(0, 1, weightMap, childrenMap, new Set(), nodes);
  assert.equal(leaf, "sample_1");
});

test("greedyRadialLayout keeps zero-weight subtrees in the tree (no crossings)", () => {
  // 0-1 and 1-2 are identical profiles (weight 0), so equal accumulated
  // depths. A depth-comparison hierarchy dropped them and produced
  // crossing chords; BFS parentage must keep every node attached.
  const nodes = [0, 1, 2, 3, 4, 5].map((id) => ({ id, member_count: 1 }));
  const edges = [
    { source: 0, target: 1, weight: 0 },
    { source: 1, target: 2, weight: 1 },
    { source: 0, target: 3, weight: 2 },
    { source: 3, target: 4, weight: 0 },
    { source: 3, target: 5, weight: 3 },
  ];
  const depthMap = new Map([[0, 0], [1, 0], [2, 1], [3, 2], [4, 2], [5, 5]]);
  const positions = greedyRadialLayout(nodes, edges, 0, depthMap);

  assert.equal(positions.size, 6);
  for (const position of positions.values()) {
    assert.ok(Number.isFinite(position[0]) && Number.isFinite(position[1]));
  }

  // No two rendered edges may properly cross.
  const segments = edges.map((edge) => {
    const a = positions.get(edge.source);
    const b = positions.get(edge.target);
    return [a, b];
  });
  const orient = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  const proper = (a, b, c, d) =>
    orient(a, b, c) * orient(a, b, d) < 0 && orient(c, d, a) * orient(c, d, b) < 0;
  for (let i = 0; i < segments.length; i += 1) {
    for (let j = i + 1; j < segments.length; j += 1) {
      const [a, b] = segments[i];
      const [c, d] = segments[j];
      const shares = [a, b].some((p) => [c, d].some((q) => p[0] === q[0] && p[1] === q[1]));
      if (shares) continue;
      assert.ok(!proper(a, b, c, d), `edges ${i} and ${j} cross`);
    }
  }
});

test("grapetreeGap is zero for identical profiles and scales with the slider", () => {
  assert.equal(grapetreeGap(0, 500, "linear"), 0);
  assert.equal(grapetreeGap(0, 500, "log"), 0);
  const base = grapetreeGap(50, 500, "log", 1);
  assert.ok(Math.abs(grapetreeGap(50, 500, "log", 2) - base * 2) < 1e-9);
  assert.ok(grapetreeGap(50, 500, "log", 0.5) < base);
});

test("grapetreeGap keeps the mode's proportionality and caps at max_link_scale", () => {
  // Linear: gap is proportional to the allele distance.
  assert.equal(grapetreeGap(5, 500, "linear"), 5);
  assert.equal(grapetreeGap(250, 500, "linear"), 250);
  assert.equal(grapetreeGap(500, 500, "linear"), 500);
  // The largest branch always maps onto GrapeTree's 500-unit link scale.
  assert.equal(grapetreeGap(9999, 500, "linear"), 500);
  assert.equal(grapetreeGap(9999, 500, "sqrt"), 500);
  assert.ok(Math.abs(grapetreeGap(9999, 500, "log") - 500) < 1e-9);
  // Log compresses the 1 vs 500 spread to a legible ratio.
  const ratio = grapetreeGap(500, 500, "log") / grapetreeGap(1, 500, "log");
  assert.ok(ratio > 5 && ratio < 12, `ratio was ${ratio}`);
});

test("buildNewick handles deep chains without overflowing the stack", () => {
  const depth = 20000;
  const nodes = Array.from({ length: depth }, (_, index) => ({
    id: index,
    label: `S${index}`,
  }));
  const children = new Map();
  const weights = new Map();
  for (let index = 1; index < depth; index += 1) {
    children.set(index - 1, [index]);
    weights.set(String(index), 1);
  }
  const newick = buildNewick(0, null, weights, children, new Set(), nodes);
  assert.ok(newick.startsWith("("));
  assert.ok(newick.includes("S19999:1.00"));
  assert.ok(newick.endsWith("S0"));
});

test("nodeShapePath draws every shape around the local origin", () => {
  for (let index = 0; index < 5; index += 1) {
    const path = nodeShapePath(index, 10);
    const numbers = (path.match(/-?\d+(\.\d+)?/g) || []).map(Number);
    assert.ok(numbers.length > 0);
    assert.ok(
      numbers.every((value) => Math.abs(value) <= 30),
      `shape ${index} is not centred on the node: ${path}`,
    );
  }
  assert.ok(nodeShapePath(1, 10).startsWith("M-9,-9"));
});
