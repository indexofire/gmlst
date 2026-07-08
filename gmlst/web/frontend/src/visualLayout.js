/**
 * Pure layout and graph utilities used by the VisualApp Vue component.
 *
 * These functions never reference `this` and operate only on their arguments,
 * making them safe to unit test and easy to move out of the App.vue monolith.
 */

/** Default categorical color palette (60 colors). */
export const PALETTE = [
  "#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed",
  "#0891b2", "#ea580c", "#0284c7", "#4f46e5", "#db2777",
  "#059669", "#ca8a04", "#6366f1", "#be123c", "#0d9488",
  "#c2410c", "#4338ca", "#9333ea", "#15803d", "#b91c1c",
  "#0369a1", "#a21caf", "#4f46e5", "#b45309", "#0f766e",
  "#9a3412", "#6d28d9", "#be185d", "#166534", "#991b1b",
  "#1e40af", "#7e22ce", "#92400e", "#065f46", "#9f1239",
  "#1d4ed8", "#a855f7", "#65a30d", "#e11d48", "#0e7490",
  "#d946ef", "#84cc16", "#f43f5e", "#14b8a6", "#f97316",
  "#8b5cf6", "#22c55e", "#ef4444", "#06b6d4", "#eab308",
  "#ec4899", "#10b981", "#f59e0b", "#3b82f6", "#e879f9",
  "#34d399", "#fb923c", "#818cf8", "#f472b6", "#a3e635",
];

/** Named color schemes for categorical node coloring. */
export const COLOR_SCHEMES = {
  default: PALETTE,
  pastel: [
    "#a1c9f4", "#ffb482", "#8de5a1", "#ff9f9b", "#d0bbff",
    "#debb9b", "#fab0e4", "#cfcfcf", "#ff3154", "#9bf4d4",
    "#67d5cd", "#f7c0bb", "#96ceb4", "#ffeaa7", "#dfe6e9",
    "#fd79a8", "#6c5ce7", "#00b894", "#fdcb6e", "#e17055",
  ],
  vivid: [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
    "#911eb4", "#42d4f4", "#f032e6", "#bfef45", "#fabed4",
    "#469990", "#dcbeff", "#9a6324", "#fffac8", "#800000",
    "#aaffc3", "#808000", "#ffd8b1", "#000075", "#a9a9a9",
  ],
  warm: [
    "#e74c3c", "#e67e22", "#f39c12", "#d35400", "#c0392b",
    "#ff6b6b", "#ffa07a", "#ff8c42", "#e84393", "#fd79a8",
    "#fab1a0", "#f8a5c2", "#f78fb3", "#e77f67", "#cf6a87",
    "#c44569", "#f19066", "#f5cd79", "#e15f41", "#b33939",
  ],
  cool: [
    "#2980b9", "#27ae60", "#1abc9c", "#16a085", "#2ecc71",
    "#3498db", "#0984e3", "#00b894", "#6c5ce7", "#a29bfe",
    "#74b9ff", "#55efc4", "#81ecec", "#00cec9", "#0984e3",
    "#6a89cc", "#82ccdd", "#78e08f", "#b8e994", "#38ada9",
  ],
};

/** Horizontal center for radial layouts. */
export const LAYOUT_CENTER_X = 700;
/** Vertical center for radial layouts. */
export const LAYOUT_CENTER_Y = 450;
/** Maximum radius for radial layouts. */
export const LAYOUT_MAX_RADIUS = 380;

/**
 * Build an undirected edge key from two node identifiers.
 *
 * @param {number|string} source
 * @param {number|string} target
 * @returns {string}
 */
export function edgeKey(source, target) {
  const left = Math.min(source, target);
  const right = Math.max(source, target);
  return `${left}:${right}`;
}

/**
 * Compute the set of edge keys along the parent path from `nodeId` to the root.
 *
 * @param {number|string} nodeId
 * @param {Map} parentMap
 * @param {function} edgeKeyFn
 * @returns {Set<string>}
 */
