/**
 * Session persistence helpers for the VisualApp.
 *
 * parseSessionState extracts a plain state object from a session payload
 * (the reverse of buildSessionJsonPayload in tableExport.js).
 * applySessionState then writes that object onto a Vue instance.
 */

/**
 * Parse a session restore payload into a plain state object.
 *
 * @param {object} payload - the session JSON object
 * @returns {object} a partial state object ready to apply
 */
export function parseSessionState(payload) {
  const options = payload.options || {};
  const inputs = payload.inputs || {};
  const response = payload.response || null;

  return {
    tsvText: inputs.tsv || "",
    metadataText: inputs.metadata_tsv || "",
    includeMissing: Boolean(options.include_missing),
    aggregateProfiles: options.aggregate_profiles !== false,
    layoutMode: options.layout_mode || "tree",
    edgeLengthMode: options.edge_length_mode || "linear",
    edgeLengthScale: Number(options.edge_length_scale ?? 50) || 50,
    longBranchMode: options.long_branch_mode || "normal",
    longBranchThreshold: Number(options.long_branch_threshold ?? 0) || 0,
    colorBy: options.color_by || "",
    maxWeight: options.max_weight ?? "",
    showEdgeLabels: options.show_edge_labels !== false,
    scaleNodeSize: options.scale_node_size !== false,
    aggregateNodes: Boolean(options.aggregate_nodes),
    correctnessOverlay: options.correctness_overlay !== false,
    viewFilterMode: options.view_filter_mode || "all",
    manualRootId: options.manual_root_id ?? null,
    overlapRelief: options.overlap_relief !== false,
    nodePositionOverrides: options.node_position_overrides || {},
    nodeSearchQuery: options.node_search_query || "",
    collapsedNodes: options.collapsed_nodes || {},
    collapseThreshold: options.collapse_threshold || 0,
    hiddenLegendValues: options.hidden_legend_values || {},
    _hiddenNodeIds: options.hidden_node_ids || {},
    _customNodeColors: options.custom_node_colors || {},
    lastData: response,
    currentLayout: null,
    currentRenderedGraph: null,
    currentEdgeWeightGraph: null,
    currentCollapseSourceGraph: null,
    metadataFields: response?.metadata_fields || [],
    tableRows: response?.table_rows || [],
    clusterSummary: response?.cluster_summary || [],
    clusterFilter: options.cluster_filter ?? "",
    analysisView: options.analysis_view || "graph",
    distanceMatrix: response?.matrix || [],
    matrixLabels: response?.labels || [],
    heatmapLoci: response?.loci || [],
    heatmapCells: response?.cells || [],
    compareLeftLabel: options.compare_left_label || "",
    compareRightLabel: options.compare_right_label || "",
    locusDiff: response?.locus_diff || null,
    suggestedColorFields: response?.suggested_color_fields || [],
    edgeWeightThreshold: options.max_weight ? Number(options.max_weight) : 0,
  };
}
