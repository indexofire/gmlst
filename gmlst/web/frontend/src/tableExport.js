/**
 * Pure export helpers used by the VisualApp Vue component.
 *
 * These functions never reference `this` and operate only on their arguments,
 * making them safe to unit test and easy to move out of the App.vue monolith.
 */

import { buildNewick } from "./visualLayout.js";
import {
  comparePayloadToJson,
  heatmapPayloadToJson,
  heatmapToTsv,
  tableRowsToTsv,
} from "./visualSelection.js";

/**
 * Trigger a browser download for a blob or string payload.
 *
 * @param {string} filename
 * @param {Blob|string} content
 * @param {string} [mimeType="application/octet-stream"]
 */
export function downloadBlob(filename, content, mimeType = "application/octet-stream") {
  const blob = content instanceof Blob ? content : new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

/**
 * Serialize an SVG element to a string with an XML declaration.
 *
 * @param {SVGSVGElement} svgElement
 * @returns {string}
 */
export function serializeSvg(svgElement) {
  const serializer = new XMLSerializer()
  const raw = serializer.serializeToString(svgElement)
  return `<?xml version="1.0" encoding="UTF-8"?>\n${raw}`
}

/**
 * Build a Blob from an SVG element.
 *
 * @param {SVGSVGElement} svgElement
 * @returns {Blob}
 */
export function svgBlob(svgElement) {
  return new Blob([serializeSvg(svgElement)], { type: "image/svg+xml;charset=utf-8" })
}

/**
 * Trigger a JSON download.
 *
 * @param {string} filename
 * @param {object} payload
 */
export function downloadJson(filename, payload) {
  downloadBlob(filename, JSON.stringify(payload, null, 2), "application/json;charset=utf-8")
}

/**
 * Build a Newick string from a rendered graph layout.
 *
 * @param {object} layout
 * @param {object} renderedGraph
 * @returns {string|null}
 */
export function buildNewickString(layout, renderedGraph) {
  const parentMap = layout.parent
  const childrenMap = new Map()
  for (const [nodeId, parentId] of parentMap) {
    if (parentId !== -1 && parentId !== undefined) {
      if (!childrenMap.has(parentId)) {
        childrenMap.set(parentId, [])
      }
      childrenMap.get(parentId).push(nodeId)
    }
  }

  const weightMap = new Map()
  for (const edge of renderedGraph.edges || []) {
    const sourceId = Number(edge.source)
    const targetId = Number(edge.target)
    const parentId = parentMap.get(sourceId)
    if (parentId === targetId) {
      weightMap.set(String(sourceId), Number(edge.weight))
    }
    const parentId2 = parentMap.get(targetId)
    if (parentId2 === sourceId) {
      weightMap.set(String(targetId), Number(edge.weight))
    }
  }

  const roots = []
  for (const [nodeId, parentId] of parentMap) {
    if (parentId === -1 || parentId === undefined) {
      roots.push(nodeId)
    }
  }
  if (roots.length === 0) {
    return null
  }

  const parts = []
  for (const root of roots) {
    const visited = new Set()
    parts.push(buildNewick(root, null, weightMap, childrenMap, visited, renderedGraph.nodes))
  }
  return parts.join("\n") + ";"
}

/**
 * Build a Blob from a Newick string.
 *
 * @param {string} newickString
 * @returns {Blob}
 */
export function newickBlob(newickString) {
  return new Blob([newickString], { type: "text/plain;charset=utf-8" })
}

/**
 * Build the payload for the current graph JSON export.
 *
 * @param {string|null} [schemaVersion]
 * @param {object} renderedGraph
 * @param {string} [source="gmlst visual"]
 * @returns {object}
 */
export function buildGraphJsonPayload(schemaVersion, renderedGraph, source = "gmlst visual") {
  return {
    schema_version: schemaVersion || "gmlst-visual-v1",
    exported_from: source,
    graph: renderedGraph,
  }
}

/**
 * Build a TSV Blob from filtered table rows and columns.
 *
 * @param {Array<object>} rows
 * @param {Array<object>} columns
 * @returns {Blob}
 */
export function tableTsvBlob(rows, columns) {
  return new Blob([tableRowsToTsv(rows, columns)], { type: "text/tab-separated-values;charset=utf-8" })
}

/**
 * Build a JSON Blob from a locus diff payload.
 *
 * @param {object} locusDiff
 * @returns {Blob}
 */
export function compareJsonBlob(locusDiff) {
  return new Blob([comparePayloadToJson(locusDiff)], { type: "application/json;charset=utf-8" })
}

/**
 * Build a TSV Blob from a heatmap view.
 *
 * @param {Array<string>} labels
 * @param {Array<string>} loci
 * @param {Array<Array<object>>} cells
 * @returns {Blob}
 */
export function heatmapTsvBlob(labels, loci, cells) {
  return new Blob([heatmapToTsv(labels, loci, cells)], { type: "text/tab-separated-values;charset=utf-8" })
}

/**
 * Build a JSON Blob from a heatmap view.
 *
 * @param {Array<string>} labels
 * @param {Array<string>} loci
 * @param {Array<Array<object>>} cells
 * @returns {Blob}
 */
export function heatmapJsonBlob(labels, loci, cells) {
  return new Blob([heatmapPayloadToJson({ labels, loci, cells })], { type: "application/json;charset=utf-8" })
}

/**
 * Build the payload for the session JSON export.
 *
 * @param {object} state
 * @returns {object}
 */
export function buildSessionJsonPayload(state) {
  return {
    schema_version: state.lastData?.export?.schema_version || "gmlst-visual-v1",
    exported_from: "gmlst visual",
    inputs: {
      tsv: state.tsvText,
      metadata_tsv: state.metadataText,
    },
    options: {
      analysis_view: state.analysisView,
      include_missing: state.includeMissing,
      aggregate_profiles: state.aggregateProfiles,
      overlap_relief: state.overlapRelief,
      layout_mode: state.layoutMode,
      edge_length_mode: state.edgeLengthMode,
      edge_length_scale: state.edgeLengthScale,
      long_branch_mode: state.longBranchMode,
      long_branch_threshold: state.longBranchThreshold,
      color_by: state.colorBy,
      max_weight: state.maxWeight,
      collapsed_nodes: state.collapsedNodes,
      collapse_threshold: state.collapseThreshold,
      hidden_legend_values: state.hiddenLegendValues,
      node_search_query: state.nodeSearchQuery,
      show_edge_labels: state.showEdgeLabels,
      scale_node_size: state.scaleNodeSize,
      aggregate_nodes: state.aggregateNodes,
      correctness_overlay: state.correctnessOverlay,
      manual_root_id: state.manualRootId,
      view_filter_mode: state.viewFilterMode,
      cluster_filter: state.clusterFilter,
      node_position_overrides: state.nodePositionOverrides,
      hidden_node_ids: state.hiddenNodeIds,
      custom_node_colors: state.customNodeColors,
    },
    response: state.lastData,
  }
}