export function highlightedPathEdges(nodeId, parentMap, edgeKeyFn) {
  const edgeKeys = new Set();
  let current = nodeId;
  while (parentMap.has(current) && parentMap.get(current) !== -1) {
    const parent = parentMap.get(current);
    edgeKeys.add(edgeKeyFn(current, parent));
    current = parent;
  }
  return edgeKeys;
}

/**
 * Compute the set of node ids along the parent path from `nodeId` to the root.
 *
 * @param {number|string} nodeId
 * @param {Map} parentMap
 * @returns {Set<number|string>}
 */
export function highlightedPathNodes(nodeId, parentMap) {
  const nodeIds = new Set([nodeId]);
  let current = nodeId;
  while (parentMap.has(current) && parentMap.get(current) !== -1) {
    const parent = parentMap.get(current);
    nodeIds.add(parent);
    current = parent;
  }
  return nodeIds;
}

/**
 * Extract the categorical value used to color a node.
 *
 * @param {object} node
 * @param {string} field
 * @returns {string}
 */
export function colorValueForNode(node, field) {
  if (!field) return "";
  return String(field === "cluster_id" ? node.cluster_id ?? "" : node.meta?.[field] ?? "");
}

/**
 * Convert a graph edge weight into a rendered length.
 *
 * @param {number|string} weight
 * @param {string} mode - "linear", "log", or "sqrt"
 * @param {number} scale
 * @returns {number}
 */
export function edgeLength(weight, mode, scale) {
  const w = Math.max(1, Number(weight) || 1);
  const s = Number(scale) || 50;
  if (mode === "log") {
    return s * Math.log2(w + 1);
  }
  if (mode === "sqrt") {
    return s * Math.sqrt(w);
  }
  return s * w;
}

/**
 * Return every descendant node id under `nodeId` according to `parentMap`.
 *
 * @param {number|string} nodeId
 * @param {Map} parentMap
 * @returns {Array<number|string>}
 */
export function getDescendants(nodeId, parentMap) {
  const children = new Map();
  for (const [childId, parentId] of parentMap.entries()) {
    if (parentId !== -1 && parentId !== undefined) {
      if (!children.has(parentId)) {
        children.set(parentId, []);
      }
      children.get(parentId).push(childId);
    }
  }
  const result = [];
  const queue = children.get(nodeId) || [];
  while (queue.length) {
    const id = queue.shift();
    result.push(id);
    const kids = children.get(id);
    if (kids) {
      queue.push(...kids);
    }
  }
  return result;
}

/**
 * Parse a non-negative integer weight ceiling from user input.
 *
 * @param {string|number|null|undefined} rawString
 * @returns {number|null}
 */
export function parseMaxWeight(rawString) {
  const raw = String(rawString ?? "").trim();
  if (!raw) {
    return null;
  }
  const parsed = Number(raw);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return null;
  }
  return Math.floor(parsed);
}

/**
 * Aggregate nodes that share the same profile key and collapse parallel edges.
 *
 * @param {Array<object>} nodes
 * @param {Array<object>} edges
 * @returns {{nodes: Array<object>, edges: Array<object>}}
 */
export function aggregateGraph(nodes, edges) {
  const groupByKey = new Map();
  const nodeToGroup = new Map();

  for (const node of nodes) {
    const key = node.profile_key || `id:${node.id}`;
    if (!groupByKey.has(key)) {
      groupByKey.set(key, []);
    }
    groupByKey.get(key).push(node);
  }

  const aggNodes = [];
  let groupId = 0;
  for (const members of groupByKey.values()) {
    const first = members[0];
    const label =
      members.length === 1
        ? first.label
        : `${first.label} (+${members.length - 1})`;
    const aggNode = {
      id: groupId,
      label,
      meta: first.meta || {},
      member_count: members.length,
    };
    aggNodes.push(aggNode);
    for (const member of members) {
      nodeToGroup.set(member.id, groupId);
    }
    groupId += 1;
  }

  const edgeMap = new Map();
  for (const edge of edges) {
    const source = nodeToGroup.get(edge.source);
    const target = nodeToGroup.get(edge.target);
    if (source === undefined || target === undefined || source === target) {
      continue;
    }
    const left = Math.min(source, target);
    const right = Math.max(source, target);
    const key = `${left}:${right}`;
    const previous = edgeMap.get(key);
    if (!previous || edge.weight < previous.weight) {
      edgeMap.set(key, {
        source: left,
        target: right,
        weight: edge.weight,
      });
    }
  }

  return {
    nodes: aggNodes,
    edges: Array.from(edgeMap.values()),
  };
}

/**
 * Determine which nodes should be collapsed given manual + threshold rules.
 *
 * @param {Array<object>} nodes
 * @param {Array<object>} edges
 * @param {Map} parentMap
 * @param {object} collapsedNodes
 * @param {number} threshold
 * @param {function} edgeKeyFn
 * @returns {Set<string>}
 */
export function resolveCollapsedNodeSet(
  nodes,
  edges,
  parentMap,
  collapsedNodes,
  threshold,
  edgeKeyFn,
) {
  const manual = new Set(
    Object.keys(collapsedNodes || {}).filter((id) => collapsedNodes[id]),
  );
  if (threshold <= 0 || !nodes.length || !edges.length || !parentMap) {
    return manual;
  }
  const edgeByKey = new Map();
  for (const edge of edges) {
    edgeByKey.set(edgeKeyFn(edge.source, edge.target), edge);
  }
  for (const node of nodes) {
    if (manual.has(String(node.id))) {
      continue;
    }
    const parentId = parentMap.get(node.id);
    if (parentId === undefined || parentId === -1) {
      continue;
    }
    const edge = edgeByKey.get(edgeKeyFn(node.id, parentId));
    if (edge && Number(edge.weight) > threshold) {
      manual.add(String(parentId));
    }
  }
  return manual;
}

/**
 * Filter edges by an upper weight bound.
 *
 * @param {Array<object>} edges
 * @param {number|null} maxWeight
 * @returns {Array<object>}
 */
export function filteredEdges(edges, maxWeight) {
  if (maxWeight === null || maxWeight === undefined) {
    return edges;
  }
  return edges.filter((edge) => Number(edge.weight) <= maxWeight);
}

/**
 * Compute the rendered radius for a node.
 *
 * @param {object} node
 * @param {boolean} scaleNodeSize
 * @returns {number}
 */
export function nodeRadius(node, scaleNodeSize) {
  const count = Number(node.member_count || 1);
  if (!scaleNodeSize) {
    return count > 1 ? 11 : 8;
  }
  return Math.min(22, 7 + Math.sqrt(Math.max(1, count)) * 3);
}

/**
 * Build the inline style object for a legend item chip.
 *
 * @param {object} item
 * @param {object} hiddenLegendValues
 * @returns {object}
 */
export function legendItemStyle(item, hiddenLegendValues) {
  const isHidden = hiddenLegendValues[item.value];
  return {
    background: isHidden ? "#e2e8f0" : `${item.color}18`,
    borderColor: isHidden ? "#cbd5e1" : `${item.color}66`,
    color: isHidden ? "#94a3b8" : "#1f2937",
    cursor: "pointer",
  };
}

/**
 * Map categorical field values to colors.
 *
 * @param {Array<object>} nodes
 * @param {string} colorField
 * @param {string} schemeName
 * @returns {Map<string, string>}
 */
export function colorMapFor(nodes, colorField, schemeName) {
  if (!colorField) {
    return new Map();
  }
  const activePalette = COLOR_SCHEMES[schemeName] || PALETTE;
  const counts = new Map();
  for (const node of nodes) {
    const value = colorField === "cluster_id" ? String(node.cluster_id) : node.meta?.[colorField];
    if (value) {
      counts.set(value, (counts.get(value) || 0) + 1);
    }
  }
  const values = Array.from(counts.entries())
    .sort((left, right) => {
      if (right[1] !== left[1]) {
        return right[1] - left[1];
      }
      return left[0].localeCompare(right[0]);
    })
    .map(([value]) => value);
  const mapping = new Map();
  values.forEach((value, index) => {
    if (index < activePalette.length) {
      mapping.set(value, activePalette[index]);
    } else {
      const hue = (index * 137.508) % 360;
      const chroma = 60 + (index % 3) * 15;
      const luminance = 50 + (index % 4) * 5;
      mapping.set(value, `hcl(${hue}, ${chroma}%, ${luminance}%)`);
    }
  });
  return mapping;
}

/**
 * Assign radial positions to tree nodes using a greedy angle-allocation strategy.
 *
 * @param {Array<object>} nodes
 * @param {Array<object>} edges
 * @param {number|string} rootId
 * @param {Map} depthMap
 * @returns {Map<number|string, [number, number]>}
 */
export function greedyRadialLayout(nodes, edges, rootId, depthMap) {
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const children = new Map(nodes.map((node) => [node.id, []]));
  const parentMap = new Map();

  for (const edge of edges) {
    if (depthMap.get(edge.source) < depthMap.get(edge.target)) {
      children.get(edge.source)?.push(edge.target);
      parentMap.set(edge.target, edge.source);
    } else if (depthMap.get(edge.target) < depthMap.get(edge.source)) {
      children.get(edge.target)?.push(edge.source);
      parentMap.set(edge.source, edge.target);
    }
  }

  children.forEach((childList) => {
    childList.sort((left, right) => {
      const leftCount = Number(nodeById.get(left)?.member_count || 1);
      const rightCount = Number(nodeById.get(right)?.member_count || 1);
      return rightCount - leftCount;
    });
  });

  const leafCount = new Map();
  const computeLeaves = (nodeId) => {
    const kids = children.get(nodeId) || [];
    if (kids.length === 0) {
      leafCount.set(nodeId, 1);
      return 1;
    }
    let total = 0;
    for (const kid of kids) {
      total += computeLeaves(kid);
    }
    leafCount.set(nodeId, total);
    return total;
  };

  const roots = [rootId];
  for (const node of nodes) {
    if (!parentMap.has(node.id) && node.id !== rootId) {
      roots.push(node.id);
    }
  }

  const uniqueRoots = [...new Set(roots.filter((nodeId) => nodeById.has(nodeId)))];
  for (const nodeId of uniqueRoots) {
    computeLeaves(nodeId);
  }

  const nodeAngles = new Map();
  const nodeRadii = new Map();
  const maxWeightedDepth = Math.max(...nodes.map((node) => depthMap.get(node.id) || 0), 1);
  const maxRadius = LAYOUT_MAX_RADIUS;

  const assignAngles = (nodeId, startAngle, endAngle) => {
    nodeAngles.set(nodeId, (startAngle + endAngle) / 2);
    nodeRadii.set(nodeId, ((depthMap.get(nodeId) || 0) / maxWeightedDepth) * maxRadius);

    const kids = children.get(nodeId) || [];
    if (kids.length === 0) {
      return;
    }

    const totalLeaves = leafCount.get(nodeId) || kids.length;
    let currentAngle = startAngle;

    for (const kid of kids) {
      const kidLeaves = leafCount.get(kid) || 1;
      const kidSpan = (endAngle - startAngle) * (kidLeaves / totalLeaves);
      assignAngles(kid, currentAngle, currentAngle + kidSpan);
      currentAngle += kidSpan;
    }
  };

  if (uniqueRoots.length === 1) {
    assignAngles(uniqueRoots[0], 0, 2 * Math.PI);
  } else {
    const rootSpan = (2 * Math.PI) / uniqueRoots.length;
    uniqueRoots.forEach((nodeId, index) => {
      assignAngles(nodeId, index * rootSpan, (index + 1) * rootSpan);
    });
  }

  const centerX = LAYOUT_CENTER_X;
  const centerY = LAYOUT_CENTER_Y;
  const positions = new Map();
  for (const node of nodes) {
    const angle = (nodeAngles.get(node.id) || 0) - Math.PI / 2;
    const radius = nodeRadii.get(node.id) || 0;
    positions.set(node.id, [
      centerX + radius * Math.cos(angle),
      centerY + radius * Math.sin(angle),
    ]);
  }

  return positions;
}

/**
 * Adjust radial positions so children lie on concentric depth rings.
 *
 * @param {Array<object>} nodes
 * @param {Array<object>} edges
 * @param {Map} positions
 * @param {Map} depthMap
 * @returns {Map<number|string, [number, number]>}
 */
export function correctBranchLengths(nodes, edges, positions, depthMap) {
  const parentMap = new Map();
  const kids = new Map(nodes.map((node) => [node.id, []]));

  for (const edge of edges) {
    if (depthMap.get(edge.source) < depthMap.get(edge.target)) {
      parentMap.set(edge.target, { id: edge.source, weight: edge.weight });
      kids.get(edge.source)?.push(edge.target);
    } else if (depthMap.get(edge.target) < depthMap.get(edge.source)) {
      parentMap.set(edge.source, { id: edge.target, weight: edge.weight });
      kids.get(edge.target)?.push(edge.source);
    }
  }

  const roots = nodes.filter((node) => !parentMap.has(node.id));
  if (!roots.length) {
    return positions;
  }

  const maxWeightedDepth = Math.max(...nodes.map((node) => depthMap.get(node.id) || 0), 1);
  const maxRadius = LAYOUT_MAX_RADIUS;
  const centerX = LAYOUT_CENTER_X;
  const centerY = LAYOUT_CENTER_Y;
  const order = [];
  const visited = new Set();

  for (const root of roots) {
    if (visited.has(root.id)) {
      continue;
    }
    visited.add(root.id);
    const queue = [root.id];
    while (queue.length) {
      const current = queue.shift();
      order.push(current);
      for (const child of kids.get(current) || []) {
        if (!visited.has(child)) {
          visited.add(child);
          queue.push(child);
        }
      }
    }
  }

  const corrected = new Map(positions);
  for (let iteration = 0; iteration < 6; iteration += 1) {
    for (const current of order) {
      const parentInfo = parentMap.get(current);
      if (!parentInfo) {
        continue;
      }

      const parentPos = corrected.get(parentInfo.id);
      const currentPos = corrected.get(current);
      if (!parentPos || !currentPos) {
        continue;
      }

      const targetDist = ((depthMap.get(current) || 0) / maxWeightedDepth) * maxRadius;
      const dx = currentPos[0] - centerX;
      const dy = currentPos[1] - centerY;
      const angle = Math.atan2(dy, dx);
      const currentDist = Math.sqrt(dx * dx + dy * dy);

      if (Math.abs(currentDist - targetDist) > 2) {
        corrected.set(current, [
          centerX + targetDist * Math.cos(angle),
          centerY + targetDist * Math.sin(angle),
        ]);
      }
    }
  }

  return corrected;
}

/**
 * Recursively build a Newick string from a rooted tree.
 *
 * @param {number|string} nodeId
 * @param {number|string|null} parent
 * @param {Map} weightMap
 * @param {Map} childrenMap
 * @param {Set} visited
 * @param {Array<object>} nodes
 * @returns {string}
 */
export function buildNewick(nodeId, parent, weightMap, childrenMap, visited, nodes) {
  visited.add(nodeId);
  const kids = childrenMap.get(nodeId) || [];
  const label = nodes.find((n) => n.id === nodeId)?.label || String(nodeId);
  const childNewicks = [];
  for (const kidId of kids) {
    if (!visited.has(kidId)) {
      childNewicks.push(buildNewick(kidId, nodeId, weightMap, childrenMap, visited, nodes));
    }
  }
  let result = "";
  if (childNewicks.length > 0) {
    result += `(${childNewicks.join(",")})`;
  }
  result += String(label).replace(/[\s()[\]{}:;,]/g, "_");
  if (parent !== null) {
    const w = weightMap.get(String(nodeId));
    if (w !== undefined) {
      result += `:${Number(w).toFixed(2)}`;
    }
  }
  return result;
}
