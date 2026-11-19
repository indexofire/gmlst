<script>
import * as d3 from "d3";

import {
  availableClusterOptions,
  buildNodeInspection,
  comparePayloadToJson,
  compareStatusOptions,
  compareRequestFromSelection,
  compareSelectionFromPair,
  filterAlleleHeatmap,
  filterAlleleHeatmapLoci,
  filterCompareRows,
  filterDistanceMatrix,
  filterRowsByCluster,
  filterTableRows,
  filterRowsForSelection,
  heatmapPayloadToJson,
  heatmapToTsv,
  heatmapAnnotations,
  heatmapCellClass,
  matrixCellTitle,
  nextCompareSelection,
  selectedNodeId,
  sortTableRows,
  tableRowsToTsv,
  valueForColumn,
  visibleTableColumns,
} from "./visualSelection.js";

import {
  aggregateGraph,
  colorMapFor,
  colorValueForNode,
  edgeKey,
  edgeLength,
  filteredEdges,
  getDescendants,
  graphBounds,
  grapetreeGap,
  greedyRadialLayout,
  LAYOUT_CENTER_X,
  LAYOUT_CENTER_Y,
  LAYOUT_MAX_RADIUS,
  highlightedPathEdges,
  highlightedPathNodes,
  legendItemStyle,
  autoNodeScale,
  nodeRadius,
  nodeShapePath,
  parseMaxWeight,
  resolveCollapsedNodeSet,
} from "./visualLayout.js";

import {
  parseSessionPayload,
  readFileWithSizeCheck,
} from "./fileInput.js";

import {
  buildGraphJsonPayload,
  buildNewickString,
  buildSessionJsonPayload,
  compareJsonBlob,
  downloadBlob,
  downloadJson as downloadJsonBlob,
  heatmapJsonBlob,
  heatmapTsvBlob,
  newickBlob,
  tableTsvBlob,
} from "./tableExport.js";

import EmptyState from "./components/EmptyState.vue";
import BuildPrompt from "./components/BuildPrompt.vue";
import DistanceMatrix from "./components/DistanceMatrix.vue";
import CompareTable from "./components/CompareTable.vue";
import AlleleHeatmap from "./components/AlleleHeatmap.vue";
import LegendBar from "./components/LegendBar.vue";
import SummaryView from "./components/SummaryView.vue";
import StatsView from "./components/StatsView.vue";
import { formatNumber } from "./format.js";
import { fetchMst, fetchDistanceMatrix, fetchAlleleHeatmap, fetchCompareResults, fetchCompareLoci } from "./mstApi.js";
import { parseSessionState } from "./sessionPersistence.js";
import { buildGraphStats } from "./mstStats.js";

const VISUAL_TITLE_FALLBACK = "gmlst visual web";

const VIEW_TITLES = {
  graph: "Minimum spanning tree",
  matrix: "Distance matrix",
  heatmap: "Allele heatmap",
  stats: "Statistics",
  summary: "Analysis summary",
  compare: "Result comparison",
};

export default {
  name: "VisualApp",
  components: {
    EmptyState,
    BuildPrompt,
    DistanceMatrix,
    CompareTable,
    AlleleHeatmap,
    LegendBar,
    SummaryView,
    StatsView,
  },
  data() {
    return {
      title:
        document.querySelector('meta[name="gmlst-visual-title"]')?.content ||
        VISUAL_TITLE_FALLBACK,
      _building: false,
      sidebarCollapsed: false,
      isFullscreen: false,
      theme: "auto",
      tsvText: "",
      // Large files are kept in memory but never mirrored into the textarea:
      // a 4 MB TSV in a DOM <textarea> costs ~15 s of layout on first paint.
      tsvFromFile: false,
      tsvFileName: "",
      metadataText: "",
      metadataFromFile: false,
      metadataFileName: "",
      includeMissing: false,
      aggregateProfiles: true,
      showEdgeLabels: true,
      scaleNodeSize: true,
      overlapRelief: false,
      showNodeLabels: true,
      nodeLabelField: "",
      nodeScale: 1,
      hiddenNonTreeEdges: 0,
      analysisView: "graph",
      viewTabs: [
        { id: "graph", label: "Graph" },
        { id: "matrix", label: "Matrix" },
        { id: "heatmap", label: "Heatmap" },
        { id: "stats", label: "Stats" },
        { id: "summary", label: "Summary" },
        { id: "compare", label: "Compare" },
      ],
      layoutMode: "grapetree",
      edgeLengthMode: "linear",
      edgeLengthModeAuto: true,
      edgeLengthScale: 50,
      longBranchMode: "normal",
      longBranchThreshold: 0,
      _legendSelectValue: "",
      _hiddenNodeIds: {},
      _customNodeColors: {},
      _nodeColorPickerTarget: null,
      nodeColorPickerValue: "#2563eb",
      colorScheme: "default",
      colorBy: "",
      shapeBy: "",
      suggestedColorFields: [],
      maxWeight: "",
      edgeWeightMax: 0,
      edgeWeightThreshold: 0,
      aggregateNodes: false,
      correctnessOverlay: true,
      viewFilterMode: "all",
      statusMessage: "Load a profile TSV to begin",
      buildError: "",
      statusKind: "",
      metadataFields: [],
      tableRows: [],
      tableQuery: "",
      tableSelectionOnly: false,
      tableSortKey: "sample_id",
      tableSortDirection: "asc",
      clusterSummary: [],
      clusterFilter: "",
      distanceMatrix: [],
      matrixLabels: [],
      heatmapLoci: [],
      heatmapCells: [],
      heatmapLocusQuery: "",
      compareLeftTsv: "",
      compareRightTsv: "",
      compareResultsSummary: null,
      compareResultRows: [],
      compareStatusFilter: "",
      compareLeftLabel: "",
      compareRightLabel: "",
      locusDiff: null,
      summary: {
        nodes: "-",
        edges: "-",
        metaFields: "-",
      },
      statsLine: "No graph rendered yet.",
      legendItems: [],
      hiddenLegendValues: {},
      hoveredLegendValue: null,
      lastData: null,
      graphData: null,
      view: {
        scale: 1,
        tx: 0,
        ty: 0,
      },
      dragging: false,
      dragStart: null,
      graphGroup: null,
      tooltip: {
        visible: false,
        title: "",
        lines: [],
        x: 0,
        y: 0,
      },
      inspectedItem: null,
      multiSelectedNodeIds: [],
      showComparePanel: false,
      timelineField: "",
      timelineValue: 0,
      timelinePlaying: false,
      timelineTimer: null,
      manualRootId: null,
      currentLayout: null,
      currentRenderedGraph: null,
      currentEdgeWeightGraph: null,
      currentCollapseSourceGraph: null,
      nodeSearchQuery: "",
      nodeSearchActive: false,
      collapsedNodes: {},
      collapseThreshold: 0,
      nodePositionOverrides: {},
    };
  },
  computed: {
    hasProfileInput() {
      return this.tsvText.trim().length > 0;
    },
    tsvInputValue() {
      return this.tsvFromFile ? "" : this.tsvText;
    },
    tsvPlaceholder() {
      if (this.tsvFromFile) {
        const source = this.tsvFileName || "file";
        return `Loaded from ${source} — paste text here to replace it`;
      }
      return "Paste cgMLST TSV or #Strain profile here";
    },
    metadataInputValue() {
      return this.metadataFromFile ? "" : this.metadataText;
    },
    metadataPlaceholder() {
      if (this.metadataFromFile) {
        const source = this.metadataFileName || "file";
        return `Loaded from ${source} — paste text here to replace it`;
      }
      return "Optional metadata table with ID column or first-column sample IDs";
    },
    profilePreview() {
      const text = this.tsvText.trim();
      if (!text) return "";
      const lines = text.split(/\r?\n/).filter((line) => line.trim().length > 0);
      if (lines.length === 0) return "";
      const header = lines[0];
      const delimiter = header.includes("\t") ? "\t" : ",";
      const columns = header.split(delimiter).length;
      const samples = Math.max(lines.length - 1, 0);
      const sampleLabel = samples === 1 ? "sample" : "samples";
      const columnLabel = columns === 1 ? "column" : "columns";
      return `Detected ${samples} ${sampleLabel} · ${columns} ${columnLabel}`;
    },
    hasGraphData() {
      return Boolean(this.graphSource?.nodes?.length);
    },
    graphSource() {
      // Graph payload survives later matrix/heatmap builds; lastData is the
      // most recently built payload (any view).
      if (Array.isArray(this.lastData?.nodes) && this.lastData.nodes.length) {
        return this.lastData;
      }
      return this.graphData;
    },
    hasMatrixData() {
      return this.distanceMatrix.length > 0;
    },
    hasHeatmapData() {
      return this.heatmapLoci.length > 0;
    },
    hasCompareData() {
      return Boolean(this.compareResultsSummary);
    },
    canCompare() {
      return Boolean(this.compareLeftTsv.trim() && this.compareRightTsv.trim());
    },
    vizTitle() {
      return VIEW_TITLES[this.analysisView] || "Analysis";
    },
    viewSubtitle() {
      if (this.statsLine.startsWith("Error:")) {
        return this.statsLine;
      }
      switch (this.analysisView) {
        case "matrix":
          return this.hasMatrixData
            ? `Rendered ${this.matrixLabels.length} × ${this.matrixLabels.length} distance matrix.`
            : "No distance matrix yet — build one from your profile table.";
        case "heatmap":
          return this.hasHeatmapData
            ? `Rendered ${this.matrixLabels.length} × ${this.heatmapLoci.length} allele heatmap.`
            : "No allele heatmap yet — build one from your profile table.";
        case "compare":
          return this.hasCompareData
            ? `Compared ${this.compareResultRows.length} samples across two result sets.`
            : "No comparison yet — compare two result TSVs to see differences.";
        case "summary":
          return this.summaryData
            ? `${this.summaryData.sample_count} samples · ${this.summaryData.mst_summary.edges} edges · ${this.summaryData.cluster_count} clusters`
            : "Build an MST first to see the analysis summary.";
        case "stats":
          return this.statsData
            ? `${this.statsData.nodeCount} samples · ${this.statsData.edgeCount} edges · median weight ${this.statsData.weightMedian}`
            : "Build an MST first to see statistics.";
        default:
          return this.hasGraphData
            ? this.statsLine
            : "No graph rendered yet — build an MST to see sample relationships.";
      }
    },
    overviewMetrics() {
      const metaFields = this.metadataFields.length;
      switch (this.analysisView) {
        case "matrix":
          return [
            { label: "Samples", value: this.matrixLabels.length || "-" },
            { label: "Cells", value: this.hasMatrixData ? this.matrixLabels.length ** 2 : "-" },
            { label: "Meta", value: metaFields },
          ];
        case "heatmap":
          return [
            { label: "Samples", value: this.matrixLabels.length || "-" },
            { label: "Loci", value: this.heatmapLoci.length || "-" },
            { label: "Meta", value: metaFields },
          ];
        case "compare":
          return [
            { label: "Matched", value: this.compareResultsSummary?.matched_samples ?? "-" },
            { label: "Different ST", value: this.compareResultsSummary?.different_st ?? "-" },
            {
              label: "Locus diff",
              value: this.compareResultsSummary?.samples_with_locus_differences ?? "-",
            },
          ];
        case "summary":
        case "stats":
          return [
            { label: "Samples", value: this.statsData?.nodeCount ?? "-" },
            { label: "Edges", value: this.statsData?.edgeCount ?? "-" },
            { label: "Meta", value: metaFields },
          ];
        default:
          return [
            { label: "Nodes", value: this.summary.nodes },
            { label: "Edges", value: this.summary.edges },
            { label: "Meta", value: this.summary.metaFields },
          ];
      }
    },
    statusKindClass() {
      return {
        ok: this.statusKind === "ok",
        error: this.statusKind === "error",
      };
    },
    tooltipStyle() {
      return {
        left: `${this.tooltip.x}px`,
        top: `${this.tooltip.y}px`,
      };
    },
    selectedTableNodeId() {
      return selectedNodeId(this.inspectedItem);
    },
    tableRenderLimit() {
      return 500;
    },
    visibleTableRows() {
      return this.filteredTableRows.slice(0, this.tableRenderLimit);
    },
    tableTruncated() {
      return this.filteredTableRows.length > this.tableRenderLimit;
    },
    filteredTableRows() {
      return sortTableRows(
        filterRowsForSelection(
          filterRowsByCluster(filterTableRows(this.tableRows, this.tableQuery), this.clusterFilter),
          this.selectedTableNodeId,
          this.tableSelectionOnly,
        ),
        this.tableSortKey,
        this.tableSortDirection,
      );
    },
    tableColumns() {
      return visibleTableColumns(this.metadataFields);
    },
    shapeFieldOptions() {
      return this.metadataFields.filter((f) => f !== this.colorBy);
    },
    clusterOptions() {
      const options = availableClusterOptions(this.clusterSummary);
      if (options.length) {
        return options;
      }
      const clusterIds = Array.from(
        new Set(
          this.tableRows
            .map((row) => row.cluster_id)
            .filter((clusterId) => clusterId !== undefined && clusterId !== null && clusterId !== ""),
        ),
      ).sort((left, right) => String(left).localeCompare(String(right), undefined, { numeric: true }));
      return clusterIds.map((clusterId) => ({
        value: String(clusterId),
        label: `Cluster ${clusterId}`,
      }));
    },
    statsData() {
      const graph = this.currentRenderedGraph || this.graphSource;
      return buildGraphStats(
        graph?.nodes,
        graph?.edges,
        {
          clusterCount: this.clusterSummary.length,
          metadataFields: this.metadataFields,
        },
      );
    },
    summaryData() {
      if (!this.statsData) return null;
      const s = this.statsData;
      const suggestions = [];
      if (s.outliers.length > 0) {
        suggestions.push(
          `${s.outliers.length} edges exceed weight 50; check those nodes for imported/divergent strains or data quality issues`,
        );
      }
      suggestions.push(
        "Compare metadata composition across clusters to identify transmission links",
      );
      if (s.zeroWeightCount > 0) {
        suggestions.push(
          `${s.zeroWeightCount} zero-weight edges indicate duplicate profiles — verify they are expected`,
        );
      }
      suggestions.push(
        "High-degree nodes are potential hub strains worth investigating for outbreak links",
      );
      return {
        sample_count: s.nodeCount,
        mst_summary: {
          edges: s.edgeCount,
          weight_median: s.weightMedian,
          weight_max: s.weightMax,
          zero_weight_pairs: s.zeroWeightCount,
        },
        cluster_count: s.clusterCount,
        top_variable_nodes: s.topDegree.slice(0, 5),
        outliers: s.outliers,
        suggested_analysis: suggestions,
      };
    },
    filteredDistanceMatrixView() {
      const limit = this.matrixRenderLimit;
      const view = this.filteredDistanceMatrixBaseView;
      if (view.labels.length <= limit) {
        return view;
      }
      return {
        labels: view.labels.slice(0, limit),
        matrix: view.matrix.slice(0, limit).map((row) => row.slice(0, limit)),
      };
    },
    filteredDistanceMatrixBaseView() {
      return filterDistanceMatrix(
        this.matrixLabels,
        this.distanceMatrix,
        this.tableRows,
        this.clusterFilter,
      );
    },
    matrixRenderLimit() {
      return 200;
    },
    lociRenderLimit() {
      return 300;
    },
    matrixTruncated() {
      return this.filteredDistanceMatrixBaseView.labels.length > this.matrixRenderLimit;
    },
    matrixTruncatedCount() {
      return this.filteredDistanceMatrixBaseView.labels.length;
    },
    matrixMaxValue() {
      let max = 0;
      for (const row of this.filteredDistanceMatrixView.matrix) {
        for (const entry of row) {
          const n = Number(entry) || 0;
          if (n > max) max = n;
        }
      }
      return max || 1;
    },
    filteredHeatmapView() {
      const limit = this.matrixRenderLimit;
      const view = this.filteredHeatmapBaseView;
      if (view.labels.length <= limit) {
        return view;
      }
      return {
        labels: view.labels.slice(0, limit),
        loci: view.loci,
        cells: view.cells.slice(0, limit),
      };
    },
    filteredHeatmapBaseView() {
      return filterAlleleHeatmap(
        this.matrixLabels,
        this.heatmapLoci,
        this.heatmapCells,
        this.tableRows,
        this.clusterFilter,
      );
    },
    heatmapTruncated() {
      return this.filteredHeatmapBaseView.labels.length > this.matrixRenderLimit;
    },
    heatmapTruncatedCount() {
      return this.filteredHeatmapBaseView.labels.length;
    },
    heatmapAnnotationRows() {
      const colorMap = colorMapFor(this.tableRows, this.colorBy, this.colorScheme);
      return heatmapAnnotations(
        this.filteredHeatmapView.labels,
        this.tableRows,
        this.colorBy,
        colorMap,
      );
    },
    filteredHeatmapLociView() {
      const raw = filterAlleleHeatmapLoci(
        this.filteredHeatmapView.loci,
        this.filteredHeatmapView.cells,
        this.heatmapLocusQuery,
      );
      const limit = this.lociRenderLimit;
      if (raw.loci.length <= limit) {
        return raw;
      }
      return {
        loci: raw.loci.slice(0, limit),
        cells: raw.cells.map((row) => row.slice(0, limit)),
      };
    },
    heatmapLociTruncated() {
      const full = filterAlleleHeatmapLoci(
        this.filteredHeatmapView.loci,
        this.filteredHeatmapView.cells,
        this.heatmapLocusQuery,
      );
      return full.loci.length > this.lociRenderLimit;
    },
    heatmapLociTruncatedCount() {
      return filterAlleleHeatmapLoci(
        this.filteredHeatmapView.loci,
        this.filteredHeatmapView.cells,
        this.heatmapLocusQuery,
      ).loci.length;
    },
    compareStatusOptions() {
      return compareStatusOptions(this.compareResultRows);
    },
    filteredCompareRows() {
      return filterCompareRows(this.compareResultRows, this.compareStatusFilter);
    },
    minEdgeWeightLabel() {
      if (!this.graphSource?.edges?.length) return "0";
      let min = Infinity;
      for (const edge of this.graphSource.edges) {
        const w = Number(edge.weight);
        if (w < min) min = w;
      }
      return String(min === Infinity ? 0 : min);
    },
    filteredEdgeCount() {
      const edges = this.currentEdgeWeightGraph?.edges || this.currentRenderedGraph?.edges || [];
      if (this.edgeWeightThreshold <= 0) {
        return edges.length;
      }
      return edges.filter((edge) => (Number(edge.weight) || 0) <= this.edgeWeightThreshold).length;
    },
    totalEdgeCount() {
      return (this.currentEdgeWeightGraph?.edges || this.currentRenderedGraph?.edges || []).length;
    },
    nodeSearchMatchCount() {
      const nodes = Array.isArray(this.currentRenderedGraph?.nodes)
        ? this.currentRenderedGraph.nodes
        : [];
      const query = this.nodeSearchQuery.trim().toLowerCase();
      if (!query) {
        return nodes.length;
      }
      return nodes.filter((node) => {
        const label = String(node.label || "").toLowerCase();
        const shown = String(this.nodeLabelText(node) || "").toLowerCase();
        return label.includes(query) || shown.includes(query);
      }).length;
    },
    nodeSearchTotal() {
      return Array.isArray(this.currentRenderedGraph?.nodes)
        ? this.currentRenderedGraph.nodes.length
        : 0;
    },
    collapsedNodeSet() {
      const graph = this.currentCollapseSourceGraph || this.currentRenderedGraph;
      return resolveCollapsedNodeSet(
        graph?.nodes || [],
        graph?.edges || [],
        this.currentLayout?.parent,
        this.collapsedNodes,
        this.collapseThreshold,
        edgeKey,
      );
    },
    thresholdHistogramBars() {
      const edges = this.currentEdgeWeightGraph?.edges || [];
      if (!edges.length) {
        return [];
      }
      if (this.edgeWeightMax <= 0) {
        return [{ key: 0, height: "100%", active: true }];
      }
      const binCount = Math.min(20, Math.max(8, this.edgeWeightMax + 1));
      const bins = Array.from({ length: binCount }, (_, index) => ({
        key: index,
        count: 0,
        lowerBound: (index / binCount) * this.edgeWeightMax,
        upperBound: ((index + 1) / binCount) * this.edgeWeightMax,
      }));
      edges.forEach((edge) => {
        const weight = Math.max(0, Math.min(this.edgeWeightMax, Number(edge.weight) || 0));
        const scaledIndex = Math.floor((weight / this.edgeWeightMax) * binCount);
        const index = Math.min(binCount - 1, scaledIndex);
        bins[index].count += 1;
      });
      const maxCount = Math.max(...bins.map((bin) => bin.count), 1);
      return bins.map((bin) => ({
        key: bin.key,
        height: `${Math.max(14, (bin.count / maxCount) * 100)}%`,
        active: this.edgeWeightThreshold <= 0 || bin.lowerBound <= this.edgeWeightThreshold,
      }));
    },
  },
  watch: {
    analysisView() {
      this.syncCanvasInteraction();
    },
    hoveredLegendValue() {
      this._applyLegendHover();
    },
    colorBy() { this.syncViewStateToUrl(); },
    shapeBy() { this.syncViewStateToUrl(); },
    layoutMode() { this.syncViewStateToUrl(); },
    aggregateProfiles() { this.syncViewStateToUrl(); },
    nodeScale() { this.syncViewStateToUrl(); },
    edgeLengthScale() { this.syncViewStateToUrl(); },
  },
  mounted() {
    this._boundCanvas = null;
    this._pendingNodeClick = null;
    this._debounceTimer = null;
    this._dragRaf = null;
    this.initTheme();
    if (window.innerWidth <= 700) {
      this.sidebarCollapsed = true;
    }
    this.loadViewStateFromUrl();
    document.addEventListener("fullscreenchange", () => {
      this.isFullscreen = Boolean(document.fullscreenElement);
    });
    this.syncCanvasInteraction();
    window.addEventListener("mousemove", this.onMouseMove);
    window.addEventListener("mouseup", this.onMouseUp);
    window.addEventListener("touchmove", this.onTouchMove, { passive: false });
    window.addEventListener("touchend", this.onTouchEnd);
    this._boundKeydown = (event) => this.handleGlobalKeydown(event);
    window.addEventListener("keydown", this._boundKeydown);
    this._themeMedia = window.matchMedia("(prefers-color-scheme: dark)");
    this._onThemeMediaChange = () => {
      if (this.theme === "auto" && this.hasGraphData) {
        this.$nextTick(() => this.redrawFromLastData());
      }
    };
    this._themeMedia.addEventListener("change", this._onThemeMediaChange);
    this._beforeUnload = (event) => {
      if (this.graphSource && Object.keys(this.nodePositionOverrides).length > 0) {
        event.preventDefault();
      }
    };
    window.addEventListener("beforeunload", this._beforeUnload);
  },
  beforeUnmount() {
    this.detachCanvasListeners();
    window.removeEventListener("mousemove", this.onMouseMove);
    window.removeEventListener("mouseup", this.onMouseUp);
    window.removeEventListener("touchmove", this.onTouchMove);
    window.removeEventListener("touchend", this.onTouchEnd);
    if (this._boundKeydown) {
      window.removeEventListener("keydown", this._boundKeydown);
      this._boundKeydown = null;
    }
    if (this._themeMedia && this._onThemeMediaChange) {
      this._themeMedia.removeEventListener("change", this._onThemeMediaChange);
      this._themeMedia = null;
      this._onThemeMediaChange = null;
    }
    if (this._pendingNodeClick) {
      window.clearTimeout(this._pendingNodeClick);
      this._pendingNodeClick = null;
    }
    if (this._beforeUnload) {
      window.removeEventListener("beforeunload", this._beforeUnload);
    }
  },
  methods: {
    toggleFullscreen() {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().then(() => {
          this.isFullscreen = true;
        }).catch(() => {});
      } else {
        document.exitFullscreen().then(() => {
          this.isFullscreen = false;
        }).catch(() => {});
      }
    },
    syncViewStateToUrl() {
      const params = new URLSearchParams();
      if (this.colorBy) params.set("color", this.colorBy);
      if (this.shapeBy) params.set("shape", this.shapeBy);
      if (this.nodeScale !== 1) params.set("node_scale", String(this.nodeScale));
      if (this.edgeLengthScale !== 50) {
        params.set("branch_scale", String(this.edgeLengthScale));
      }
      if (this.layoutMode !== "grapetree") {
        params.set("layout", this.layoutMode);
      }
      if (this.theme !== "auto") params.set("theme", this.theme);
      if (this.aggregateProfiles !== true) params.set("agg", "0");
      const hash = params.toString();
      const url = hash ? `${location.pathname}?${hash}` : location.pathname;
      history.replaceState(null, "", url);
    },
    loadViewStateFromUrl() {
      const params = new URLSearchParams(location.search);
      const color = params.get("color");
      const shape = params.get("shape");
      const layout = params.get("layout");
      const theme = params.get("theme");
      const agg = params.get("agg");
      if (color) this.colorBy = color;
      if (shape) this.shapeBy = shape;
      if (layout && ["tree", "radial", "grapetree"].includes(layout)) {
        this.layoutMode = layout;
      }
      if (theme && ["light", "dark"].includes(theme)) {
        this.theme = theme;
        document.documentElement.setAttribute("data-theme", theme);
      }
      if (agg === "0") this.aggregateProfiles = false;
      const nodeScale = Number(params.get("node_scale"));
      if (Number.isFinite(nodeScale) && nodeScale >= 0.5 && nodeScale <= 2) {
        this.nodeScale = nodeScale;
      }
      const branchScale = Number(params.get("branch_scale"));
      if (Number.isFinite(branchScale) && branchScale >= 10 && branchScale <= 100) {
        this.edgeLengthScale = branchScale;
      }
    },
    initTheme() {
      const saved = localStorage.getItem("gmlst-theme");
      if (saved === "light" || saved === "dark") {
        this.theme = saved;
        document.documentElement.setAttribute("data-theme", saved);
      } else {
        this.theme = "auto";
      }
    },
    toggleMultiSelect(nodeId) {
      const id = String(nodeId);
      const idx = this.multiSelectedNodeIds.indexOf(id);
      if (idx >= 0) {
        this.multiSelectedNodeIds.splice(idx, 1);
      } else {
        this.multiSelectedNodeIds.push(id);
      }
      this.showComparePanel = this.multiSelectedNodeIds.length >= 2;
      this.redrawFromLastData();
    },
    clearMultiSelect() {
      this.multiSelectedNodeIds = [];
      this.showComparePanel = false;
      this.redrawFromLastData();
    },
    timelineFieldOptions() {
      if (!this.graphSource?.nodes?.length) return [];
      const fields = this.metadataFields.filter((f) => {
        return this.graphSource.nodes.some((nd) => {
          const v = nd.meta?.[f];
          return v && /^\d{4}([-.]\d{1,2})?$/.test(String(v).trim());
        });
      });
      return fields;
    },
    timelineMaxValue() {
      if (!this.timelineField || !this.graphSource?.nodes) return 0;
      return Math.max(
        ...this.graphSource.nodes.map((nd) =>
          parseInt(String(nd.meta?.[this.timelineField] || "0"), 10) || 0,
        ),
      );
    },
    timelineNodeVisible(node) {
      if (!this.timelineField || this.timelineValue <= 0) return true;
      const year = parseInt(String(node.meta?.[this.timelineField] || "0"), 10) || 0;
      return year <= this.timelineValue;
    },
    toggleTimelinePlay() {
      if (this.timelinePlaying) {
        this.stopTimeline();
      } else {
        this.startTimeline();
      }
    },
    startTimeline() {
      if (!this.timelineField) return;
      this.timelinePlaying = true;
      this.timelineValue = 0;
      const max = this.timelineMaxValue();
      this.timelineTimer = window.setInterval(() => {
        this.timelineValue += 1;
        if (this.timelineValue >= max) {
          this.stopTimeline();
          this.timelineValue = max;
        }
        this.redrawFromLastData();
      }, 400);
    },
    stopTimeline() {
      this.timelinePlaying = false;
      if (this.timelineTimer) {
        window.clearInterval(this.timelineTimer);
        this.timelineTimer = null;
      }
    },
    resetTimeline() {
      this.stopTimeline();
      this.timelineValue = 0;
      this.redrawFromLastData();
    },
    selectedNodesForCompare() {
      if (!this.graphSource?.nodes) return [];
      const idSet = new Set(this.multiSelectedNodeIds);
      return this.graphSource.nodes.filter((n) => idSet.has(String(n.id)));
    },
    comparePairsDistance() {
      const nodes = this.selectedNodesForCompare();
      if (nodes.length < 2 || !this.graphSource?.edges) return [];
      const idSet = new Set(nodes.map((n) => String(n.id)));
      const relevant = this.graphSource.edges.filter(
        (e) => idSet.has(String(e.source)) && idSet.has(String(e.target)),
      );
      const nodeMap = new Map(nodes.map((n) => [String(n.id), n]));
      return relevant.map((e) => ({
        a: nodeMap.get(String(e.source))?.label || "?",
        b: nodeMap.get(String(e.target))?.label || "?",
        weight: e.weight,
        loci: (e.mismatch_loci || []).join(", "),
      }));
    },
    shapeIndexFor(value) {
      const str = String(value);
      let hash = 0;
      for (let i = 0; i < str.length; i++) {
        hash = ((hash << 5) - hash + str.charCodeAt(i)) & 0xffffffff;
      }
      return Math.abs(hash) % 5;
    },
    cycleTheme() {
      const order = ["auto", "light", "dark"];
      const next = order[(order.indexOf(this.theme) + 1) % order.length];
      this.theme = next;
      if (next === "auto") {
        document.documentElement.removeAttribute("data-theme");
        localStorage.removeItem("gmlst-theme");
      } else {
        document.documentElement.setAttribute("data-theme", next);
        localStorage.setItem("gmlst-theme", next);
      }
      this.syncViewStateToUrl();
      if (this.hasGraphData) {
        this.$nextTick(() => this.redrawFromLastData());
      }
    },
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed;
    },
    onNodeSearch() {
      this._legendSelectValue = "";
      this.nodeSearchActive = Boolean(this.nodeSearchQuery.trim());
      this.redrawFromLastData();
    },
    clearNodeSearch() {
      this.nodeSearchQuery = "";
      this.nodeSearchActive = false;
      this._legendSelectValue = "";
      this.redrawFromLastData();
    },
    focusNodeSearchInput() {
      this.$nextTick(() => {
        const input = document.getElementById("node-search");
        if (input && typeof input.focus === "function") {
          input.focus();
          if (typeof input.select === "function") {
            input.select();
          }
        }
      });
    },
    handleGlobalKeydown(event) {
      const tag = event.target?.tagName;
      const editable = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT"
        || event.target?.isContentEditable;
      const mod = event.ctrlKey || event.metaKey;
      if (mod && !event.altKey && String(event.key || "").toLowerCase() === "f") {
        if (this.analysisView === "graph" && !editable) {
          event.preventDefault();
          if (this.sidebarCollapsed) {
            this.sidebarCollapsed = false;
          }
          this.focusNodeSearchInput();
        }
        return;
      }
      if (mod && String(event.key || "").toLowerCase() === "s") {
        if (editable) return;
        event.preventDefault();
        if (this.analysisView === "graph") {
          this.exportGraphJson();
        }
        return;
      }
      if (mod && String(event.key || "").toLowerCase() === "e") {
        if (editable) return;
        event.preventDefault();
        if (this.analysisView === "graph") {
          this.exportNewick();
        }
        return;
      }
      if (!mod && event.key === "/") {
        if (editable) {
          return;
        }
        event.preventDefault();
        const searchInput = document.getElementById("node-search");
        if (this.analysisView === "graph" && this.hasGraphData && searchInput) {
          if (this.sidebarCollapsed) {
            this.sidebarCollapsed = false;
          }
          searchInput.focus();
        } else {
          document.getElementById("tsv-input")?.focus();
        }
        return;
      }
      if (!mod && String(event.key || "").toLowerCase() === "f" && !event.altKey) {
        if (!editable && this.analysisView === "graph" && this.hasGraphData) {
          event.preventDefault();
          this.fitView();
        }
        return;
      }
      if (!mod && event.key === "Escape") {
        if (this.buildError) {
          this.buildError = "";
        }
        if (this._legendSelectValue || this.nodeSearchActive) {
          this.clearNodeSearch();
        }
        return;
      }
      if (!mod && (event.key === "+" || event.key === "=")) {
        if (editable) return;
        if (this.analysisView === "graph") {
          event.preventDefault();
          this.zoomIn();
        }
        return;
      }
      if (!mod && event.key === "-") {
        if (editable) return;
        if (this.analysisView === "graph") {
          event.preventDefault();
          this.zoomOut();
        }
        return;
      }
    },
    attachCanvasListeners() {
      const canvas = this.$refs.canvas;
      if (!canvas || canvas === this._boundCanvas) {
        return;
      }
      this.detachCanvasListeners();
      canvas.addEventListener("wheel", this.handleWheel, { passive: false });
      canvas.addEventListener("mousedown", this.onMouseDown);
      canvas.addEventListener("touchstart", this.onTouchStart, { passive: false });
      this._boundCanvas = canvas;
    },
    detachCanvasListeners() {
      if (!this._boundCanvas) {
        return;
      }
      this._boundCanvas.removeEventListener("wheel", this.handleWheel);
      this._boundCanvas.removeEventListener("mousedown", this.onMouseDown);
      this._boundCanvas.removeEventListener("touchstart", this.onTouchStart);
      this._boundCanvas = null;
    },
    syncCanvasInteraction() {
      if (this.analysisView !== "graph") {
        this.detachCanvasListeners();
        this.dragging = false;
        this.dragStart = null;
        return;
      }
      this.$nextTick(() => {
        this.attachCanvasListeners();
        if (Array.isArray(this.graphSource?.nodes) && Array.isArray(this.graphSource?.edges)) {
          this.redrawFromLastData();
        }
      });
    },
    viewAvailable(viewId) {
      switch (viewId) {
        case "summary":
        case "stats":
          return this.hasGraphData;
        default:
          return true;
      }
    },
    isViewBuilt(viewId) {
      switch (viewId) {
        case "matrix":
          return this.hasMatrixData;
        case "heatmap":
          return this.hasHeatmapData;
        case "compare":
          return this.hasCompareData;
        case "summary":
        case "stats":
        case "graph":
          return this.hasGraphData;
        default:
          return true;
      }
    },
    viewBuildHint(viewId) {
      switch (viewId) {
        case "matrix":
          return this.hasMatrixData
            ? "Distance matrix"
            : "Not built yet — click to build the distance matrix";
        case "heatmap":
          return this.hasHeatmapData
            ? "Allele heatmap"
            : "Not built yet — click to build the allele heatmap";
        case "compare":
          if (this.hasCompareData) return "Result comparison";
          return this.canCompare
            ? "Ready to compare — click to run the comparison"
            : "Not compared yet — paste two result TSVs in the sidebar, then compare";
        case "summary":
          return this.hasGraphData
            ? "Analysis summary"
            : "Build an MST first to see the analysis summary";
        case "stats":
          return this.hasGraphData
            ? "Statistics"
            : "Build an MST first to see statistics";
        default:
          return VIEW_TITLES[viewId] || viewId;
      }
    },
    switchAnalysisView(viewId) {
      this.analysisView = viewId;
    },
    onTsvInput(event) {
      this.tsvFromFile = false;
      this.tsvFileName = "";
      this.tsvText = event.target.value;
    },
    onMetadataInput(event) {
      this.metadataFromFile = false;
      this.metadataFileName = "";
      this.metadataText = event.target.value;
    },
    async onFileChange(event) {
      const file = event.target.files?.[0];
      if (!file) {
        return;
      }
      try {
        this.tsvText = await readFileWithSizeCheck(file);
        this.tsvFromFile = true;
        this.tsvFileName = file.name;
        this.setStatus("ok", "Profile loaded");
      } catch (error) {
        this.setStatus("error", error.message);
      }
    },
    async onMetadataFileChange(event) {
      const file = event.target.files?.[0];
      if (!file) {
        return;
      }
      try {
        this.metadataText = await readFileWithSizeCheck(file);
        this.metadataFromFile = true;
        this.metadataFileName = file.name;
        this.setStatus("ok", "Metadata loaded");
      } catch (error) {
        this.setStatus("error", error.message);
      }
    },
    async onSessionFileChange(event) {
      const file = event.target.files?.[0];
      if (!file) {
        return;
      }
      try {
        const payload = parseSessionPayload(await readFileWithSizeCheck(file));
        this.applySessionPayload(payload);
        this.setStatus("ok", "Session restored");
      } catch (error) {
        this.setStatus("error", `Failed to load session: ${error.message}`);
      }
    },
    nodeLabelText(node) {
      const field = this.nodeLabelField;
      if (!field) {
        return node.label;
      }
      if (field === "cluster_id") {
        const cluster = node.cluster_id;
        return cluster === undefined || cluster === null || String(cluster) === "-1"
          ? node.label
          : String(cluster);
      }
      const raw = node.meta?.[field];
      if (raw === undefined || raw === null || String(raw).trim() === "") {
        return node.label;
      }
      // Aggregated nodes join differing member values with " | "; keep the
      // first value so labels stay compact.
      return String(raw).split(" | ")[0];
    },
    _autoEdgeLengthMode(data) {
      // Linear branch lengths only make sense when the allele-distance
      // range is narrow (classical MLST). cgMLST distances reach tens to
      // hundreds of alleles, which would compress dense clusters into a
      // hairball; logarithmic scaling keeps the tree readable.
      const weights = (data?.edges || [])
        .map((edge) => Number(edge.weight) || 0)
        .filter((weight) => weight > 0);
      if (!weights.length) {
        return "linear";
      }
      return Math.max(...weights) >= 20 ? "log" : "linear";
    },
    onEdgeLengthModeChange() {
      this.edgeLengthModeAuto = false;
      this.redrawFromLastData();
    },
    graphTheme() {
      const styles = getComputedStyle(document.documentElement);
      const read = (name, fallback) => styles.getPropertyValue(name).trim() || fallback;
      return {
        edgeMin: read("--graph-edge-min", "#d6e1ee"),
        edgeMax: read("--graph-edge-max", "#334155"),
        edgeWeak: read("--graph-edge-weak", "#d5dee9"),
        edgeLabel: read("--graph-edge-label", "#475569"),
        labelHalo: read("--graph-label-halo", "#ffffff"),
        ring: read("--graph-node-ring", "rgba(15, 23, 42, 0.35)"),
        ringStroke: read("--graph-node-ring-stroke", "rgba(15, 23, 42, 0.5)"),
        labelBg: read("--graph-label-bg", "rgba(255, 255, 255, 0.86)"),
        labelStroke: read("--graph-label-stroke", "rgba(203, 213, 225, 0.9)"),
        labelText: read("--graph-label-text", "#1f2937"),
        labelTextStrong: read("--graph-label-text-strong", "#0f172a"),
        scaleBg: read("--graph-scale-bg", "rgba(255, 255, 255, 0.85)"),
        scaleStroke: read("--graph-scale-stroke", "rgba(203, 213, 225, 0.6)"),
        edgeConnector: read("--graph-edge-connector", "rgba(100, 116, 139, 0.55)"),
      };
    },
    formatNumber,
    setStatus(kind, message) {
      this.statusKind = kind;
      this.statusMessage = message;
    },
    clearSvg() {
      this._graphBounds = null;
      const svg = this.$refs.svg;
      if (!svg) {
        this.graphGroup = null;
        return;
      }
      svg.querySelector(".scale-bar")?.remove();
      while (svg.firstChild) {
        svg.removeChild(svg.firstChild);
      }
      this.graphGroup = null;
    },
    updateSummary(nodeCount, edgeCount, sampleCount) {
      this.summary.nodes = nodeCount;
      this.summary.edges = edgeCount;
      this.summary.metaFields = this.metadataFields.length;
      const sampleText = sampleCount ? ` from ${sampleCount} samples` : "";
      this.statsLine = `Rendered ${nodeCount} nodes and ${edgeCount} edges${sampleText}.`;
    },
    onThresholdChange() {
      this.maxWeight = this.edgeWeightThreshold > 0 ? String(this.edgeWeightThreshold) : "";
      this.debouncedRedraw();
    },
    updateLegend(colorMap, nodes, colorField) {
      if (!colorField) {
        this.legendItems = [];
        return;
      }
      const counts = new Map();
      for (const node of nodes) {
        const value = colorField === "cluster_id" ? String(node.cluster_id) : node.meta?.[colorField];
        if (!value) {
          continue;
        }
        counts.set(value, (counts.get(value) || 0) + Number(node.member_count || 1));
      }
      this.legendItems = Array.from(colorMap.entries()).map(([value, color]) => {
        const total = counts.get(value) || 0;
        const visible = this.hiddenLegendValues[value] ? 0 : total;
        return {
          value,
          color,
          count: `${visible}/${total}`,
        };
      });
    },
    toggleLegendValue(value) {
      const updated = { ...this.hiddenLegendValues };
      if (updated[value]) {
        delete updated[value];
      } else {
        updated[value] = true;
      }
      this.hiddenLegendValues = updated;
      this.redrawFromLastData();
    },
    showAllLegendValues() {
      this.hiddenLegendValues = {};
      this.redrawFromLastData();
    },
    selectNodesByLegendValue(value) {
      if (!this.currentLayout || !this.colorBy) return;
      const nodes = this.graphSource?.nodes || [];
      let count = 0;
      for (const node of nodes) {
        if (colorValueForNode(node, this.colorBy) === value) {
          count += 1;
        }
      }
      this.nodeSearchActive = true;
      this.nodeSearchQuery = "";
      this._legendSelectValue = value;
      this.redrawFromLastData();
      this.setStatus("ok", `Selected ${count} nodes with ${this.colorBy} = ${value}`);
    },
    legendItemStyle(item) {
      return legendItemStyle(item, this.hiddenLegendValues);
    },
    applyViewTransform() {
      const svg = this.$refs.svg;
      if (!this.graphGroup) {
        if (svg) {
          this._drawScaleBar(svg);
        }
        return;
      }
      this.graphGroup.setAttribute(
        "transform",
        `translate(${this.view.tx} ${this.view.ty}) scale(${this.view.scale})`,
      );
      if (svg) {
        this._drawScaleBar(svg);
      }
    },
    eventClientPoint(event) {
      const nativeEvent = event?.sourceEvent || event;
      if (nativeEvent?.touches?.length) {
        return {
          x: nativeEvent.touches[0].clientX,
          y: nativeEvent.touches[0].clientY,
        };
      }
      if (nativeEvent?.changedTouches?.length) {
        return {
          x: nativeEvent.changedTouches[0].clientX,
          y: nativeEvent.changedTouches[0].clientY,
        };
      }
      if (
        typeof nativeEvent?.clientX !== "number" ||
        typeof nativeEvent?.clientY !== "number"
      ) {
        return null;
      }
      return {
        x: nativeEvent.clientX,
        y: nativeEvent.clientY,
      };
    },
    clientPointToSvg(point) {
      const svg = this.$refs.svg;
      if (!svg) {
        return null;
      }
      const matrix = svg.getScreenCTM();
      if (!matrix) {
        return null;
      }
      const svgPoint = svg.createSVGPoint();
      svgPoint.x = point.x;
      svgPoint.y = point.y;
      return svgPoint.matrixTransform(matrix.inverse());
    },
    clientPointToGraph(point) {
      const svgPoint = this.clientPointToSvg(point);
      if (!svgPoint) {
        return null;
      }
      return {
        x: (svgPoint.x - this.view.tx) / this.view.scale,
        y: (svgPoint.y - this.view.ty) / this.view.scale,
      };
    },
    fitView() {
      if (!this.graphGroup) {
        this.view.scale = 1;
        this.view.tx = 0;
        this.view.ty = 0;
        this.applyViewTransform();
        return;
      }
      // Use the drawn node bounds instead of graphGroup.getBBox(): measuring
      // a 600-node MST with hundreds of text labels takes ~6s in Chromium.
      const bounds = this._graphBounds;
      const bbox = bounds
        ? {
            x: bounds.minX - 12,
            y: bounds.minY - 12,
            width: bounds.maxX - bounds.minX + 24,
            height: bounds.maxY - bounds.minY + 24,
          }
        : this.graphGroup.getBBox();
      if (!bbox.width || !bbox.height) {
        this.view.scale = 1;
        this.view.tx = 0;
        this.view.ty = 0;
        this.applyViewTransform();
        return;
      }
      const svg = this.$refs.svg;
      if (!svg) {
        return;
      }
      const vb = svg.viewBox.baseVal;
      const svgW = vb.width || 1400;
      const svgH = vb.height || 900;
      const padding = 60;
      const scaleX = (svgW - 2 * padding) / bbox.width;
      const scaleY = (svgH - 2 * padding) / bbox.height;
      const scale = Math.min(scaleX, scaleY, 3);
      const cx = bbox.x + bbox.width / 2;
      const cy = bbox.y + bbox.height / 2;
      this.view.scale = scale;
      this.view.tx = svgW / 2 - cx * scale;
      this.view.ty = svgH / 2 - cy * scale;
      this.applyViewTransform();
    },
    showTooltip(node, event) {
      const inspection = buildNodeInspection(node);
      const point = this.eventClientPoint(event);
      if (!point) {
        return;
      }

      const canvas = this.$refs.canvas;
      const canvasRect = canvas ? canvas.getBoundingClientRect() : null;
      const tooltipWidth = 280;
      const tooltipHeight = inspection.lines.length * 20 + 40;
      const maxX = canvasRect ? canvasRect.width - tooltipWidth : Infinity;
      const maxY = canvasRect ? canvasRect.height - tooltipHeight : Infinity;
      const x = canvasRect ? point.x - canvasRect.left + 12 : point.x + 12;
      const y = canvasRect ? point.y - canvasRect.top + 12 : point.y + 12;
      this.tooltip = {
        visible: true,
        title: inspection.title,
        lines: inspection.lines,
        x: Math.max(4, Math.min(x, maxX)),
        y: Math.max(4, Math.min(y, maxY)),
      };
      this.inspectedItem = inspection;
      this.focusSelectedTableRow();
    },
    showEdgeTooltip(edge, event) {
      const mismatchLoci = edge.mismatch_loci || [];
      const mismatchCount = Number(edge.mismatch_count ?? mismatchLoci.length);
      const lines = [
        `distance: ${edge.weight}`,
        `source: ${edge.source_label}`,
        `target: ${edge.target_label}`,
        `mismatch loci: ${mismatchCount}`,
      ];
      if (mismatchLoci.length) {
        lines.push(`loci: ${mismatchLoci.join(", ")}`);
      } else if (mismatchCount > 0) {
        lines.push("locus list omitted for large trees — use Compare for details");
      }
      const point = this.eventClientPoint(event);
      if (!point) {
        return;
      }
      const canvas = this.$refs.canvas;
      const canvasRect = canvas ? canvas.getBoundingClientRect() : null;
      const tooltipWidth = 280;
      const tooltipHeight = lines.length * 20 + 40;
      const maxX = canvasRect ? canvasRect.width - tooltipWidth : Infinity;
      const maxY = canvasRect ? canvasRect.height - tooltipHeight : Infinity;
      const x = canvasRect ? point.x - canvasRect.left + 12 : point.x + 12;
      const y = canvasRect ? point.y - canvasRect.top + 12 : point.y + 12;
      this.tooltip = {
        visible: true,
        title: `${edge.source_label} ↔ ${edge.target_label}`,
        lines,
        x: Math.max(4, Math.min(x, maxX)),
        y: Math.max(4, Math.min(y, maxY)),
      };
      this.inspectedItem = {
        kind: "edge",
        title: `${edge.source_label} ↔ ${edge.target_label}`,
        lines,
      };
    },
    hideTooltip() {
      this.tooltip.visible = false;
    },
    _applyLegendHover() {
      const svg = this.$refs.svg;
      if (!svg) return;
      svg.querySelectorAll(".legend-hover-ring-dynamic").forEach((el) => el.remove());
      const value = this.hoveredLegendValue;
      if (!value || !this.colorBy) return;
      const groups = svg.querySelectorAll(".node-group, .pie-node-group");
      for (const g of groups) {
        const legendVal = g.getAttribute("data-legend-value");
        const dimmed = g.getAttribute("data-dimmed") === "1";
        if (legendVal === value && !dimmed) {
          const color = g.getAttribute("data-node-color") || "#2563eb";
          const radius = Number(g.getAttribute("data-radius")) || 8;
          const ring = document.createElementNS("http://www.w3.org/2000/svg", "circle");
          ring.setAttribute("class", "legend-hover-ring-dynamic");
          ring.setAttribute("r", String(radius + 6));
          ring.setAttribute("fill", "none");
          ring.setAttribute("stroke", color);
          ring.setAttribute("stroke-width", "3");
          ring.setAttribute("stroke-opacity", "0.7");
          g.insertBefore(ring, g.firstChild);
        }
      }
    },
    toggleEdgeLabels() {
      const svg = this.$refs.svg;
      if (!svg) return;
      const labels = svg.querySelectorAll(".edge-label");
      labels.forEach((el) => {
        el.style.display = this.showEdgeLabels && el.getAttribute("data-overlap-hidden") !== "1"
          ? ""
          : "none";
      });
    },
    applySuggestedColor(field) {
      this.colorBy = field;
      this.redrawFromLastData();
    },
    clearManualRoot() {
      this.manualRootId = null;
      this.redrawFromLastData();
    },
    clearDraggedLayout() {
      if (Object.keys(this.nodePositionOverrides).length > 0 && !confirm("Reset all dragged node positions?")) return;
      this.nodePositionOverrides = {};
      this.redrawFromLastData();
    },
    toggleNodeCollapse(nodeId) {
      const newCollapsed = { ...this.collapsedNodes };
      const key = String(nodeId);
      if (newCollapsed[key]) {
        delete newCollapsed[key];
      } else {
        newCollapsed[key] = true;
      }
      this.collapsedNodes = newCollapsed;
      this.redrawFromLastData();
    },
    expandAllNodes() {
      this.collapsedNodes = {};
      this.collapseThreshold = 0;
      this.redrawFromLastData();
    },
    collapseAllLeaves() {
      const graph = this.currentCollapseSourceGraph || this.currentRenderedGraph;
      if (!graph || !this.currentLayout?.parent) {
        return;
      }
      const childMap = new Map();
      for (const [nodeId, parentId] of this.currentLayout.parent.entries()) {
        if (parentId === undefined || parentId === -1) {
          continue;
        }
        if (!childMap.has(parentId)) {
          childMap.set(parentId, []);
        }
        childMap.get(parentId).push(nodeId);
      }
      const collapsed = {};
      for (const node of graph.nodes) {
        const childIds = childMap.get(node.id) || [];
        if (!childIds.length) {
          continue;
        }
        const hasGrandchild = childIds.some((childId) => (childMap.get(childId) || []).length > 0);
        if (!hasGrandchild) {
          collapsed[String(node.id)] = true;
        }
      }
      this.collapsedNodes = collapsed;
      this.redrawFromLastData();
    },
    hideNode(nodeId) {
      this._hiddenNodeIds[String(nodeId)] = true;
      this.redrawFromLastData();
    },
    showAllHiddenNodes() {
      this._hiddenNodeIds = {};
      this.redrawFromLastData();
    },
    openNodeColorPicker(nodeId, currentColor) {
      this._nodeColorPickerTarget = nodeId;
      this.nodeColorPickerValue = currentColor || "#2563eb";
      this.$nextTick(() => {
        const picker = this.$refs.nodeColorPicker;
        if (picker) picker.click();
      });
    },
    applyCustomNodeColor(color) {
      if (this._nodeColorPickerTarget == null) return;
      this._customNodeColors[String(this._nodeColorPickerTarget)] = color;
      this.redrawFromLastData();
    },
    resetNodeColor(nodeId) {
      delete this._customNodeColors[String(nodeId)];
      this.redrawFromLastData();
    },
    resetAllNodeColors() {
      this._customNodeColors = {};
      this.redrawFromLastData();
    },
    selectGraphNode(node) {
      // Single click inspects/highlights; re-rooting the tree is an
      // explicit action (Inspection details → “Set as tree root”) so the
      // layout never jumps underneath the cursor.
      const members = Array.isArray(node.members) ? node.members : [];
      const row = {
        id: node.id,
        label: node.label,
        sample_id: members[0] || node.label,
        member_count: node.member_count || 1,
        members: members.length ? members : [node.label],
        cluster_id: node.cluster_id,
        meta: node.meta || {},
      };
      this.inspectedItem = buildNodeInspection(row);
      this.focusSelectedTableRow();
      this.redrawFromLastData();
    },
    setManualRoot(nodeId) {
      this.manualRootId = nodeId;
      this.redrawFromLastData();
    },
    selectTableRow(row) {
      this.inspectedItem = buildNodeInspection(row);
      const next = nextCompareSelection(
        this.compareLeftLabel,
        this.compareRightLabel,
        row.sample_id,
      );
      this.compareLeftLabel = next.left;
      this.compareRightLabel = next.right;
      this.focusSelectedTableRow();
      this.redrawFromLastData();
    },
    selectClusterFilter(clusterId) {
      this.clusterFilter = String(clusterId);
      this.redrawFromLastData();
    },
    focusSelectedTableRow() {
      this.$nextTick(() => {
        const panel = this.$refs.tablePanel;
        if (!panel) {
          return;
        }
        const selectedRow = panel.querySelector("tbody tr.selected");
        if (selectedRow) {
          selectedRow.scrollIntoView({ block: "nearest" });
        }
      });
    },
    toggleTableSort(sortKey) {
      if (this.tableSortKey === sortKey) {
        this.tableSortDirection = this.tableSortDirection === "asc" ? "desc" : "asc";
        return;
      }
      this.tableSortKey = sortKey;
      this.tableSortDirection = "asc";
    },
    tableCellValue(row, key) {
      return valueForColumn(row, key) || "-";
    },
    applySessionPayload(payload) {
      Object.assign(this, parseSessionState(payload));
      // Restored sessions carry the full inputs; keep multi-megabyte text out
      // of the textareas (see the note on tsvFromFile).
      this.tsvFromFile = this.tsvText.length > 50_000;
      this.tsvFileName = this.tsvFromFile ? "saved session" : "";
      this.metadataFromFile = this.metadataText.length > 50_000;
      this.metadataFileName = this.metadataFromFile ? "saved session" : "";
      this.nodeSearchActive = Boolean(this.nodeSearchQuery.trim());
      this.hoveredLegendValue = null;
      if (this.edgeLengthModeAuto && this.graphSource) {
        this.edgeLengthMode = this._autoEdgeLengthMode(this.graphSource);
      }
      this.fitView();
      if (this.lastData) {
        this.$nextTick(() => {
          this.redrawFromLastData();
        });
      }
    },
    _drawScaleBar(svg) {
      svg?.querySelector(".scale-bar")?.remove();
      if (!svg || !this.graphGroup) {
        return;
      }

      const viewScale = Number(this.view.scale) || 1;
      const minBarPx = 40;
      const maxBarPx = 150;
      const targetBarPx = 100;
      const candidates = [];

      for (let exponent = 0; exponent <= 6; exponent += 1) {
        const base = 10 ** exponent;
        candidates.push(base, 2 * base, 5 * base);
      }

      // Never label the ruler with a weight the data does not contain:
      // at strong zoom-out the rendered lengths of huge candidates happen
      // to land in the pixel range (e.g. "1000000 alleles" on a cgMLST
      // tree whose longest edge is ~600).
      const dataMax = Number(this.edgeWeightMax) || 0;
      const pool = dataMax
        ? candidates.filter((value) => value <= dataMax)
        : candidates;
      const allowed = pool.length ? pool : [Math.max(1, dataMax)];

      let barWeight = allowed[0];
      let bestInRange = null;
      let bestFallback = null;

      for (const value of allowed) {
        const renderedLength = this._edgeUnitFor && Number(this._edgeUnitPx) > 0
          ? this._edgeUnitFor(value) * Number(this._edgeUnitPx) * viewScale
          : edgeLength(value, this.edgeLengthMode, this.edgeLengthScale) * viewScale;
        const candidate = {
          value,
          renderedLength,
          distanceToTarget: Math.abs(renderedLength - targetBarPx),
        };
        if (renderedLength >= minBarPx && renderedLength <= maxBarPx) {
          if (!bestInRange || candidate.distanceToTarget < bestInRange.distanceToTarget) {
            bestInRange = candidate;
          }
          continue;
        }
        if (!bestFallback || candidate.distanceToTarget < bestFallback.distanceToTarget) {
          bestFallback = candidate;
        }
      }

      if (bestInRange) {
        barWeight = bestInRange.value;
      } else if (bestFallback) {
        barWeight = bestFallback.value;
      }

      const unitFor = this._edgeUnitFor;
      const unitPx = Number(this._edgeUnitPx) || 0;
      const barLen = unitFor && unitPx > 0
        ? unitFor(barWeight) * unitPx * viewScale
        : edgeLength(barWeight, this.edgeLengthMode, this.edgeLengthScale) * viewScale;
      if (barLen < 12) {
        return;  // too small to read; omit instead of drawing a fake ruler
      }
      const vb = svg.viewBox.baseVal;
      const svgH = vb.height || 900;
      const x = 30;
      const y = svgH - 30;
      const ns = "http://www.w3.org/2000/svg";

      const g = document.createElementNS(ns, "g");
      g.setAttribute("class", "scale-bar");
      g.setAttribute("transform", `translate(${x}, ${y})`);

      const bg = document.createElementNS(ns, "rect");
      bg.setAttribute("x", "-8");
      bg.setAttribute("y", "-22");
      bg.setAttribute("width", String(barLen + 16));
      bg.setAttribute("height", "30");
      bg.setAttribute("rx", "6");
      const gtheme = this.graphTheme();
      bg.setAttribute("fill", gtheme.scaleBg);
      bg.setAttribute("stroke", gtheme.scaleStroke);
      bg.setAttribute("stroke-width", "0.8");
      g.appendChild(bg);

      const line = document.createElementNS(ns, "line");
      line.setAttribute("x1", "0");
      line.setAttribute("y1", "0");
      line.setAttribute("x2", String(barLen));
      line.setAttribute("y2", "0");
      line.setAttribute("stroke", gtheme.edgeLabel);
      line.setAttribute("stroke-width", "2");
      g.appendChild(line);

      const leftTick = document.createElementNS(ns, "line");
      leftTick.setAttribute("x1", "0");
      leftTick.setAttribute("y1", "-5");
      leftTick.setAttribute("x2", "0");
      leftTick.setAttribute("y2", "5");
      leftTick.setAttribute("stroke", gtheme.edgeLabel);
      leftTick.setAttribute("stroke-width", "2");
      g.appendChild(leftTick);

      const rightTick = document.createElementNS(ns, "line");
      rightTick.setAttribute("x1", String(barLen));
      rightTick.setAttribute("y1", "-5");
      rightTick.setAttribute("x2", String(barLen));
      rightTick.setAttribute("y2", "5");
      rightTick.setAttribute("stroke", gtheme.edgeLabel);
      rightTick.setAttribute("stroke-width", "2");
      g.appendChild(rightTick);

      const text = document.createElementNS(ns, "text");
      text.setAttribute("x", String(barLen / 2));
      text.setAttribute("y", "-7");
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("font-size", "11");
      text.setAttribute("fill", gtheme.edgeLabel);
      text.setAttribute("font-family", '"IBM Plex Sans", sans-serif');
      text.setAttribute("font-weight", "500");
      text.textContent = `${barWeight} allele${barWeight > 1 ? "s" : ""}`;
      g.appendChild(text);

      svg.appendChild(g);
    },
    _getNodePosition(nodeId) {
      if (this.nodePositionOverrides[nodeId]) {
        return this.nodePositionOverrides[nodeId];
      }
      if (!this.currentLayout?.positions) {
        return null;
      }
      return this.currentLayout.positions.get(nodeId) || null;
    },
    applyOverlapRelief(nodes, edges, positions) {
      if (!this.overlapRelief || nodes.length <= 2) {
        return positions;
      }
      const simNodes = nodes
        .map((node) => {
          const point = positions.get(node.id);
          if (!point) {
            return null;
          }
          return {
            id: node.id,
            x: point[0],
            y: point[1],
            baseX: point[0],
            baseY: point[1],
            radius:
              nodeRadius(node, this.scaleNodeSize) *
              this.nodeScale *
              this._autoNodeScale,
          };
        })
        .filter(Boolean);
      const simNodeById = new Map(simNodes.map((node) => [node.id, node]));
      const simLinks = edges
        .filter((edge) => simNodeById.has(edge.source) && simNodeById.has(edge.target))
        .map((edge) => ({ source: edge.source, target: edge.target, weight: edge.weight }));

      const simulation = d3
        .forceSimulation(simNodes)
        .force(
          "x",
          d3
            .forceX((node) => node.baseX)
            .strength(0.18),
        )
        .force(
          "y",
          d3
            .forceY((node) => node.baseY)
            .strength(0.18),
        )
        .force(
          "link",
          d3
            .forceLink(simLinks)
            .id((node) => node.id)
            .distance((edge) => edgeLength(edge.weight, this.edgeLengthMode, this.edgeLengthScale) * 0.6)
            .strength(0.08),
        )
        .force(
          "collide",
          d3.forceCollide((node) => node.radius + 8).iterations(2),
        )
        .stop();

      const tickCount = Math.min(120, Math.max(30, nodes.length));
      for (let index = 0; index < tickCount; index += 1) {
        simulation.tick();
      }
      simulation.stop();

      const relaxed = new Map(positions);
      simNodes.forEach((node) => {
        if (!(node.id in this.nodePositionOverrides)) {
          relaxed.set(node.id, [node.x, node.y]);
        }
      });
      return relaxed;
    },
    computePositions(nodes, edges, layoutMode, rootId) {
      const nodeById = new Map(nodes.map((node) => [node.id, node]));
      const adjacency = new Map(nodes.map((node) => [node.id, []]));
      for (const edge of edges) {
        adjacency.get(edge.source)?.push({ id: edge.target, weight: edge.weight });
        adjacency.get(edge.target)?.push({ id: edge.source, weight: edge.weight });
      }

      const fallbackRoot = [...nodes].sort((left, right) => {
        const leftCount = Number(left.member_count || 1);
        const rightCount = Number(right.member_count || 1);
        if (rightCount !== leftCount) {
          return rightCount - leftCount;
        }
        return String(left.label).localeCompare(String(right.label));
      })[0]?.id;
      const requestedRoot = nodeById.has(this.manualRootId) ? this.manualRootId : rootId;
      const effectiveRoot = nodeById.has(requestedRoot) ? requestedRoot : fallbackRoot;

      const parent = new Map();
      const depth = new Map();
      const componentByNode = new Map();
      const children = new Map(nodes.map((node) => [node.id, []]));
      const componentRoots = [];
      const sortNeighbors = (left, right) => {
        const leftNode = nodeById.get(left.id);
        const rightNode = nodeById.get(right.id);
        const leftCount = Number(leftNode?.member_count || 1);
        const rightCount = Number(rightNode?.member_count || 1);
        if (rightCount !== leftCount) {
          return rightCount - leftCount;
        }
        if (left.weight !== right.weight) {
          return left.weight - right.weight;
        }
        return String(leftNode?.label || "").localeCompare(String(rightNode?.label || ""));
      };

      // Branch units: one global, monotonic mapping from allele distance to
      // drawn length. The same weight always gets the same length, whatever
      // the layout or the node sizes. Log keeps cgMLST's 1..3000 range
      // readable; sqrt and linear are available in the branch-length mode
      // selector.
      const maxLink = Math.max(
        1,
        ...edges.map((edge) => Number(edge.weight) || 0),
      );
      const unitFor = (weight) =>
        grapetreeGap(weight, maxLink, this.edgeLengthMode, 1);
      // Branch-length scale slider: ratios in data units (fitView then
      // normalises the drawing, so this changes branches relative to nodes).
      const layoutScale = Math.max(0.2, Number(this.edgeLengthScale) / 50);
      this._edgeUnitFor = unitFor;

      const linkWeightByChild = new Map();
      const visit = (startId, componentIndex) => {
        componentRoots.push(startId);
        const queue = [startId];
        parent.set(startId, -1);
        depth.set(startId, 0);
        componentByNode.set(startId, componentIndex);
        while (queue.length) {
          const current = queue.shift();
          const neighbors = [...(adjacency.get(current) || [])].sort(sortNeighbors);
          for (const next of neighbors) {
            if (parent.has(next.id)) {
              continue;
            }
            parent.set(next.id, current);
            linkWeightByChild.set(next.id, Number(next.weight) || 0);
            depth.set(
              next.id,
              (depth.get(current) || 0) + unitFor(next.weight),
            );
            componentByNode.set(next.id, componentIndex);
            children.get(current)?.push(next.id);
            queue.push(next.id);
          }
        }
      };

      if (effectiveRoot !== undefined) {
        visit(effectiveRoot, 0);
      }
      let componentIndex = componentRoots.length;
      for (const node of nodes) {
        if (!parent.has(node.id)) {
          visit(node.id, componentIndex);
          componentIndex += 1;
        }
      }

      const buildHierarchyNode = (rootId) => {
        const root = {
          id: rootId,
          label: nodeById.get(rootId)?.label || String(rootId),
          nodeRef: nodeById.get(rootId),
          children: [],
        };
        const pending = [root];
        while (pending.length > 0) {
          const current = pending.pop();
          for (const childId of children.get(current.id) || []) {
            const child = {
              id: childId,
              label: nodeById.get(childId)?.label || String(childId),
              nodeRef: nodeById.get(childId),
              children: [],
            };
            current.children.push(child);
            pending.push(child);
          }
        }
        return root;
      };

      const syntheticRoot = {
        id: "__root__",
        label: "__root__",
        children: componentRoots.map((nodeId) => buildHierarchyNode(nodeId)),
      };

      const hierarchy = d3.hierarchy(syntheticRoot);
      const separation = (left, right) => {
        const leftCount = Number(left.data.nodeRef?.member_count || 1);
        const rightCount = Number(right.data.nodeRef?.member_count || 1);
        const base = left.parent === right.parent ? 1 : 1.35;
        return base + Math.max(leftCount, rightCount) * 0.03;
      };

      const positions = new Map();
      if (layoutMode === "tree") {
        d3.tree().nodeSize([58, 1]).separation(separation)(hierarchy);
        const descendants = hierarchy.descendants().filter((node) => node.data.id !== "__root__");
        const maxWeightedDepth = Math.max(
          ...descendants.map((node) => depth.get(node.data.id) || 0),
          1,
        );
        const maxTreeY =
          Math.max(...descendants.map((node) => node.y), 1) * 180 * layoutScale;
        descendants.forEach((node) => {
          const weightedDepth = depth.get(node.data.id) || 0;
          node.y = maxWeightedDepth > 0 ? (weightedDepth / maxWeightedDepth) * maxTreeY : node.y * 180;
        });
        this._edgeUnitPx = maxTreeY / maxWeightedDepth;
        const minX = Math.min(...descendants.map((node) => node.x), 0);
        descendants.forEach((node) => {
          positions.set(node.data.id, [node.y, node.x - minX + 90]);
        });
        Object.entries(this.nodePositionOverrides).forEach(([nodeId, point]) => {
          if (positions.has(Number(nodeId))) {
            positions.set(Number(nodeId), point);
          }
        });
        // A tidy tree is already planar: force-based "overlap relief"
        // displaces nodes off the grid and makes edges cross, so it only
        // applies to the radial layout.
        return {
          positions,
          rootId: effectiveRoot,
          parent,
          depth,
          componentByNode,
          componentCount: componentRoots.length,
        };
      }

      if (layoutMode === "grapetree") {
        // GrapeTree layout with locked branch lengths. Each child is placed
        // *relative to its parent* at `radius(parent) + radius(child) +
        // gap(weight)`, so every edge of the same allele distance has the
        // same outline-to-outline length regardless of where it points.
        // Directions follow the tidy-tree leaf order, which spreads leaves
        // across the full circle instead of packing them into a narrow
        // wedge.
        const nodeRadiusById = new Map(
          nodes.map((node) => [
            node.id,
            nodeRadius(node, this.scaleNodeSize) *
              this.nodeScale *
              this._autoNodeScale,
          ]),
        );
        // Gap between the two node outlines; the slider is a linear
        // multiplier on the 500-unit link scale.
        const gapScale = Math.max(0.2, Number(this.edgeLengthScale) / 50);
        const gapOf = (weight) => unitFor(weight) * gapScale;
        d3.tree().nodeSize([58, 1]).separation(separation)(hierarchy);
        const tidyNodes = hierarchy
          .descendants()
          .filter((item) => item.data.id !== "__root__");
        const tidyXs = tidyNodes.map((item) => item.x);
        const minTidyX = Math.min(...tidyXs);
        const spanTidyX = Math.max(...tidyXs) - minTidyX || 1;
        const tidyAngle = new Map(
          tidyNodes.map((item) => [
            item.data.id,
            ((item.x - minTidyX) / spanTidyX) * 2 * Math.PI - Math.PI / 2,
          ]),
        );
        const graphPositions = new Map();
        const edgeDistance = (parentItem, childId) => {
          const parentRadius = nodeRadiusById.get(parentItem.data.id) ?? 0;
          const childRadius = nodeRadiusById.get(childId) ?? 10;
          return (
            parentRadius +
            childRadius +
            gapOf(linkWeightByChild.get(childId) || 0)
          );
        };

        const placeTree = (rootItem, rootOrigin) => {
          graphPositions.set(rootItem.data.id, rootOrigin);
          const pending = [[rootItem, rootOrigin]];
          while (pending.length > 0) {
            const [item, origin] = pending.pop();
            for (const kid of item.children || []) {
              const childId = kid.data.id;
              const direction = tidyAngle.get(childId) ?? 0;
              const distance = edgeDistance(item, childId);
              const childOrigin = [
                origin[0] + Math.cos(direction) * distance,
                origin[1] + Math.sin(direction) * distance,
              ];
              graphPositions.set(childId, childOrigin);
              pending.push([kid, childOrigin]);
            }
          }
        };

        const roots = hierarchy.children || [];
        roots.forEach((rootItem, index) => {
          // Usually a single component: park its root at the centre. A
          // forest is spread out so the trees do not overlap.
          const spread = (index - (roots.length - 1) / 2) * 2400;
          placeTree(rootItem, [LAYOUT_CENTER_X + spread, LAYOUT_CENTER_Y]);
        });

        Object.entries(this.nodePositionOverrides).forEach(([nodeId, point]) => {
          if (graphPositions.has(Number(nodeId))) {
            graphPositions.set(Number(nodeId), point);
          }
        });
        this._edgeUnitFor = gapOf;
        this._edgeUnitPx = 1;
        return {
          positions: graphPositions,
          rootId: effectiveRoot,
          parent,
          depth,
          componentByNode,
          componentCount: componentRoots.length,
        };
      }

      // Radial layout derived from the same tidy tree: the angle comes
      // from the tidy x-ordering (sibling subtrees occupy disjoint angular
      // sectors) and the radius from accumulated weighted depth. This keeps
      // the drawing planar by construction — the previous greedy radial
      // allocation could place a parent and child at overlapping angles.
      d3.tree().nodeSize([58, 1]).separation(separation)(hierarchy);
      const radialDescendants = hierarchy
        .descendants()
        .filter((node) => node.data.id !== "__root__");
      const radialMaxDepth = Math.max(
        ...radialDescendants.map((node) => depth.get(node.data.id) || 0),
        1,
      );
      this._edgeUnitPx =
        (LAYOUT_MAX_RADIUS * layoutScale) / radialMaxDepth;
      const radialXs = radialDescendants.map((node) => node.x);
      const radialMinX = Math.min(...radialXs);
      const radialSpanX = Math.max(...radialXs) - radialMinX || 1;
      const radialPositions = new Map();
      radialDescendants.forEach((node) => {
        const angle =
          ((node.x - radialMinX) / radialSpanX) * 2 * Math.PI - Math.PI / 2;
        const radius =
          ((depth.get(node.data.id) || 0) / radialMaxDepth) *
          LAYOUT_MAX_RADIUS *
          layoutScale;
        radialPositions.set(node.data.id, [
          LAYOUT_CENTER_X + radius * Math.cos(angle),
          LAYOUT_CENTER_Y + radius * Math.sin(angle),
        ]);
      });
      // No force-based displacement: it moves nodes off their rings and
      // turns the radial tree into crossing chords. Overlap tuning is
      // available explicitly via the "nudge" switch (opt-in).
      const componentByNodeRadial = componentByNode;
      const componentCountRadial = componentRoots.length;
      Object.entries(this.nodePositionOverrides).forEach(([nodeId, point]) => {
        if (radialPositions.has(Number(nodeId))) {
          radialPositions.set(Number(nodeId), point);
        }
      });
      return {
        positions: this.overlapRelief
          ? this.applyOverlapRelief(nodes, edges, radialPositions)
          : radialPositions,
        rootId: effectiveRoot,
        parent,
        depth,
        componentByNode: componentByNodeRadial,
        componentCount: componentCountRadial,
      };
    },
    filterRenderedGraph(nodes, edges, layoutData) {
      if (!this.inspectedItem?.nodeId || this.viewFilterMode === "all") {
        return { nodes, edges };
      }
      if (this.viewFilterMode === "component") {
        const componentId = layoutData.componentByNode.get(this.inspectedItem.nodeId);
        const visibleNodeIds = new Set(
          nodes
            .filter((node) => layoutData.componentByNode.get(node.id) === componentId)
            .map((node) => node.id),
        );
        return {
          nodes: nodes.filter((node) => visibleNodeIds.has(node.id)),
          edges: edges.filter(
            (edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target),
          ),
        };
      }
      if (this.viewFilterMode === "path") {
        const visibleNodeIds = highlightedPathNodes(this.inspectedItem.nodeId, layoutData.parent);
        const visibleEdgeKeys = highlightedPathEdges(this.inspectedItem.nodeId, layoutData.parent, edgeKey);
        return {
          nodes: nodes.filter((node) => visibleNodeIds.has(node.id)),
          edges: edges.filter((edge) => visibleEdgeKeys.has(edge.edgeKey)),
        };
      }
      return { nodes, edges };
    },
    refreshInspectionSummary(layoutData) {
      const lines = [];
      lines.push(`root id: ${layoutData.rootId ?? "-"}`);
      lines.push(`components: ${layoutData.componentCount}`);
      lines.push(`view filter: ${this.viewFilterMode}`);
      lines.push(`layout mode: ${this.layoutMode}`);
      if (this.manualRootId !== null) {
        lines.push(`manual root override: ${this.manualRootId}`);
      }
      if (Object.keys(this.nodePositionOverrides).length > 0) {
        lines.push(`dragged nodes: ${Object.keys(this.nodePositionOverrides).length}`);
      }
      this.inspectedItem = {
        kind: "layout",
        title: "Layout diagnostics",
        lines,
      };
    },
    _prepareGraphData(rawNodes, rawEdges) {
      const activeGraph = this.aggregateNodes
        ? aggregateGraph(rawNodes, rawEdges)
        : { nodes: rawNodes, edges: rawEdges };
      // Dense graphs need smaller circles relative to branch lengths,
      // otherwise neighbouring leaves overlap; the user can still scale
      // them with the node-size slider.
      this._autoNodeScale = autoNodeScale(activeGraph.nodes.length);
      const maxWeight = parseMaxWeight(this.maxWeight);
      const visibleEdges = filteredEdges(activeGraph.edges, maxWeight);
      const fullLayoutData = this.computePositions(
        activeGraph.nodes,
        visibleEdges,
        this.layoutMode,
        this.graphSource?.layout?.root_id,
      );
      const collapseSet = resolveCollapsedNodeSet(
        activeGraph.nodes,
        visibleEdges,
        fullLayoutData.parent,
        this.collapsedNodes,
        this.collapseThreshold,
        edgeKey,
      );
      let graphNodes = activeGraph.nodes;
      let graphEdges = visibleEdges;
      if (collapseSet.size > 0) {
        const childMap = new Map();
        for (const edge of graphEdges) {
          const sourceParent = fullLayoutData.parent.get(edge.source);
          const targetParent = fullLayoutData.parent.get(edge.target);
          if (sourceParent === edge.target) {
            if (!childMap.has(edge.target)) {
              childMap.set(edge.target, []);
            }
            childMap.get(edge.target).push(edge.source);
          }
          if (targetParent === edge.source) {
            if (!childMap.has(edge.source)) {
              childMap.set(edge.source, []);
            }
            childMap.get(edge.source).push(edge.target);
          }
        }
        const removed = new Set();
        const queue = [];
        for (const nodeId of collapseSet) {
          queue.push(...(childMap.get(Number(nodeId)) || []));
        }
        while (queue.length) {
          const nodeId = queue.shift();
          if (removed.has(nodeId)) {
            continue;
          }
          removed.add(nodeId);
          queue.push(...(childMap.get(nodeId) || []));
        }
        graphNodes = graphNodes.filter((node) => !removed.has(node.id));
        graphEdges = graphEdges.filter(
          (edge) => !removed.has(edge.source) && !removed.has(edge.target),
        );
      }
      const hiddenIds = new Set(
        Object.keys(this._hiddenNodeIds).filter((k) => this._hiddenNodeIds[k]),
      );
      if (hiddenIds.size > 0) {
        graphNodes = graphNodes.filter((node) => !hiddenIds.has(String(node.id)));
        graphEdges = graphEdges.filter(
          (edge) => !hiddenIds.has(String(edge.source)) && !hiddenIds.has(String(edge.target)),
        );
      }
      const layoutData = collapseSet.size > 0
        ? this.computePositions(
          graphNodes,
          graphEdges,
          this.layoutMode,
          this.graphSource?.layout?.root_id,
        )
        : fullLayoutData;
      const colorMap = colorMapFor(activeGraph.nodes, this.colorBy, this.colorScheme);
      const selectedNode = selectedNodeId(this.inspectedItem);
      const highlightedEdgeKeys =
        this.correctnessOverlay && this.inspectedItem?.kind === "node"
          ? highlightedPathEdges(this.inspectedItem.nodeId, layoutData.parent, edgeKey)
          : new Set();
      const searchQuery = this.nodeSearchQuery.trim().toLowerCase();
      const hasSearch = this.nodeSearchActive && searchQuery.length > 0;
      const hiddenValues = new Set(
        Object.keys(this.hiddenLegendValues).filter((value) => this.hiddenLegendValues[value]),
      );
      const hoveredValue = this.hoveredLegendValue;
      const colorByField = this.colorBy;
      const renderedNodes = graphNodes
        .filter((node) => !this.clusterFilter || String(node.cluster_id) === String(this.clusterFilter))
        .map((node) => {
          const point = layoutData.positions.get(node.id);
          if (!point) {
            return null;
          }
          const isRoot = layoutData.rootId === node.id;
          const sameComponent =
            this.inspectedItem?.kind === "node"
              ? layoutData.componentByNode.get(this.inspectedItem.nodeId) ===
                layoutData.componentByNode.get(node.id)
              : true;
          const nodeLabel = String(node.label || "");
          const legendValue = colorValueForNode(node, this.colorBy);
          const legendSelect = this._legendSelectValue
            ? legendValue === this._legendSelectValue
            : true;
          const searchMatch = (hasSearch ? nodeLabel.toLowerCase().includes(searchQuery) : true) && legendSelect;
          const searchDimmed = (hasSearch ? !nodeLabel.toLowerCase().includes(searchQuery) : false) || (this._legendSelectValue ? legendValue !== this._legendSelectValue : false);
          const legendDimmed = hiddenValues.size > 0 && this.colorBy
            ? hiddenValues.has(legendValue)
            : false;
          return {
            ...node,
            x: point[0],
            y: point[1],
            color: this._customNodeColors[String(node.id)] || colorMap.get(legendValue) || "#2563eb",
            radius:
              nodeRadius(node, this.scaleNodeSize) *
              this.nodeScale *
              this._autoNodeScale,
            isRoot,
            sameComponent,
            isSelected:
              selectedNode === node.id
              || this.multiSelectedNodeIds.includes(String(node.id)),
            searchMatch,
            searchDimmed:
              (hasSearch ? !searchMatch : false)
              || !this.timelineNodeVisible(node),
            legendDimmed,
          };
        })
        .filter(Boolean);
      const renderedNodeById = new Map(renderedNodes.map((node) => [node.id, node]));
      const renderedEdges = graphEdges
        .map((edge) => {
          const sourcePoint = layoutData.positions.get(edge.source);
          const targetPoint = layoutData.positions.get(edge.target);
          const sourceNode = renderedNodeById.get(edge.source);
          const targetNode = renderedNodeById.get(edge.target);
          if (!sourcePoint || !targetPoint || !sourceNode || !targetNode) {
            return null;
          }
          const edgeKeyValue = edgeKey(edge.source, edge.target);
          const inHighlightedPath = highlightedEdgeKeys.has(edgeKeyValue);
          const sameComponent =
            layoutData.componentByNode.get(edge.source) === layoutData.componentByNode.get(edge.target);
          return {
            ...edge,
            sourcePoint,
            targetPoint,
            midX: (sourcePoint[0] + targetPoint[0]) / 2,
            midY: (sourcePoint[1] + targetPoint[1]) / 2,
            edgeKey: edgeKeyValue,
            inHighlightedPath,
            sameComponent,
            sourceClusterId: sourceNode.cluster_id,
            targetClusterId: targetNode.cluster_id,
            searchDimmed: hasSearch
              ? Boolean(sourceNode.searchDimmed || targetNode.searchDimmed)
              : false,
            legendDimmed: Boolean(sourceNode.legendDimmed || targetNode.legendDimmed),
          };
        })
        .filter(
          (edge) =>
            !this.clusterFilter ||
            (String(edge.sourceClusterId) === String(this.clusterFilter) &&
              String(edge.targetClusterId) === String(this.clusterFilter)),
        )
        .filter(Boolean);
      const edgeWeightGraph = this.filterRenderedGraph(renderedNodes, renderedEdges, layoutData);
      const weightExtent = d3.extent(edgeWeightGraph.edges, (edge) => Number(edge.weight) || 0);
      const minEdgeWeight = weightExtent[0] ?? 0;
      const maxEdgeWeight = weightExtent[1] ?? 0;
      const finalGraph = {
        nodes: edgeWeightGraph.nodes,
        edges: filteredEdges(edgeWeightGraph.edges, maxWeight),
      };
      return {
        activeGraph,
        visibleEdges,
        graphNodes,
        graphEdges,
        layoutData,
        fullLayoutData,
        colorMap,
        renderedNodes,
        renderedEdges,
        finalGraph,
        edgeWeightGraph,
        collapseSet,
        selectedNode,
        highlightedEdgeKeys,
        searchQuery,
        hasSearch,
        hiddenValues,
        hoveredValue,
        colorByField,
        minEdgeWeight,
        maxEdgeWeight,
      };
    },
    _syncGraphState(prepared) {
      const {
        activeGraph,
        visibleEdges,
        layoutData,
        fullLayoutData,
        colorMap,
        finalGraph,
        edgeWeightGraph,
      } = prepared;
      this.currentLayout = fullLayoutData;
      this.currentCollapseSourceGraph = {
        nodes: activeGraph.nodes,
        edges: visibleEdges,
      };
      if (!this.tooltip.visible) {
        this.refreshInspectionSummary(fullLayoutData);
      }
      this.updateLegend(colorMap, activeGraph.nodes, this.colorBy);
      this.currentEdgeWeightGraph = {
        nodes: edgeWeightGraph.nodes,
        edges: edgeWeightGraph.edges,
        layout: {
          root_id: layoutData.rootId,
          component_count: layoutData.componentCount,
          mode: this.layoutMode,
          manual_root_id: this.manualRootId,
          view_filter_mode: this.viewFilterMode,
        },
      };
      this.currentRenderedGraph = {
        nodes: finalGraph.nodes,
        edges: finalGraph.edges,
        layout: {
          root_id: layoutData.rootId,
          component_count: layoutData.componentCount,
          mode: this.layoutMode,
          manual_root_id: this.manualRootId,
          view_filter_mode: this.viewFilterMode,
        },
      };
    },
    _createGraphScaffold() {
      const svg = this.$refs.svg;
      this.graphGroup = d3.select(svg).append("g").node();
      this.applyViewTransform();
      const graph = d3.select(this.graphGroup);
      const defsSeed = `viz-${Date.now()}-${Math.floor(Math.random() * 1000000)}`;
      const nodeShadowId = `${defsSeed}-node-shadow`;
      const nodeGlowId = `${defsSeed}-node-glow`;
      const defs = graph.append("defs");
      const shadowFilter = defs
        .append("filter")
        .attr("id", nodeShadowId)
        .attr("x", "-40%")
        .attr("y", "-40%")
        .attr("width", "180%")
        .attr("height", "180%");
      shadowFilter.append("feDropShadow").attr("dx", 0).attr("dy", 1).attr("stdDeviation", 1.6).attr("flood-color", "#0f172a").attr("flood-opacity", 0.28);
      const glowFilter = defs
        .append("filter")
        .attr("id", nodeGlowId)
        .attr("x", "-90%")
        .attr("y", "-90%")
        .attr("width", "280%")
        .attr("height", "280%");
      glowFilter.append("feDropShadow").attr("dx", 0).attr("dy", 0).attr("stdDeviation", 2.5).attr("flood-color", "#f59e0b").attr("flood-opacity", 0.85);
      const setTooltipAccent = (accentColor) => {
        const tooltipEl = this.$refs.canvas?.querySelector(".tooltip");
        if (tooltipEl) {
          tooltipEl.style.setProperty("--tooltip-accent", accentColor || "#3b82f6");
        }
      };
      return {
        svg,
        graph,
        nodeShadowId,
        nodeGlowId,
        setTooltipAccent,
      };
    },
    _buildRenderContext(prepared, scaffold) {
      const {
        layoutData,
        collapseSet,
        selectedNode,
        highlightedEdgeKeys,
        hasSearch,
        searchQuery,
        hiddenValues,
        hoveredValue,
        colorByField,
        minEdgeWeight,
        maxEdgeWeight,
        colorMap,
      } = prepared;
      const { nodeShadowId, nodeGlowId, setTooltipAccent } = scaffold;
      this.edgeWeightMax = maxEdgeWeight;
      if (this.edgeWeightThreshold > maxEdgeWeight) {
        this.edgeWeightThreshold = 0;
        this.maxWeight = "";
      }
      const edgeWeightSpan = Math.max(1, maxEdgeWeight - minEdgeWeight);
      const edgeShade = d3.scaleLinear().domain([minEdgeWeight, maxEdgeWeight]).range([0.9, 0.25]);
      const longBranchThreshold = this.longBranchThreshold;
      const longBranchMode = this.longBranchMode;
      const isLongBranch = (edge) =>
        longBranchMode !== "normal" && longBranchThreshold > 0 && Number(edge.weight) > longBranchThreshold;
      const edgeOpacity = (edge) => {
        if (edge.searchDimmed) {
          return 0.1;
        }
        if (edge.legendDimmed) {
          return 0.08;
        }
        if (longBranchMode === "hide" && isLongBranch(edge)) {
          return 0;
        }
        if (hasSearch) {
          return 1;
        }
        return edge.sameComponent ? 1 : 0.4;
      };
      const nodeGroupClass = (node, baseClass = "node") => {
        const classes = [baseClass];
        if (hasSearch && node.searchMatch) {
          classes.push("search-match");
        }
        if (hasSearch && node.searchDimmed) {
          classes.push("search-dimmed");
        }
        return classes.join(" ");
      };
      const nodeGroupOpacity = (node) => {
        if (node.searchDimmed) {
          return 0.2;
        }
        if (node.legendDimmed) {
          return 0.18;
        }
        return 1;
      };
      const nodeContentOpacity = (node) => {
        if (hasSearch) {
          return 1;
        }
        return this.correctnessOverlay && !node.sameComponent ? 0.45 : 1;
      };
      const labelOpacity = (node) => {
        if (node.searchDimmed) {
          return 0.15;
        }
        if (node.legendDimmed) {
          return 0.12;
        }
        if (hasSearch) {
          return 1;
        }
        return this.correctnessOverlay && !node.sameComponent ? 0.45 : 1;
      };
      return {
        hasSearch,
        searchQuery,
        hiddenValues,
        hoveredValue,
        colorByField,
        selectedNode,
        highlightedEdgeKeys,
        parentMap: layoutData.parent,
        edgeShade,
        edgeWeightSpan,
        minEdgeWeight,
        edgeOpacity,
        nodeGroupClass,
        nodeGroupOpacity,
        nodeContentOpacity,
        labelOpacity,
        setTooltipAccent,
        nodeShadowId,
        nodeGlowId,
        isLongBranch,
        longBranchMode,
        colorMap,
        collapseSet,
      };
    },
    _renderEdgeGroup(graph, finalGraph, context) {
      const {
        edgeShade,
        edgeWeightSpan,
        minEdgeWeight,
        edgeOpacity,
        setTooltipAccent,
        isLongBranch,
        longBranchMode,
      } = context;
      const gtheme = this.graphTheme();
      const edgeStroke = (edge) => {
        if (edge.inHighlightedPath) {
          return "#dc2626";
        }
        if (!edge.sameComponent) {
          return gtheme.edgeWeak;
        }
        const shade = edgeShade(Number(edge.weight) || 0);
        return d3.interpolateRgb(gtheme.edgeMin, gtheme.edgeMax)(shade);
      };
      const edgeStrokeWidth = (edge) => {
        if (edge.inHighlightedPath) {
          return 3.2;
        }
        // Near-distance links (0-1 alleles) read as thin connectors;
        // thicker strokes are reserved for long inter-cluster jumps.
        const normalized = ((Number(edge.weight) || 0) - minEdgeWeight) / edgeWeightSpan;
        return 1.2 + normalized * 1.0;
      };
      const edgeStrokeDasharray = (edge) => {
        if (longBranchMode === "shorten" && isLongBranch(edge)) {
          return "3 6";
        }
        const normalized = ((Number(edge.weight) || 0) - minEdgeWeight) / edgeWeightSpan;
        return normalized >= 0.72 ? "5 4" : null;
      };
      const edgeGroup = graph.append("g").attr("class", "edges");
      const edgeHover = (_event, edge) => {
        setTooltipAccent("#334155");
        this.showEdgeTooltip(edge, _event);
      };
      if (this.layoutMode === "tree") {
        // Classic rectangular phylogram drawn from the hierarchy only:
        //  - one horizontal branch per tree edge (length = allele distance)
        //    at the child's row,
        //  - one thin vertical connector per parent spanning its children's
        //    rows (pure scaffolding).
        // Non-tree edges (grapetree shortcuts / chords) cannot be drawn in
        // a tree layout without crossing, so they are omitted and reported.
        const parentMap = context.parentMap || new Map();
        const isTreeEdge = (edge) =>
          parentMap.get(edge.target) === edge.source ||
          parentMap.get(edge.source) === edge.target;
        const treeEdges = finalGraph.edges.filter(isTreeEdge);
        const hidden = finalGraph.edges.length - treeEdges.length;
        if (hidden !== this.hiddenNonTreeEdges) {
          this.hiddenNonTreeEdges = hidden;
        }

        // MST edges are stored in arbitrary order; orient each one from
        // the hierarchy parent to the child so the horizontal branch sits
        // on the child's row and the connector starts exactly at the
        // parent's x.
        const oriented = treeEdges.map((edge) => {
          const forward = parentMap.get(edge.target) === edge.source;
          return {
            edge,
            parentId: forward ? edge.source : edge.target,
            parentPoint: forward ? edge.sourcePoint : edge.targetPoint,
            childPoint: forward ? edge.targetPoint : edge.sourcePoint,
          };
        });
        const connectors = new Map();
        for (const item of oriented) {
          const entry = connectors.get(item.parentId) || {
            x: item.parentPoint[0],
            ys: [],
          };
          entry.ys.push(item.childPoint[1]);
          connectors.set(item.parentId, entry);
        }
        edgeGroup
          .append("g")
          .attr("class", "edge-connectors")
          .selectAll("line")
          .data([...connectors.values()])
          .enter()
          .append("line")
          .attr("x1", (item) => item.x)
          .attr("x2", (item) => item.x)
          .attr("y1", (item) => Math.min(...item.ys))
          .attr("y2", (item) => Math.max(...item.ys))
          .attr("stroke", gtheme.edgeConnector)
          .attr("stroke-width", 0.9)
          .attr("stroke-opacity", 0.75)
          .style("pointer-events", "none");

        edgeGroup
          .selectAll("path.edge-branch")
          .data(
            oriented.filter(
              (item) =>
                Number(item.edge.weight) > 0 &&
                item.childPoint[0] - item.parentPoint[0] >= 1,
            ),
          )
          .enter()
          .append("path")
          .attr("class", "edge-branch")
          .attr("fill", "none")
          .attr(
            "d",
            (item) =>
              `M${item.parentPoint[0]},${item.childPoint[1]} H${item.childPoint[0]}`,
          )
          .attr("stroke", (item) => edgeStroke(item.edge))
          .attr("stroke-width", (item) => edgeStrokeWidth(item.edge))
          .attr("stroke-dasharray", (item) => edgeStrokeDasharray(item.edge))
          .attr("stroke-linecap", "round")
          .attr("stroke-opacity", edgeOpacity)
          .on("mousemove", (_event, item) => edgeHover(_event, item.edge))
          .on("mouseleave", this.hideTooltip);
      } else if (this.layoutMode === "grapetree") {
        // GrapeTree draws plain links: the distance between the two node
        // centres already equals node radii + scaled allele distance, so a
        // straight line is exactly proportional to the branch.
        edgeGroup
          .selectAll("line.edge-grapetree")
          .data(finalGraph.edges)
          .enter()
          .append("line")
          .attr("class", "edge-grapetree")
          .attr("data-weight", (edge) => Number(edge.weight) || 0)
          .attr("x1", (edge) => edge.sourcePoint[0])
          .attr("y1", (edge) => edge.sourcePoint[1])
          .attr("x2", (edge) => edge.targetPoint[0])
          .attr("y2", (edge) => edge.targetPoint[1])
          .attr("stroke", (edge) => edgeStroke(edge))
          .attr("stroke-width", (edge) => edgeStrokeWidth(edge))
          .attr("stroke-dasharray", (edge) => edgeStrokeDasharray(edge))
          .attr("stroke-linecap", "round")
          .attr("stroke-opacity", (edge) => edgeOpacity(edge))
          .on("mousemove", edgeHover)
          .on("mouseleave", this.hideTooltip);
      } else {
        // Radial phylogram: the radial segment encodes the branch length
        // (straight chords mix in the tangential displacement, which made
        // 1-allele and 500-allele branches look alike); the circular arc is
        // layout scaffolding drawn thin and muted.
        const centre = { x: LAYOUT_CENTER_X, y: LAYOUT_CENTER_Y };
        const polar = (point) => ({
          angle: Math.atan2(point[1] - centre.y, point[0] - centre.x),
          radius: Math.hypot(point[0] - centre.x, point[1] - centre.y),
        });
        const toXY = (angle, radius) => [
          centre.x + radius * Math.cos(angle),
          centre.y + radius * Math.sin(angle),
        ];
        const parentMap = context.parentMap || new Map();
        const orientedRadial = finalGraph.edges.map((edge) => {
          const forward = parentMap.get(edge.target) === edge.source;
          const parentPolar = polar(forward ? edge.sourcePoint : edge.targetPoint);
          const childPolar = polar(forward ? edge.targetPoint : edge.sourcePoint);
          const delta = Math.atan2(
            Math.sin(childPolar.angle - parentPolar.angle),
            Math.cos(childPolar.angle - parentPolar.angle),
          );
          return {
            edge,
            parentPolar,
            childPolar,
            delta,
            radialFrom: toXY(parentPolar.angle, parentPolar.radius),
            radialTo: toXY(parentPolar.angle, childPolar.radius),
            arcFrom: toXY(parentPolar.angle, childPolar.radius),
            arcTo: toXY(childPolar.angle, childPolar.radius),
          };
        });

        edgeGroup
          .selectAll("path.edge-arc")
          .data(orientedRadial.filter((item) => Math.abs(item.delta) > 1e-4))
          .enter()
          .append("path")
          .attr("class", "edge-arc")
          .attr("fill", "none")
          .attr("d", (item) => {
            const largeArc = Math.abs(item.delta) > Math.PI ? 1 : 0;
            const sweep = item.delta > 0 ? 1 : 0;
            return `M${item.arcFrom[0]},${item.arcFrom[1]} A${item.childPolar.radius},${item.childPolar.radius} 0 ${largeArc} ${sweep} ${item.arcTo[0]},${item.arcTo[1]}`;
          })
          .attr("stroke", gtheme.edgeConnector)
          .attr("stroke-width", 0.9)
          .attr("stroke-opacity", 0.75)
          .style("pointer-events", "none");

        edgeGroup
          .selectAll("path.edge-branch-radial")
          .data(
            orientedRadial.filter(
              (item) => item.childPolar.radius - item.parentPolar.radius > 0.5,
            ),
          )
          .enter()
          .append("path")
          .attr("class", "edge-branch-radial")
          .attr("fill", "none")
          .attr(
            "d",
            (item) =>
              `M${item.radialFrom[0]},${item.radialFrom[1]} L${item.radialTo[0]},${item.radialTo[1]}`,
          )
          .attr("stroke", (item) => edgeStroke(item.edge))
          .attr("stroke-width", (item) => edgeStrokeWidth(item.edge))
          .attr("stroke-dasharray", (item) => edgeStrokeDasharray(item.edge))
          .attr("stroke-linecap", "round")
          .attr("stroke-opacity", (item) => edgeOpacity(item.edge))
          .on("mousemove", (_event, item) => edgeHover(_event, item.edge))
          .on("mouseleave", this.hideTooltip);
      }
    },
    _renderEdgeLabels(graph, finalGraph, context) {
      if (!this.showEdgeLabels) {
        return;
      }
      const { setTooltipAccent } = context;
      const gtheme = this.graphTheme();
      const edgeLabelGroup = graph
        .append("g")
        .attr("class", "edge-labels")
        .selectAll("g")
        // In the tree layout a zero-weight branch has zero length and is not
        // drawn, so its label would float without a line.
        .data(
          this.layoutMode === "tree"
            ? finalGraph.edges.filter((edge) => Number(edge.weight) > 0)
            : finalGraph.edges,
        )
        .enter()
        .append("g")
        .attr("class", "edge-label")
        .attr("transform", (edge) => {
          const parentMap = context.parentMap || new Map();
          const forward = parentMap.get(edge.target) === edge.source;
          const parentPoint = forward ? edge.sourcePoint : edge.targetPoint;
          const childPoint = forward ? edge.targetPoint : edge.sourcePoint;
          if (this.layoutMode === "tree") {
            const x = (parentPoint[0] + childPoint[0]) / 2;
            return `translate(${x}, ${childPoint[1] - 8})`;
          }
          if (this.layoutMode === "grapetree") {
            const x = (parentPoint[0] + childPoint[0]) / 2;
            const y = (parentPoint[1] + childPoint[1]) / 2;
            return `translate(${x}, ${y - 8})`;
          }
          const centreX = LAYOUT_CENTER_X;
          const centreY = LAYOUT_CENTER_Y;
          const parentRadius = Math.hypot(
            parentPoint[0] - centreX,
            parentPoint[1] - centreY,
          );
          const childRadius = Math.hypot(
            childPoint[0] - centreX,
            childPoint[1] - centreY,
          );
          const midRadius = (parentRadius + childRadius) / 2;
          const angle = Math.atan2(
            parentPoint[1] - centreY,
            parentPoint[0] - centreX,
          );
          const x = centreX + midRadius * Math.cos(angle);
          const y = centreY + midRadius * Math.sin(angle);
          return `translate(${x}, ${y - 8})`;
        })
        .attr("opacity", (edge) => {
          if (edge.searchDimmed) {
            return 0.1;
          }
          if (edge.legendDimmed) {
            return 0.08;
          }
          return 1;
        })
        .on("mousemove", (_event, edge) => {
          setTooltipAccent("#334155");
          this.showEdgeTooltip(edge, _event);
        })
        .on("mouseleave", this.hideTooltip);
      edgeLabelGroup
        .append("text")
        .attr("x", 0)
        .attr("y", 2)
        .attr("font-size", 9)
        .attr("font-weight", 700)
        .attr("fill", "none")
        .attr("stroke", gtheme.labelHalo)
        .attr("stroke-width", 3.5)
        .attr("stroke-linejoin", "round")
        .attr("text-anchor", "middle")
        .text((edge) => edge.weight);
      edgeLabelGroup
        .append("text")
        .attr("x", 0)
        .attr("y", 2)
        .attr("font-size", 9)
        .attr("font-weight", 600)
        .attr("fill", gtheme.edgeLabel)
        .attr("text-anchor", "middle")
        .text((edge) => edge.weight);
      edgeLabelGroup.attr("data-overlap-hidden", (edge) => {
        const labelX = edge.midX;
        const labelY = edge.midY;
        for (const node of finalGraph.nodes) {
          const dx = labelX - node.x;
          const dy = labelY - node.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < node.radius + 12) {
            return "1";
          }
        }
        return "0";
      });
      edgeLabelGroup.style("display", (edge) => {
        const labelX = edge.midX;
        const labelY = edge.midY;
        for (const node of finalGraph.nodes) {
          const dx = labelX - node.x;
          const dy = labelY - node.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < node.radius + 12) {
            return "none";
          }
        }
        if (!this.showEdgeLabels) {
          return "none";
        }
        return null;
      });
    },
    _renderHalos(graph, finalGraph, context) {
      const { hasSearch, nodeGlowId } = context;
      const gtheme = this.graphTheme();
      const haloGroup = graph.append("g").attr("class", "halos");
      haloGroup
        .selectAll("path")
        .data(finalGraph.nodes.filter((node) => node.isRoot || node.isSelected))
        .enter()
        .append("path")
        .attr("d", (node) => {
          const outerR = node.radius + (node.isSelected ? 9 : 7);
          const innerR = node.radius + (node.isSelected ? 5 : 3);
          const arc = d3
            .arc()
            .innerRadius(innerR)
            .outerRadius(outerR)
            .startAngle(0)
            .endAngle(2 * Math.PI);
          return arc();
        })
        .attr("transform", (node) => `translate(${node.x},${node.y})`)
        .attr("fill", (node) => {
          if (node.isSelected) {
            return "rgba(245, 158, 11, 0.85)";
          }
          return gtheme.ring;
        })
        .attr("stroke", (node) =>
          node.isSelected ? "#fbbf24" : gtheme.ringStroke,
        )
        .attr("stroke-width", (node) => (node.isSelected ? 1.5 : 0))
        .attr("stroke-dasharray", (node) => (node.isRoot ? "2 5" : null))
        .attr("opacity", (node) => {
          if (node.searchDimmed) {
            return 0.12;
          }
          if (node.legendDimmed) {
            return 0.1;
          }
          if (hasSearch) {
            return node.isSelected ? 0.95 : 0.7;
          }
          if (this.correctnessOverlay && !node.sameComponent) {
            return 0.3;
          }
          return node.isSelected ? 0.95 : 0.7;
        })
        .attr("filter", (node) => (node.isSelected ? `url(#${nodeGlowId})` : null));
    },
    _renderNodes(graph, finalGraph, context) {
      const {
        hasSearch,
        nodeGroupClass,
        nodeGroupOpacity,
        nodeContentOpacity,
        setTooltipAccent,
        nodeShadowId,
        nodeGlowId,
        colorMap,
        collapseSet,
      } = context;
      const nodesGroup = graph.append("g").attr("class", "nodes").attr("filter", `url(#${nodeShadowId})`);
      const pieNodes = finalGraph.nodes.filter((n) => {
        if (!this.colorBy) {
          return false;
        }
        const breakdown = n.meta_breakdown?.[this.colorBy];
        return breakdown && Object.keys(breakdown).length > 1;
      });
      const circleNodes = finalGraph.nodes.filter((n) => !pieNodes.includes(n));
      const createNodeGroups = (selection, baseClass, useSelectedFilter = false) => {
        const groups = selection
          .enter()
          .append("g")
          .attr("class", (node) => nodeGroupClass(node, baseClass))
          .attr("transform", (node) => `translate(${node.x},${node.y})`)
          .attr("opacity", nodeGroupOpacity)
          .style("cursor", "pointer")
          .attr("data-legend-value", (node) => colorValueForNode(node, this.colorBy))
          .attr("data-node-color", (node) => node.color)
          .attr("data-radius", (node) => node.radius)
          .attr("data-dimmed", (node) => node.legendDimmed || node.searchDimmed ? "1" : "0")
          .on("mousemove", (_event, node) => {
            setTooltipAccent(node.color);
            this.showTooltip(node, _event);
          })
          .on("mouseleave", this.hideTooltip)
          .on("dblclick", (event, node) => {
            event.stopPropagation();
            this.toggleNodeCollapse(node.id);
          });
        if (useSelectedFilter) {
          groups.attr("filter", (node) => (node.isSelected ? `url(#${nodeGlowId})` : null));
        }
        groups
          .filter((node) => hasSearch && node.searchMatch && !node.searchDimmed)
          .append("circle")
          .attr("class", "search-ring")
          .attr("r", (node) => node.radius + (node.isSelected ? 6 : 4))
          .attr("fill", "none")
          .attr("stroke", "#f59e0b")
          .attr("stroke-width", 2.2)
          .attr("stroke-opacity", 0.85);
        return groups;
      };
      const circleNodeGroups = createNodeGroups(
        nodesGroup.selectAll("g.node").data(circleNodes),
        "node",
      );
      circleNodeGroups
        .each((node, i, elems) => {
          const group = d3.select(elems[i]);
          const r = node.radius + (node.isSelected ? 2 : 0);
          const fillColor = node.color;
          const strokeFn = (nd) => {
            if (nd.isSelected) return '#fbbf24';
            if (this.correctnessOverlay && nd.isRoot) return '#0f172a';
            return 'rgba(255,255,255,0.7)';
          };
          if (this.shapeBy && node.meta?.[this.shapeBy] !== undefined) {
            const shapeIdx = this.shapeIndexFor(node.meta[this.shapeBy]);
            group.append('path')
              .attr('d', nodeShapePath(shapeIdx, r))
              .attr('fill', fillColor)
              .attr('stroke', strokeFn)
              .attr('stroke-width', 1.2);
          } else {
            group.append('circle')
              .attr('r', r)
              .attr('fill', fillColor);
          }
        })
        .attr("stroke", (node) => {
          if (node.isSelected) {
            return "#fbbf24";
          }
          if (this.correctnessOverlay && node.isRoot) {
            return "#0f172a";
          }
          return "#ffffff";
        })
        .attr("stroke-width", (node) => {
          if (node.isSelected) {
            return 3.6;
          }
          return this.correctnessOverlay && node.isRoot ? 3.2 : 1.5;
        })
        .attr("filter", (node) => (node.isSelected ? `url(#${nodeGlowId})` : null))
        .attr("opacity", nodeContentOpacity)
        .style("transition", "r 0.15s ease");
      circleNodeGroups
        .filter((node) => collapseSet.has(String(node.id)))
        .append("text")
        .attr("class", "collapse-badge")
        .attr("x", (node) => node.radius + 6)
        .attr("y", 4)
        .attr("font-size", 13)
        .attr("font-weight", 700)
        .attr("fill", "#f59e0b")
        .text("+");
      const pieNodeGroups = createNodeGroups(
        nodesGroup.selectAll("g.pie-node").data(pieNodes),
        "pie-node",
        true,
      );
      pieNodeGroups.each((nodeData, i, elements) => {
        const breakdown = nodeData.meta_breakdown[this.colorBy];
        const entries = Object.entries(breakdown).map(([value, count]) => ({
          value: count,
          color: colorMap.get(value) || "#2563eb",
        }));
        const pie = d3.pie().value((d) => d.value).sort(null).padAngle(0.02);
        const arc = d3.arc().innerRadius(0).outerRadius(nodeData.radius + (nodeData.isSelected ? 2 : 0));
        const slices = d3
          .select(elements[i])
          .selectAll("path")
          .data(pie(entries))
          .enter()
          .append("path")
          .attr("d", arc)
          .attr("fill", (d) => d.data.color)
          .attr("stroke", "#ffffff")
          .attr("stroke-width", 1)
          .attr("opacity", nodeContentOpacity(nodeData));
        if (nodeData.isSelected) {
          slices.attr("stroke", "#fbbf24").attr("stroke-width", 2);
        }
      });
      pieNodeGroups
        .filter((node) => collapseSet.has(String(node.id)))
        .append("text")
        .attr("class", "collapse-badge")
        .attr("x", (node) => node.radius + 6)
        .attr("y", 4)
        .attr("font-size", 13)
        .attr("font-weight", 700)
        .attr("fill", "#f59e0b")
        .text("+");
    },
    _renderLabels(graph, finalGraph, context) {
      if (!this.showNodeLabels) {
        return;
      }
      const { labelOpacity } = context;
      const labelText = new Map(
        finalGraph.nodes.map((node) => [node.id, this.nodeLabelText(node)]),
      );
      const labelGroup = graph
        .append("g")
        .attr("class", "labels")
        .selectAll("g")
        .data(finalGraph.nodes)
        .enter()
        .append("g")
        .attr("transform", (node) => `translate(${node.x + node.radius + 5}, ${node.y})`)
        .attr("opacity", labelOpacity);
      const gtheme = this.graphTheme();
      labelGroup
        .append("rect")
        .attr("x", -3)
        .attr("y", (node) => (node.isRoot ? -11 : -10))
        .attr("width", (node) => labelText.get(node.id).length * 7 + 10)
        .attr("height", (node) => (node.isRoot ? 18 : 16))
        .attr("rx", 8)
        .attr("fill", gtheme.labelBg)
        .attr("stroke", gtheme.labelStroke)
        .attr("stroke-width", 0.7);
      labelGroup
        .append("text")
        .attr("x", 2)
        .attr("y", 4)
        .attr("font-size", (node) => (node.isRoot ? 12.8 : 12))
        .attr("fill", (node) =>
          node.isRoot ? gtheme.labelTextStrong : gtheme.labelText,
        )
        .attr("font-weight", (node) => (node.isRoot ? 700 : 500))
        .text((node) => labelText.get(node.id));
    },
    _renderHitAreas(graph, finalGraph, context) {
      const { setTooltipAccent } = context;
      graph
        .append("g")
        .attr("class", "node-hit-area")
        .selectAll("circle")
        .data(finalGraph.nodes)
        .enter()
        .append("circle")
        .attr("cx", (node) => node.x)
        .attr("cy", (node) => node.y)
        .attr("r", (node) => node.radius + 6)
        .attr("fill", "transparent")
        .style("cursor", "pointer")
        .on("mousemove", (_event, node) => {
          setTooltipAccent(node.color);
          this.showTooltip(node, _event);
        })
        .on("mouseleave", this.hideTooltip)
        .on("click", (_event, node) => {
          if (_event.shiftKey) {
            _event.stopPropagation();
            this.openNodeColorPicker(node.id, node.color);
            return;
          }
          if (_event.ctrlKey || _event.metaKey) {
            _event.stopPropagation();
            this.toggleMultiSelect(node.id);
            return;
          }
          if (this._pendingNodeClick) {
            window.clearTimeout(this._pendingNodeClick);
          }
          this._pendingNodeClick = window.setTimeout(() => {
            this._pendingNodeClick = null;
            this.selectGraphNode(node);
          }, 220);
        })
        .on("dblclick", (event, node) => {
          event.stopPropagation();
          if (this._pendingNodeClick) {
            window.clearTimeout(this._pendingNodeClick);
            this._pendingNodeClick = null;
          }
          this.toggleNodeCollapse(node.id);
        })
        .on("contextmenu", (event, node) => {
          event.preventDefault();
          event.stopPropagation();
          this.hideNode(node.id);
        })
        .call(
          d3
            .drag()
            .on("start", (event) => {
              event.sourceEvent.stopPropagation();
            })
            .on("drag", (event, node) => {
              event.sourceEvent.stopPropagation();
              const point = this.eventClientPoint(event);
              const localPoint = point ? this.clientPointToGraph(point) : null;
              if (!localPoint) {
                return;
              }
              const layout = this.currentLayout;
              if (!layout || !layout.parent) {
                this.nodePositionOverrides = {
                  ...this.nodePositionOverrides,
                  [node.id]: [localPoint.x, localPoint.y],
                };
                this.redrawFromLastData();
                return;
              }
              const oldX = this.nodePositionOverrides[node.id]?.[0] ?? node.x;
              const oldY = this.nodePositionOverrides[node.id]?.[1] ?? node.y;
              const newX = localPoint.x;
              const newY = localPoint.y;
              const dx = newX - oldX;
              const dy = newY - oldY;
              if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) {
                return;
              }
              const descendants = getDescendants(node.id, layout.parent);
              const overrides = { ...this.nodePositionOverrides };
              overrides[node.id] = [newX, newY];
              for (const childId of descendants) {
                const currentPos = this._getNodePosition(childId);
                if (currentPos) {
                  overrides[childId] = [currentPos[0] + dx, currentPos[1] + dy];
                }
              }
              this.nodePositionOverrides = overrides;
              this.redrawFromLastData();
            }),
        );
    },
    drawGraph(rawNodes, rawEdges) {
      this.clearSvg();
      if (!rawNodes.length) {
        return;
      }
      const prepared = this._prepareGraphData(rawNodes, rawEdges);
      this._syncGraphState(prepared);
      const { finalGraph } = prepared;
      this._graphBounds = graphBounds(finalGraph.nodes);
      const { svg, graph, ...scaffold } = this._createGraphScaffold();
      const context = this._buildRenderContext(prepared, scaffold);
      this._renderEdgeGroup(graph, finalGraph, context);
      this._renderEdgeLabels(graph, finalGraph, context);
      this._renderHalos(graph, finalGraph, context);
      this._renderNodes(graph, finalGraph, context);
      this._renderHitAreas(graph, finalGraph, context);
      this._renderLabels(graph, finalGraph, context);
      this.updateSummary(
        finalGraph.nodes.length,
        finalGraph.edges.length,
        this.graphSource?.sample_count || rawNodes.length,
      );
      this._drawScaleBar(svg);
      this._applyLegendHover();
      if (this.view.scale === 1 && this.view.tx === 0 && this.view.ty === 0) {
        this.$nextTick(() => {
          this.fitView();
        });
      }
    },
    changeLayoutMode() {
      // Each layout uses its own coordinate space (ring radii, tree depth,
      // GrapeTree node radii + gaps), so the previous zoom would leave the
      // new drawing tiny or clipped. Refit right after the redraw.
      this.redrawFromLastData();
      this.fitView();
    },
    redrawFromLastData() {
      if (
        !this.graphSource ||
        !Array.isArray(this.graphSource.nodes) ||
        !Array.isArray(this.graphSource.edges)
      ) {
        this.clearSvg();
        return;
      }
      this.drawGraph(this.graphSource.nodes, this.graphSource.edges);
    },
    debouncedRedraw() {
      clearTimeout(this._debounceTimer);
      this._debounceTimer = setTimeout(() => this.redrawFromLastData(), 50);
    },
    _resetViewState(data, view) {
      this.analysisView = view;
      this.lastData = data;
      this.currentRenderedGraph = null;
      this.currentEdgeWeightGraph = null;
      this.currentCollapseSourceGraph = null;
      this.currentLayout = null;
      this.metadataFields = data.metadata_fields || [];
      this.tableRows = data.table_rows || [];
      this.clusterFilter = "";
      this.compareLeftLabel = "";
      this.compareRightLabel = "";
      this.locusDiff = null;
      this.suggestedColorFields = data.suggested_color_fields || [];
      if (
        this.colorBy &&
        this.colorBy !== "cluster_id" &&
        !this.metadataFields.includes(this.colorBy)
      ) {
        this.colorBy = "";
      }
      if (!this.colorBy && data.default_color_field) {
        this.colorBy = data.default_color_field;
      }
    },
    async buildMst() {
      if (this._building) return;
      this._building = true;
      try {
        this.setStatus("ok", "Building MST...");
        const data = await fetchMst({
          tsv: this.tsvText,
          metadataTsv: this.metadataText,
          includeMissing: this.includeMissing,
          aggregateProfiles: this.aggregateProfiles,
        });

        this._resetViewState(data, "graph");
        this.graphData = data;
        if (this.edgeLengthModeAuto) {
          this.edgeLengthMode = this._autoEdgeLengthMode(data);
        }
        this.manualRootId = null;
        this.nodePositionOverrides = {};
        if ((data.nodes || []).length > 1500) {
          // Thousands of SVG text labels are unreadable and slow; keep the
          // graph responsive and let the user opt back in.
          this.showNodeLabels = false;
          this.showEdgeLabels = false;
        }
        this.clusterSummary = data.cluster_summary || [];
        this.heatmapLocusQuery = "";
        this.edgeWeightThreshold = this.maxWeight ? Number(this.maxWeight) : 0;
        this.fitView();
        await this.$nextTick();
        this.redrawFromLastData();
        this.buildError = "";
        this.setStatus(
          "ok",
          this.aggregateProfiles ? "Profile MST rendered" : "Sample MST rendered",
        );
      } catch (error) {
        this.statsLine = `Error: ${error.message}`;
        this.buildError = error.message || "Failed to build MST";
        this.setStatus("error", error.message || "Failed to build MST");
        this.clearSvg();
      } finally {
        this._building = false;
      }
    },
    async buildDistanceMatrix() {
      if (this._building) return;
      this._building = true;
      try {
        this.setStatus("ok", "Building distance matrix...");
        const data = await fetchDistanceMatrix({
          tsv: this.tsvText,
          metadataTsv: this.metadataText,
          includeMissing: this.includeMissing,
          aggregateProfiles: this.aggregateProfiles,
        });

        this._resetViewState(data, "matrix");
        this.clusterSummary = data.cluster_summary || [];
        this.distanceMatrix = data.matrix || [];
        this.matrixLabels = data.labels || [];
        this.clearSvg();
        this.updateSummary(this.matrixLabels.length, "-", this.matrixLabels.length);
        this.statsLine = `Rendered ${this.matrixLabels.length} × ${this.matrixLabels.length} distance matrix.`;
        this.buildError = "";
        this.setStatus("ok", "Distance matrix rendered");
      } catch (error) {
        this.statsLine = `Error: ${error.message}`;
        this.buildError = error.message || "Failed to build distance matrix";
        this.setStatus("error", error.message || "Failed to build distance matrix");
        this.clearSvg();
      } finally {
        this._building = false;
      }
    },
    async buildAlleleHeatmap() {
      if (this._building) return;
      this._building = true;
      try {
        this.setStatus("ok", "Building allele heatmap...");
        const data = await fetchAlleleHeatmap({
          tsv: this.tsvText,
          metadataTsv: this.metadataText,
          aggregateProfiles: this.aggregateProfiles,
        });

        this._resetViewState(data, "heatmap");
        this.clusterSummary = [];
        this.matrixLabels = data.labels || [];
        this.heatmapLoci = data.loci || [];
        this.heatmapCells = data.cells || [];
        this.heatmapLocusQuery = "";
        this.clearSvg();
        this.updateSummary(this.matrixLabels.length, "-", this.matrixLabels.length);
        this.statsLine = `Rendered ${this.matrixLabels.length} × ${this.heatmapLoci.length} allele heatmap.`;
        this.buildError = "";
        this.setStatus("ok", "Allele heatmap rendered");
      } catch (error) {
        this.statsLine = `Error: ${error.message}`;
        this.buildError = error.message || "Failed to build allele heatmap";
        this.setStatus("error", error.message || "Failed to build allele heatmap");
        this.clearSvg();
      } finally {
        this._building = false;
      }
    },
    resetSession() {
      if (!window.confirm("Clear the loaded data and the current analysis result?")) {
        return;
      }
      this.tsvText = "";
      this.tsvFromFile = false;
      this.tsvFileName = "";
      this.metadataText = "";
      this.metadataFromFile = false;
      this.metadataFileName = "";
      this.compareLeftTsv = "";
      this.compareRightTsv = "";
      this.lastData = null;
      this.graphData = null;
      this.distanceMatrix = [];
      this.matrixLabels = [];
      this.heatmapLoci = [];
      this.heatmapCells = [];
      this.compareResultsSummary = null;
      this.compareResultRows = [];
      this.compareStatusFilter = "";
      this.clusterSummary = [];
      this.buildError = "";
      this.analysisView = "graph";
      this.statsLine = "";
      this.updateSummary(0, 0, 0);
      this.setStatus("idle", "Load a profile TSV to begin");
      this.clearSvg();
      const fileInput = document.getElementById("file-input");
      if (fileInput) {
        fileInput.value = "";
      }
    },
    openCompareWorkflow() {
      const details = this.$refs.compareWorkflow;
      if (details) {
        details.open = true;
        details.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
      this.$nextTick(() => {
        const leftInput = document.getElementById("compare-left-tsv");
        if (leftInput) {
          leftInput.focus();
        }
      });
    },
    async compareResults() {
      if (this._building) return;
      this._building = true;
      try {
        this.setStatus("ok", "Comparing result sets...");
        const data = await fetchCompareResults({
          leftTsv: this.compareLeftTsv,
          rightTsv: this.compareRightTsv,
        });

        this.analysisView = "compare";
        this.currentRenderedGraph = null;
        this.currentEdgeWeightGraph = null;
        this.currentCollapseSourceGraph = null;
        this.compareResultsSummary = data.summary;
        this.compareResultRows = data.rows || [];
        this.compareStatusFilter = "";
        this.clearSvg();
        this.statsLine = `Compared ${data.rows.length} samples across two result sets.`;
        this.buildError = "";
        this.buildError = "";
        this.setStatus("ok", "Comparison summary rendered");
      } catch (error) {
        this.statsLine = `Error: ${error.message}`;
        this.buildError = error.message || "Failed to compare result sets";
        this.setStatus("error", error.message || "Failed to compare result sets");
      } finally {
        this._building = false;
      }
    },
    handleWheel(event) {
      event.preventDefault();
      if (!this.graphGroup) {
        return;
      }
      const point = this.eventClientPoint(event);
      const svgPoint = point ? this.clientPointToSvg(point) : null;
      const multiplier = event.deltaY < 0 ? 1.1 : 0.9;
      const oldScale = this.view.scale;
      const newScale = Math.min(6, Math.max(0.25, oldScale * multiplier));
      if (svgPoint && newScale !== oldScale) {
        const scaleRatio = newScale / oldScale;
        this.view.tx = svgPoint.x - (svgPoint.x - this.view.tx) * scaleRatio;
        this.view.ty = svgPoint.y - (svgPoint.y - this.view.ty) * scaleRatio;
      }
      this.view.scale = newScale;
      this.applyViewTransform();
    },
    zoomIn() {
      const oldScale = this.view.scale;
      const newScale = Math.min(6, oldScale * 1.2);
      if (newScale === oldScale) return;
      const cx = 700, cy = 450;
      const ratio = newScale / oldScale;
      this.view.tx = cx - (cx - this.view.tx) * ratio;
      this.view.ty = cy - (cy - this.view.ty) * ratio;
      this.view.scale = newScale;
      this.applyViewTransform();
    },
    zoomOut() {
      const oldScale = this.view.scale;
      const newScale = Math.max(0.25, oldScale * 0.8);
      if (newScale === oldScale) return;
      const cx = 700, cy = 450;
      const ratio = newScale / oldScale;
      this.view.tx = cx - (cx - this.view.tx) * ratio;
      this.view.ty = cy - (cy - this.view.ty) * ratio;
      this.view.scale = newScale;
      this.applyViewTransform();
    },
    onMouseDown(event) {
      const point = this.eventClientPoint(event);
      const svgPoint = point ? this.clientPointToSvg(point) : null;
      if (!svgPoint) {
        return;
      }
      this.dragging = true;
      this.dragStart = {
        x: svgPoint.x,
        y: svgPoint.y,
        tx: this.view.tx,
        ty: this.view.ty,
      };
      this.$refs.canvas.classList.add("dragging");
      this.hideTooltip();
    },
    onMouseMove(event) {
      if (!this.dragging || !this.dragStart) {
        return;
      }
      const point = this.eventClientPoint(event);
      const svgPoint = point ? this.clientPointToSvg(point) : null;
      if (!svgPoint) {
        return;
      }
      const dx = svgPoint.x - this.dragStart.x;
      const dy = svgPoint.y - this.dragStart.y;
      this.view.tx = this.dragStart.tx + dx;
      this.view.ty = this.dragStart.ty + dy;
      if (!this._dragRaf) {
        this._dragRaf = requestAnimationFrame(() => {
          this.applyViewTransform();
          this._dragRaf = null;
        });
      }
    },
    onMouseUp() {
      this.dragging = false;
      this.dragStart = null;
      if (this._dragRaf) {
        cancelAnimationFrame(this._dragRaf);
        this._dragRaf = null;
      }
      this.applyViewTransform();
      const canvas = this.$refs.canvas;
      if (canvas) {
        canvas.classList.remove("dragging");
      }
    },
    onTouchStart(event) {
      if (!this.graphGroup) return;
      if (event.touches.length === 1) {
        event.preventDefault();
        const point = this.eventClientPoint(event);
        const svgPoint = point ? this.clientPointToSvg(point) : null;
        if (!svgPoint) return;
        this.dragging = true;
        this.dragStart = { x: svgPoint.x, y: svgPoint.y, tx: this.view.tx, ty: this.view.ty };
        this.$refs.canvas?.classList.add("dragging");
        this.hideTooltip();
      } else if (event.touches.length === 2) {
        event.preventDefault();
        this.dragging = false;
        this.dragStart = null;
        const t0 = event.touches[0], t1 = event.touches[1];
        this._pinchStart = {
          dist: Math.hypot(t1.clientX - t0.clientX, t1.clientY - t0.clientY),
          scale: this.view.scale,
          tx: this.view.tx,
          ty: this.view.ty,
          cx: (t0.clientX + t1.clientX) / 2,
          cy: (t0.clientY + t1.clientY) / 2,
        };
      }
    },
    onTouchMove(event) {
      if (event.touches.length === 1 && this.dragging && this.dragStart) {
        event.preventDefault();
        const point = this.eventClientPoint(event);
        const svgPoint = point ? this.clientPointToSvg(point) : null;
        if (!svgPoint) return;
        this.view.tx = this.dragStart.tx + (svgPoint.x - this.dragStart.x);
        this.view.ty = this.dragStart.ty + (svgPoint.y - this.dragStart.y);
        if (!this._dragRaf) {
          this._dragRaf = requestAnimationFrame(() => {
            this.applyViewTransform();
    this._dragRaf = null;
    this._pinchStart = null;
          });
        }
      } else if (event.touches.length === 2 && this._pinchStart) {
        event.preventDefault();
        const t0 = event.touches[0], t1 = event.touches[1];
        const dist = Math.hypot(t1.clientX - t0.clientX, t1.clientY - t0.clientY);
        const ratio = dist / (this._pinchStart.dist || 1);
        const newScale = Math.min(6, Math.max(0.25, this._pinchStart.scale * ratio));
        const svgPoint = this.clientPointToSvg({ x: this._pinchStart.cx, y: this._pinchStart.cy });
        if (svgPoint) {
          const scaleRatio = newScale / this._pinchStart.scale;
          this.view.tx = svgPoint.x - (svgPoint.x - this._pinchStart.tx) * scaleRatio;
          this.view.ty = svgPoint.y - (svgPoint.y - this._pinchStart.ty) * scaleRatio;
        }
        this.view.scale = newScale;
        this.applyViewTransform();
      }
    },
    onTouchEnd(event) {
      if (event.touches.length < 2) {
        this._pinchStart = null;
      }
      if (event.touches.length === 0) {
        this.dragging = false;
        this.dragStart = null;
        if (this._dragRaf) {
          cancelAnimationFrame(this._dragRaf);
          this._dragRaf = null;
        }
        this.applyViewTransform();
        this.$refs.canvas?.classList.remove("dragging");
      }
    },
    _downloadBlob(filename, blob) {
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    },
    exportSvg() {
      const svg = this.$refs.svg;
      const raw = new XMLSerializer().serializeToString(svg);
      const content = `<?xml version="1.0" encoding="UTF-8"?>\n${raw}`;
      this._downloadBlob("gmlst_mst.svg", new Blob([content], { type: "image/svg+xml;charset=utf-8" }));
      this.setStatus("ok", "SVG exported");
    },
    async exportPng(scale = 2) {
      const svg = this.$refs.svg;
      if (!svg) {
        this.setStatus("error", "Build a graph before exporting PNG");
        return;
      }
      const bbox = svg.getBoundingClientRect();
      const width = Math.ceil(bbox.width);
      const height = Math.ceil(bbox.height);
      const raw = new XMLSerializer().serializeToString(svg);
      const svgUrl = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(raw)}`;
      const img = new Image();
      await new Promise((resolve, reject) => {
        img.onload = resolve;
        img.onerror = reject;
        img.src = svgUrl;
      });
      const canvas = document.createElement("canvas");
      canvas.width = width * scale;
      canvas.height = height * scale;
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = getComputedStyle(document.documentElement)
        .getPropertyValue("--graph-bg")
        .trim() || "#ffffff";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      canvas.toBlob((blob) => {
        if (blob) {
          this._downloadBlob("gmlst_mst.png", blob);
          this.setStatus("ok", "PNG exported");
        }
      }, "image/png");
    },
    downloadJson(filename, payload) {
      this._downloadBlob(
        filename,
        new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" }),
      );
    },
    exportNewick() {
      if (!this.currentLayout || !this.currentRenderedGraph) {
        this.setStatus("error", "Build a graph before exporting Newick");
        return;
      }
      const newick = buildNewickString(this.currentLayout, this.currentRenderedGraph);
      if (!newick) {
        this.setStatus("error", "No root node found for Newick export");
        return;
      }
      this._downloadBlob("gmlst_tree.nwk", newickBlob(newick));
      this.setStatus("ok", "Newick tree exported");
    },
    exportGraphJson() {
      if (!this.graphSource || !this.currentRenderedGraph) {
        this.setStatus("error", "Build a graph before exporting JSON");
        return;
      }
      this.downloadJson(
        "gmlst_graph.json",
        buildGraphJsonPayload(
          this.graphSource.export?.schema_version,
          this.currentRenderedGraph,
        ),
      );
      this.setStatus("ok", "Current graph JSON exported");
    },
    exportTableTsv() {
      if (!this.filteredTableRows.length) {
        this.setStatus("error", "Build or filter a graph before exporting table TSV");
        return;
      }
      this._downloadBlob("gmlst_table.tsv", new Blob([tableRowsToTsv(this.filteredTableRows, this.tableColumns)], {
        type: "text/tab-separated-values;charset=utf-8",
      }));
      this.setStatus("ok", "Table TSV exported");
    },
    matrixTitle(rowLabel, colLabel, value) {
      return matrixCellTitle(rowLabel, colLabel, value);
    },
    heatmapClass(state) {
      return heatmapCellClass(state);
    },
    async compareLoci() {
      if (!this.compareLeftLabel || !this.compareRightLabel) {
        this.setStatus("error", "Choose two samples to compare");
        return;
      }
      try {
        const data = await fetchCompareLoci({
          tsv: this.tsvText,
          metadataTsv: this.metadataText,
          includeMissing: this.includeMissing,
          leftLabel: this.compareLeftLabel,
          rightLabel: this.compareRightLabel,
        });
        this.locusDiff = data;
        this.setStatus("ok", "Locus difference report ready");
      } catch (error) {
        this.setStatus("error", error.message || "Failed to compare loci");
      }
    },
    async triggerCompareFromPair(leftLabel, rightLabel) {
      const payload = compareRequestFromSelection(leftLabel, rightLabel);
      if (!payload) {
        return;
      }
      this.compareLeftLabel = payload.left_label;
      this.compareRightLabel = payload.right_label;
      await this.compareLoci();
    },
    exportCompareJson() {
      if (!this.locusDiff) {
        this.setStatus("error", "Run a locus comparison before exporting");
        return;
      }
      this._downloadBlob("gmlst_locus_diff.json", new Blob([comparePayloadToJson(this.locusDiff)], {
        type: "application/json;charset=utf-8",
      }));
      this.setStatus("ok", "Locus diff JSON exported");
    },
    fillCompareFromPair(leftLabel, rightLabel) {
      const next = compareSelectionFromPair(
        this.compareLeftLabel,
        this.compareRightLabel,
        leftLabel,
        rightLabel,
      );
      this.compareLeftLabel = next.left;
      this.compareRightLabel = next.right;
    },
    exportHeatmapTsv() {
      const lociView = this.filteredHeatmapLociView;
      const labels = this.filteredHeatmapView.labels;
      if (!labels.length || !lociView.loci.length) {
        this.setStatus("error", "Build or filter an allele heatmap before exporting TSV");
        return;
      }
      this._downloadBlob("gmlst_heatmap.tsv", new Blob([heatmapToTsv(labels, lociView.loci, lociView.cells)], {
        type: "text/tab-separated-values;charset=utf-8",
      }));
      this.setStatus("ok", "Heatmap TSV exported");
    },
    exportHeatmapJson() {
      const lociView = this.filteredHeatmapLociView;
      const labels = this.filteredHeatmapView.labels;
      if (!labels.length || !lociView.loci.length) {
        this.setStatus("error", "Build or filter an allele heatmap before exporting JSON");
        return;
      }
      this._downloadBlob("gmlst_heatmap.json", new Blob(
        [heatmapPayloadToJson({ labels, loci: lociView.loci, cells: lociView.cells })],
        { type: "application/json;charset=utf-8" },
      ));
      this.setStatus("ok", "Heatmap JSON exported");
    },
    exportSessionJson() {
      if (!this.graphSource) {
        this.setStatus("error", "Build a graph before exporting session JSON");
        return;
      }
      this.downloadJson("gmlst_session.json", buildSessionJsonPayload(this));
      this.setStatus("ok", "Session JSON exported");
    },
  },
};
</script>

<template>
  <div class="app-root">
    <header class="topbar card">
      <div class="topbar-brand">
        <h1>{{ title }}</h1>
        <p class="topbar-subtitle">MST workspace</p>
      </div>
      <button
        class="theme-toggle"
        :aria-label="`Theme: ${theme}`"
        :title="`Theme: ${theme} (click to cycle)`"
        type="button"
        @click="cycleTheme"
      >
        <svg v-if="theme === 'light'" viewBox="0 0 20 20" fill="currentColor" width="16" height="16" aria-hidden="true">
          <path d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4.95 2.05a1 1 0 010 1.41l-.7.7a1 1 0 11-1.42-1.4l.71-.71a1 1 0 011.41 0zM18 10a1 1 0 01-1 1h-1a1 1 0 110-2h1a1 1 0 011 1zm-3.05 4.95a1 1 0 01-1.41 0l-.71-.7a1 1 0 111.42-1.42l.7.71a1 1 0 010 1.41zM10 16a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zm-4.95-1.05a1 1 0 010 1.41 1 1 0 01-1.41 0l-.71-.7a1 1 0 111.42-1.42l.7.71zM2 10a1 1 0 011-1h1a1 1 0 110 2H3a1 1 0 01-1-1zm1.05-5.66a1 1 0 011.41 0l.71.71A1 1 0 013.75 6.34l-.7-.7a1 1 0 010-1.3zM10 6a4 4 0 100 8 4 4 0 000-8z"/>
        </svg>
        <svg v-else-if="theme === 'dark'" viewBox="0 0 20 20" fill="currentColor" width="16" height="16" aria-hidden="true">
          <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z"/>
        </svg>
        <svg v-else viewBox="0 0 20 20" fill="currentColor" width="16" height="16" aria-hidden="true">
          <path d="M10 2a8 8 0 100 16 8 8 0 000-16zm1 2.07A6 6 0 0111 15.93V4.07z"/>
        </svg>
      </button>
      <button
        class="theme-toggle"
        :aria-label="isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'"
        :title="isFullscreen ? 'Exit fullscreen (Esc)' : 'Enter fullscreen'"
        type="button"
        @click="toggleFullscreen"
      >
        <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16" aria-hidden="true">
          <path v-if="!isFullscreen" d="M3 3h5v2H5v3H3V3zm9 0h5v5h-2V5h-3V3zM3 12h2v3h3v2H3v-5zm12 3v-3h2v5h-5v-2h3z"/>
          <path v-else d="M7 3v4H3V5h2V3h2zm6 0h2v2h2v2h-4V3zM3 13h4v4H5v-2H3v-2zm12 0h2v2h-2v2h-2v-4h2z"/>
        </svg>
      </button>
      <nav v-if="lastData" class="view-tabs" aria-label="Analysis view switcher">
        <button
          v-for="tab in viewTabs"
          :key="tab.id"
          class="view-tab"
          :class="{
            active: analysisView === tab.id,
            'is-unbuilt': !viewAvailable(tab.id) || !isViewBuilt(tab.id),
          }"
          :aria-label="tab.label"
          :aria-pressed="String(analysisView === tab.id)"
          :disabled="!viewAvailable(tab.id)"
          :title="viewBuildHint(tab.id)"
          type="button"
          @click="switchAnalysisView(tab.id)"
        >
          <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <template v-if="tab.id === 'graph'">
              <path
                d="M4 4.5 8 8l4-4"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <path
                d="M8 8 4 11.5"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <circle cx="4" cy="4.5" r="1.5" stroke="currentColor" stroke-width="1.5" />
              <circle cx="8" cy="8" r="1.5" stroke="currentColor" stroke-width="1.5" />
              <circle cx="12" cy="4" r="1.5" stroke="currentColor" stroke-width="1.5" />
              <circle cx="4" cy="11.5" r="1.5" stroke="currentColor" stroke-width="1.5" />
            </template>
            <template v-else-if="tab.id === 'matrix'">
              <rect
                x="2.5"
                y="2.5"
                width="4"
                height="4"
                rx="0.75"
                stroke="currentColor"
                stroke-width="1.5"
              />
              <rect
                x="9.5"
                y="2.5"
                width="4"
                height="4"
                rx="0.75"
                stroke="currentColor"
                stroke-width="1.5"
              />
              <rect
                x="2.5"
                y="9.5"
                width="4"
                height="4"
                rx="0.75"
                stroke="currentColor"
                stroke-width="1.5"
              />
              <rect
                x="9.5"
                y="9.5"
                width="4"
                height="4"
                rx="0.75"
                stroke="currentColor"
                stroke-width="1.5"
              />
            </template>
            <template v-else-if="tab.id === 'heatmap'">
              <rect x="2" y="2.5" width="3.25" height="4" rx="0.75" fill="currentColor" opacity="0.35" />
              <rect x="6.375" y="2.5" width="3.25" height="4" rx="0.75" fill="currentColor" opacity="0.65" />
              <rect x="10.75" y="2.5" width="3.25" height="4" rx="0.75" fill="currentColor" />
              <rect x="2" y="9.5" width="3.25" height="4" rx="0.75" fill="currentColor" opacity="0.2" />
              <rect x="6.375" y="9.5" width="3.25" height="4" rx="0.75" fill="currentColor" opacity="0.5" />
              <rect x="10.75" y="9.5" width="3.25" height="4" rx="0.75" fill="currentColor" opacity="0.82" />
            </template>
            <template v-else-if="tab.id === 'summary'">
              <rect x="2" y="2.5" width="12" height="2.5" rx="1.25" fill="currentColor" opacity="0.3" />
              <rect x="2" y="6.5" width="9" height="2.5" rx="1.25" fill="currentColor" opacity="0.5" />
              <rect x="2" y="10.5" width="11" height="2.5" rx="1.25" fill="currentColor" opacity="0.7" />
            </template>
            <template v-else-if="tab.id === 'stats'">
              <path d="M3 13.5 3 9 6.5 9 6.5 13.5" stroke="currentColor" stroke-width="1.4" fill="none" />
              <path d="M6.75 13.5 6.75 3.5 10.25 3.5 10.25 13.5" stroke="currentColor" stroke-width="1.4" fill="none" />
              <path d="M10.5 13.5 10.5 6.5 14 6.5 14 13.5" stroke="currentColor" stroke-width="1.4" fill="none" />
            </template>
            <template v-else>
              <rect
                x="2.5"
                y="4"
                width="7"
                height="8"
                rx="1"
                stroke="currentColor"
                stroke-width="1.5"
              />
              <rect
                x="6.5"
                y="2.5"
                width="7"
                height="8"
                rx="1"
                stroke="currentColor"
                stroke-width="1.5"
              />
            </template>
          </svg>
          <span>{{ tab.label }}</span>
        </button>
      </nav>
      <span class="status-pill" :class="statusKindClass">{{ statusMessage }}</span>
    </header>

    <main class="layout" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
      <aside class="sidebar card" :class="{ collapsed: sidebarCollapsed }" aria-label="Analysis controls">
        <button
          class="sidebar-toggle"
          type="button"
          :aria-expanded="String(!sidebarCollapsed)"
          :title="sidebarCollapsed ? 'Expand controls' : 'Collapse controls'"
          @click="toggleSidebar"
        >
          {{ sidebarCollapsed ? '›' : '‹' }}
        </button>
        <div v-show="!sidebarCollapsed" class="sidebar-scroll">
        <section class="workflow-section">
          <p class="section-title">1. Load data</p>
          <label class="field-label" for="file-input">Profile TSV file</label>
          <input id="file-input" type="file" @change="onFileChange" />
          <label class="field-label" for="tsv-input">Or paste profile text</label>
          <textarea
            id="tsv-input"
            :value="tsvInputValue"
            :placeholder="tsvPlaceholder"
            aria-label="TSV profile data input"
            @input="onTsvInput"
          ></textarea>
          <p v-if="profilePreview" class="tip compact-tip profile-preview">
            {{ profilePreview }}
          </p>

          <details class="foldout">
            <summary>Optional metadata and saved session</summary>
            <div class="foldout-body">
              <label class="field-label" for="metadata-file-input">Metadata TSV/CSV file</label>
              <input id="metadata-file-input" type="file" @change="onMetadataFileChange" />
              <label class="field-label" for="metadata-input">Or paste metadata text</label>
              <textarea
                id="metadata-input"
                :value="metadataInputValue"
                :placeholder="metadataPlaceholder"
                aria-label="Metadata TSV input"
                @input="onMetadataInput"
              ></textarea>
              <label class="field-label" for="session-file-input">Restore session JSON</label>
              <input id="session-file-input" type="file" @change="onSessionFileChange" />
            </div>
          </details>

          <details ref="compareWorkflow" class="foldout">
            <summary>Alternate workflow: compare two result TSV files</summary>
            <div class="foldout-body">
              <label class="field-label" for="compare-left-tsv">Left result TSV</label>
              <textarea
                id="compare-left-tsv"
                v-model="compareLeftTsv"
                placeholder="Paste left result TSV for comparison"
              ></textarea>
              <label class="field-label" for="compare-right-tsv">Right result TSV</label>
              <textarea
                id="compare-right-tsv"
                v-model="compareRightTsv"
                placeholder="Paste right result TSV for comparison"
              ></textarea>
              <button class="btn btn-secondary btn-full" @click="compareResults">
                Compare result sets
              </button>
            </div>
          </details>

          <button
            v-if="hasProfileInput || lastData"
            class="btn btn-secondary btn-chip reset-session"
            @click="resetSession"
          >
            Start over
          </button>
        </section>

        <section class="workflow-section">
          <p class="section-title">2. Build analysis</p>
          <div class="button-stack">
            <button class="btn btn-primary btn-full" :disabled="_building" @click="buildMst">
              {{ _building ? 'Building...' : 'Build MST' }}
            </button>
            <button class="btn btn-secondary btn-full" :disabled="_building" @click="buildDistanceMatrix">
              Build distance matrix
            </button>
            <button class="btn btn-secondary btn-full" :disabled="_building" @click="buildAlleleHeatmap">
              Build allele heatmap
            </button>
          </div>
          <label class="switch">
            <input type="checkbox" v-model="aggregateProfiles" />
            Aggregate identical profiles before building the graph
          </label>
          <label class="switch">
            <input type="checkbox" v-model="includeMissing" />
            Count missing-token differences in distance calculations
          </label>
          <p class="tip compact-tip">
            MST is the best first view. Matrix and heatmap are useful follow-up views when you need
            a denser sample-by-sample comparison.
          </p>
        </section>

        <section v-if="lastData" class="workflow-section">
          <p class="section-title">3. Result overview</p>
          <div class="metrics">
            <div v-for="metric in overviewMetrics" :key="metric.label" class="metric">
              <span>{{ metric.label }}</span><strong>{{ metric.value }}</strong>
            </div>
          </div>
          <div class="summary-note">
            <strong>Current view</strong>
            <span>{{ viewSubtitle }}</span>
          </div>
          <p class="tip compact-tip">
            View controls below affect only the rendered result, not the uploaded TSV itself.
          </p>
        </section>

        <section v-if="lastData && analysisView !== 'compare'" class="workflow-section">
          <p class="section-title">4. View controls</p>

          <details class="foldout view-group" open>
            <summary>Layout</summary>
            <div class="foldout-body">
              <template v-if="analysisView === 'graph'">
                <label class="field-label" for="layout-mode">Layout mode</label>
                <select id="layout-mode" v-model="layoutMode" @change="changeLayoutMode">
                  <option value="grapetree">GrapeTree layout (default)</option>
                  <option value="radial">Radial layout (planar rings)</option>
                  <option value="tree">Tree layout (cladogram)</option>
                </select>
              </template>

              <label class="field-label" for="cluster-filter">Cluster filter</label>
              <select id="cluster-filter" v-model="clusterFilter" @change="redrawFromLastData">
                <option value="">All clusters</option>
                <option v-for="option in clusterOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>

              <template v-if="analysisView === 'graph'">
                <div class="button-row action-row-tight">
                  <button class="btn btn-secondary btn-chip" @click="fitView">Fit view</button>
                  <button class="btn btn-secondary btn-chip" @click="clearManualRoot">Reset root</button>
                  <button class="btn btn-secondary btn-chip" @click="clearDraggedLayout">
                    Reset drag layout
                  </button>
                </div>
              </template>
            </div>
          </details>

          <details class="foldout view-group" open>
            <summary>Node</summary>
            <div class="foldout-body">
              <label class="field-label" for="color-by">Color nodes by</label>
              <select id="color-by" v-model="colorBy" @change="redrawFromLastData">
                <option value="">None</option>
                <option value="cluster_id">Cluster</option>
                <option v-for="field in metadataFields" :key="field" :value="field">
                  {{ field }}
                </option>
              </select>

              <label class="field-label" for="color-scheme">Color scheme</label>
              <select id="color-scheme" v-model="colorScheme" @change="redrawFromLastData">
                <option value="default">Default (60 colors)</option>
                <option value="pastel">Pastel</option>
                <option value="vivid">Vivid</option>
                <option value="warm">Warm tones</option>
                <option value="cool">Cool tones</option>
              </select>

              <div v-if="suggestedColorFields.length" class="preset-row">
                <span class="field-label">Suggested coloring</span>
                <div class="button-row">
                  <button
                    v-for="field in suggestedColorFields"
                    :key="field"
                    class="btn btn-secondary btn-chip"
                    @click="applySuggestedColor(field)"
                  >
                    {{ field }}
                  </button>
                </div>
              </div>

              <label class="field-label" for="shape-by">Shape nodes by</label>
              <select id="shape-by" v-model="shapeBy" @change="redrawFromLastData">
                <option value="">Circle (default)</option>
                <option v-for="field in shapeFieldOptions" :key="field" :value="field">
                  {{ field }}
                </option>
              </select>

              <template v-if="analysisView === 'graph'">
                <label class="field-label" for="node-scale">
                  Node size scale: {{ nodeScale.toFixed(1) }}×
                </label>
                <input
                  id="node-scale"
                  type="range"
                  min="0.5"
                  max="2"
                  step="0.1"
                  v-model.number="nodeScale"
                  @input="redrawFromLastData"
                />
              </template>

              <label class="field-label" for="label-by">Label nodes by</label>
              <select id="label-by" v-model="nodeLabelField" @change="redrawFromLastData">
                <option value="">Sample ID</option>
                <option value="cluster_id">Cluster ID</option>
                <option v-for="field in metadataFields" :key="'label-' + field" :value="field">
                  {{ field }}
                </option>
              </select>
              <label class="switch">
                <input
                  type="checkbox"
                  v-model="showNodeLabels"
                  @change="redrawFromLastData"
                />
                Show node labels
              </label>
              <label class="switch">
                <input type="checkbox" v-model="scaleNodeSize" @change="redrawFromLastData" />
                Scale node size by member count
              </label>

              <template v-if="analysisView === 'graph'">
                <label class="field-label" for="node-search">Search nodes</label>
                <div class="search-row">
                  <input
                    id="node-search"
                    type="text"
                    v-model="nodeSearchQuery"
                    placeholder="Sample ID..."
                    aria-label="Search nodes by label"
                    @input="onNodeSearch"
                    @keydown.esc="clearNodeSearch"
                  />
                  <button
                    v-if="nodeSearchQuery"
                    class="btn btn-secondary btn-chip btn-search-clear"
                    @click="clearNodeSearch"
                    aria-label="Clear search"
                  >
                    ✕
                  </button>
                </div>
                <div v-if="nodeSearchActive" class="search-info">
                  {{ nodeSearchMatchCount }} of {{ nodeSearchTotal }} nodes
                </div>

                <label class="field-label">
                  Collapse threshold
                  <span v-if="collapseThreshold > 0" class="threshold-badge">{{ collapseThreshold }}</span>
                  <span v-else class="threshold-badge threshold-none">Off</span>
                </label>
                <div class="threshold-slider-row">
                  <span class="threshold-bound">Off</span>
                  <input
                    id="collapse-threshold"
                    type="range"
                    min="0"
                    :max="edgeWeightMax || 1"
                    step="1"
                    aria-label="Collapse threshold"
                    v-model.number="collapseThreshold"
                    @input="debouncedRedraw"
                  />
                  <span class="threshold-bound">{{ edgeWeightMax || '-' }}</span>
                </div>
                <div class="button-row action-row-tight" style="margin-top: 6px;">
                  <button class="btn btn-secondary btn-chip" @click="expandAllNodes">Expand all</button>
                  <button class="btn btn-secondary btn-chip" @click="collapseAllLeaves">
                    Collapse all leaves
                  </button>
                  <button
                    v-if="Object.keys(_hiddenNodeIds).length > 0"
                    class="btn btn-secondary btn-chip"
                    @click="showAllHiddenNodes"
                  >
                    Show {{ Object.keys(_hiddenNodeIds).length }} hidden
                  </button>
                  <button
                    v-if="Object.keys(_customNodeColors).length > 0"
                    class="btn btn-secondary btn-chip"
                    @click="resetAllNodeColors"
                  >
                    Reset {{ Object.keys(_customNodeColors).length }} colors
                  </button>
                </div>
              </template>
            </div>
          </details>

          <details class="foldout view-group" open>
            <summary>Edge</summary>
            <div class="foldout-body">
              <label class="field-label" for="edge-length-mode">
                Branch length mode{{ edgeLengthModeAuto ? " (auto)" : "" }}
              </label>
              <select
                id="edge-length-mode"
                v-model="edgeLengthMode"
                @change="onEdgeLengthModeChange"
              >
                <option value="linear">Linear (MLST)</option>
                <option value="log">Logarithmic (cgMLST)</option>
                <option value="sqrt">Square root (cgMLST)</option>
              </select>

              <p
                v-if="edgeLengthModeAuto && edgeLengthMode === 'log'"
                class="tip compact-tip"
              >
                Auto: logarithmic branch scaling keeps cgMLST distances
                readable. Equal allele differences always get the same
                branch length.
              </p>

              <template v-if="analysisView === 'graph'">
                <label class="field-label" for="edge-length-scale">
                  Branch length scale: {{ edgeLengthScale }}
                </label>
                <input
                  id="edge-length-scale"
                  type="range"
                  min="10"
                  max="100"
                  step="5"
                  v-model.number="edgeLengthScale"
                  @input="debouncedRedraw"
                />

                <label class="field-label" for="long-branch-mode">Long branches</label>
                <select id="long-branch-mode" v-model="longBranchMode" @change="debouncedRedraw">
                  <option value="normal">Show all</option>
                  <option value="shorten">Shorten + dash</option>
                  <option value="hide">Hide</option>
                </select>
                <div v-if="longBranchMode !== 'normal'" class="threshold-slider-row">
                  <span class="threshold-bound">Min</span>
                  <input
                    id="long-branch-threshold"
                    type="range"
                    min="1"
                    :max="edgeWeightMax || 1"
                    step="1"
                    aria-label="Long-branch threshold"
                    v-model.number="longBranchThreshold"
                    @input="debouncedRedraw"
                  />
                  <span class="threshold-bound">{{ edgeWeightMax || '-' }}</span>
                </div>

                <label class="field-label">
                  Edge weight threshold
                  <span v-if="edgeWeightThreshold > 0" class="threshold-badge">{{ edgeWeightThreshold }}</span>
                  <span v-else class="threshold-badge threshold-none">No limit</span>
                </label>
                <div class="threshold-slider-row">
                  <span class="threshold-bound">{{ minEdgeWeightLabel }}</span>
                  <input
                    id="edge-weight-threshold"
                    type="range"
                    :min="0"
                    :max="edgeWeightMax"
                    step="1"
                    aria-label="Edge weight threshold"
                    v-model.number="edgeWeightThreshold"
                    @input="onThresholdChange"
                  />
                  <span class="threshold-bound">{{ edgeWeightMax }}</span>
                </div>
                <div v-if="totalEdgeCount" class="threshold-histogram" aria-hidden="true">
                  <span
                    v-for="bar in thresholdHistogramBars"
                    :key="bar.key"
                    class="threshold-histogram-bar"
                    :class="{ active: bar.active }"
                    :style="{ height: bar.height }"
                  ></span>
                </div>
                <div v-if="edgeWeightThreshold > 0 && currentRenderedGraph" class="threshold-stats">
                  {{ filteredEdgeCount }} of {{ totalEdgeCount }} edges visible
                </div>

                <label class="field-label" for="view-filter-mode">Focus view on</label>
                <select id="view-filter-mode" v-model="viewFilterMode" @change="redrawFromLastData">
                  <option value="all">All visible nodes</option>
                  <option value="component">Current inspected component</option>
                  <option value="path">Current inspected root path</option>
                </select>

                <label class="switch">
                  <input type="checkbox" v-model="showEdgeLabels" @change="toggleEdgeLabels" />
                  Show edge weights
                </label>
              </template>

              <p v-if="hiddenNonTreeEdges" class="tip compact-tip">
                {{ hiddenNonTreeEdges }} non-tree edge(s) hidden in tree view
                (shortcut chords would cross branches; use the radial layout to
                see them).
              </p>
            </div>
          </details>

          <details class="foldout view-group">
            <summary>Display</summary>
            <div class="foldout-body">
              <template v-if="analysisView === 'graph'">
                <label class="switch">
                  <input type="checkbox" v-model="overlapRelief" @change="redrawFromLastData" />
                  Nudge overlapping nodes apart (force tweak; may cross edges)
                </label>
                <label class="switch">
                  <input
                    type="checkbox"
                    v-model="correctnessOverlay"
                    @change="redrawFromLastData"
                  />
                  Highlight root path and component context
                </label>
                <label class="switch">
                  <input
                    type="checkbox"
                    v-model="aggregateNodes"
                    @change="redrawFromLastData"
                  />
                  Collapse identical profiles after rendering
                </label>
              </template>
            </div>
          </details>
        </section>

        <details v-if="multiSelectedNodeIds.length >= 2" v-show="analysisView === 'graph'" class="foldout" open>
          <summary>Compare selected ({{ multiSelectedNodeIds.length }})</summary>
          <div class="foldout-body compare-panel">
            <div class="compare-node-list">
              <span v-for="n in selectedNodesForCompare()" :key="n.id" class="compare-chip">
                {{ n.label }}
              </span>
            </div>
            <table v-if="comparePairsDistance().length" class="compare-table">
              <thead>
                <tr>
                  <th>Sample A</th>
                  <th>Sample B</th>
                  <th>Dist</th>
                  <th>Mismatch loci</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(pair, i) in comparePairsDistance()" :key="i">
                  <td>{{ pair.a }}</td>
                  <td>{{ pair.b }}</td>
                  <td class="compare-dist">{{ pair.weight }}</td>
                  <td class="compare-loci">{{ pair.loci || '—' }}</td>
                </tr>
              </tbody>
            </table>
            <p v-else class="tip compact-tip">
              Selected samples are not directly connected in the MST.
              Compare their distance via the distance matrix view.
            </p>
            <button class="btn btn-secondary btn-full" @click="clearMultiSelect">
              Clear selection
            </button>
          </div>
        </details>

        <details v-if="lastData" v-show="analysisView === 'graph'" class="foldout">
          <summary>Inspection details</summary>
          <div class="foldout-body">
            <div v-if="inspectedItem" class="inspect-panel">
              <div class="inspect-title">{{ inspectedItem.title }}</div>
              <div class="inspect-kind">{{ inspectedItem.kind }}</div>
              <div v-for="line in inspectedItem.lines" :key="line" class="inspect-line">
                {{ line }}
              </div>
              <button
                v-if="inspectedItem.kind === 'node'"
                class="btn btn-secondary btn-chip inspect-root-btn"
                @click="setManualRoot(inspectedItem.nodeId)"
              >
                Set as tree root
              </button>
            </div>
            <p v-else class="tip compact-tip">
              Hover a node or edge in the graph to inspect metadata, distance, and mismatch details.
            </p>
          </div>
        </details>

        <details v-if="clusterSummary.length" v-show="analysisView !== 'compare'" class="foldout">
          <summary>Cluster summary</summary>
          <div class="foldout-body cluster-panel">
            <div
              v-for="cluster in clusterSummary"
              :key="cluster.cluster_id"
              class="cluster-card"
              :class="{ selected: String(cluster.cluster_id) === String(clusterFilter) }"
              tabindex="0"
              role="button"
              :aria-pressed="String(String(cluster.cluster_id) === String(clusterFilter))"
              :aria-label="'Cluster ' + cluster.cluster_id + ', ' + cluster.sample_count + ' samples'"
              @click="selectClusterFilter(cluster.cluster_id)"
              @keydown.enter="selectClusterFilter(cluster.cluster_id)"
              @keydown.space.prevent="selectClusterFilter(cluster.cluster_id)"
            >
              <div class="cluster-title">Cluster {{ cluster.cluster_id }}</div>
              <div class="cluster-line">Nodes: {{ cluster.node_count }}</div>
              <div class="cluster-line">Samples: {{ cluster.sample_count }}</div>
              <div class="cluster-line">Members: {{ cluster.members.join(', ') }}</div>
            </div>
          </div>
        </details>

        <details v-if="tableRows.length" v-show="analysisView !== 'compare'" class="foldout">
          <summary>Sample comparison</summary>
          <div class="foldout-body">
            <label class="field-label" for="compare-left">Left sample</label>
            <select id="compare-left" v-model="compareLeftLabel">
              <option value="">Select sample</option>
              <option v-for="row in tableRows" :key="`left-${row.id}`" :value="row.sample_id">
                {{ row.sample_id }}
              </option>
            </select>
            <label class="field-label" for="compare-right">Right sample</label>
            <select id="compare-right" v-model="compareRightLabel">
              <option value="">Select sample</option>
              <option v-for="row in tableRows" :key="`right-${row.id}`" :value="row.sample_id">
                {{ row.sample_id }}
              </option>
            </select>
            <div class="button-row">
              <button class="btn btn-secondary btn-chip" @click="compareLoci">Compare loci</button>
              <button class="btn btn-secondary btn-chip" @click="exportCompareJson">
                Export compare JSON
              </button>
            </div>
            <div v-if="locusDiff" class="inspect-panel">
              <div class="inspect-title">{{ locusDiff.left_label }} ↔ {{ locusDiff.right_label }}</div>
              <div class="inspect-line">Distance: {{ locusDiff.distance }}</div>
              <div v-if="locusDiff.differences.length === 0" class="inspect-line">
                No differing loci.
              </div>
              <div
                v-for="diff in locusDiff.differences"
                :key="`${diff.locus}-${diff.left}-${diff.right}`"
                class="inspect-line"
              >
                {{ diff.locus }}: {{ diff.left }} → {{ diff.right }} ({{ diff.type }})
              </div>
            </div>
          </div>
        </details>

        <details v-if="tableRows.length" v-show="analysisView !== 'compare'" class="foldout">
          <summary>Sample table</summary>
          <div ref="tablePanel" class="table-panel">
            <div v-if="tableTruncated" class="status-message warn">
              Showing first {{ tableRenderLimit }} of
              {{ filteredTableRows.length }} rows. Search/filter to narrow,
              or export for the full table.
            </div>
            <div class="table-toolbar">
              <input
                v-model="tableQuery"
                class="table-search"
                type="text"
                placeholder="Search sample, ST, metadata"
              />
              <label class="switch compact-switch">
                <input type="checkbox" v-model="tableSelectionOnly" />
                Selected only
              </label>
              <button class="btn btn-secondary btn-chip" @click="exportTableTsv">
                Export TSV
              </button>
            </div>
            <table class="isolate-table">
              <thead>
                <tr>
                  <th
                    v-for="column in tableColumns"
                    :key="column.key"
                    class="sortable"
                    :class="{ sorted: tableSortKey === column.key }"
                    :aria-sort="
                      tableSortKey === column.key
                        ? (tableSortDirection === 'asc' ? 'ascending' : 'descending')
                        : 'none'
                    "
                    @click="toggleTableSort(column.key)"
                  >
                    {{ column.label }}
                    <span
                      v-if="tableSortKey === column.key"
                      class="sort-arrow"
                      aria-hidden="true"
                    >{{ tableSortDirection === 'asc' ? '▲' : '▼' }}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in visibleTableRows"
                  :key="row.id"
                  :class="{ selected: selectedTableNodeId === row.id }"
                  @click="selectTableRow(row)"
                >
                  <td v-for="column in tableColumns" :key="column.key">
                    {{ tableCellValue(row, column.key) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </details>

        <details v-if="lastData" class="foldout">
          <summary>Export and save</summary>
          <div class="foldout-body button-stack">
            <button v-show="analysisView === 'graph'" class="btn btn-secondary btn-full" @click="exportSvg">
              Export SVG
            </button>
            <button v-show="analysisView === 'graph'" class="btn btn-secondary btn-full" @click="exportPng()">
              Export PNG
            </button>
            <button v-show="analysisView === 'graph'" class="btn btn-secondary btn-full" @click="exportNewick">
              Export Newick
            </button>
            <button v-show="analysisView !== 'compare'" class="btn btn-secondary btn-full" @click="exportGraphJson">
              Export graph JSON
            </button>
            <button class="btn btn-secondary btn-full" @click="exportSessionJson">
              Export session JSON
            </button>
          </div>
        </details>
        </div>
      </aside>

      <section class="viz card">
        <div class="viz-top">
        <div class="viz-header">
          <div class="viz-title-block">
            <h2 class="viz-title">{{ vizTitle }}</h2>
            <p class="viz-stats">{{ viewSubtitle }}</p>
          </div>
          <LegendBar
            :items="legendItems"
            :color-by="colorBy"
            :hidden-values="hiddenLegendValues"
            :hovered-value="hoveredLegendValue"
            @toggle="toggleLegendValue"
            @show-all="showAllLegendValues"
            @select-by-value="selectNodesByLegendValue"
            @update:hovered-value="hoveredLegendValue = $event"
          />
        </div>
        <div v-if="buildError" class="viz-alert" role="alert">
          <strong>Build failed</strong>
          <span class="viz-alert-message">{{ buildError }}</span>
          <button class="btn btn-secondary btn-chip" @click="buildError = ''">
            Dismiss
          </button>
        </div>
        </div>
        <div v-if="analysisView === 'graph' && timelineFieldOptions().length" class="timeline-bar">
          <select v-model="timelineField" class="timeline-select" aria-label="Timeline field">
            <option value="">No timeline</option>
            <option v-for="f in timelineFieldOptions()" :key="f" :value="f">{{ f }}</option>
          </select>
          <template v-if="timelineField">
            <button class="timeline-btn" @click="toggleTimelinePlay" :aria-label="timelinePlaying ? 'Pause' : 'Play'">
              {{ timelinePlaying ? '⏸' : '▶' }}
            </button>
            <input
              type="range"
              class="timeline-slider"
              min="0"
              :max="timelineMaxValue()"
              v-model.number="timelineValue"
              @input="redrawFromLastData()"
              :aria-label="`Timeline: ${timelineField}`"
            />
            <span class="timeline-value">{{ timelineValue || 'all' }}</span>
            <button class="timeline-btn" @click="resetTimeline" aria-label="Reset timeline">↺</button>
          </template>
        </div>
        <div v-if="analysisView === 'graph'" ref="canvas" class="canvas" role="region" aria-label="Graph viewport — drag to pan, scroll to zoom, click to inspect, shift-click to recolor, right-click to hide">
          <div v-if="_building" class="loading-overlay">
            <div class="loading-spinner"></div>
            <span class="loading-text">Processing...</span>
          </div>
          <template v-if="hasGraphData">
            <svg ref="svg" id="graph" viewBox="0 0 1400 900" role="img" aria-label="Minimum spanning tree graph"></svg>
            <div
              class="tooltip"
              :class="{ show: tooltip.visible }"
              :style="tooltipStyle"
            >
              <div class="head">{{ tooltip.title }}</div>
              <div v-for="line in tooltip.lines" :key="line" class="line">{{ line }}</div>
            </div>
          </template>
          <EmptyState
            v-else
            :has-profile-input="hasProfileInput"
            @build-mst="buildMst"
            @build-distance-matrix="buildDistanceMatrix"
            @build-allele-heatmap="buildAlleleHeatmap"
            @compare-results="openCompareWorkflow"
          />
        </div>
        <template v-else-if="analysisView === 'matrix'">
          <BuildPrompt
            v-if="!hasMatrixData"
            title="Build the distance matrix"
            description="A pairwise sample-by-sample distance table will appear here. It uses the same profile TSV you loaded for the MST."
            action-label="Build distance matrix"
            :has-input="hasProfileInput"
            input-hint="Load or paste a profile TSV in the sidebar first."
            @action="buildDistanceMatrix"
          />
          <DistanceMatrix
            v-else
            :labels="filteredDistanceMatrixView.labels"
            :matrix="filteredDistanceMatrixView.matrix"
            :max-value="matrixMaxValue"
            :truncated="matrixTruncated"
            :render-limit="matrixRenderLimit"
            :truncated-count="matrixTruncatedCount"
            @compare-pair="triggerCompareFromPair"
          />
        </template>
        <template v-else-if="analysisView === 'heatmap'">
          <BuildPrompt
            v-if="!hasHeatmapData"
            title="Build the allele heatmap"
            description="A sample × locus grid will appear here, one cell per called allele, so you can scan locus-level variation across samples."
            action-label="Build allele heatmap"
            :has-input="hasProfileInput"
            input-hint="Load or paste a profile TSV in the sidebar first."
            @action="buildAlleleHeatmap"
          />
          <AlleleHeatmap
            v-else
            :locus-query="heatmapLocusQuery"
            :loci="filteredHeatmapLociView.loci"
            :cells="filteredHeatmapLociView.cells"
            :labels="filteredHeatmapView.labels"
            :annotation-rows="heatmapAnnotationRows"
            :color-by="colorBy"
            :truncated="heatmapTruncated"
            :render-limit="matrixRenderLimit"
            :truncated-count="matrixTruncatedCount"
            :loci-truncated="heatmapLociTruncated"
            :loci-render-limit="lociRenderLimit"
            :loci-truncated-count="heatmapLociTruncatedCount"
            @update:locus-query="heatmapLocusQuery = $event"
            @export-tsv="exportHeatmapTsv"
            @export-json="exportHeatmapJson"
            @fill-compare="fillCompareFromPair($event, compareRightLabel || $event)"
            @trigger-compare="triggerCompareFromPair(compareLeftLabel || $event, $event)"
          />
        </template>
        <SummaryView v-else-if="analysisView === 'summary'" :summary="summaryData" />
        <StatsView v-else-if="analysisView === 'stats'" :stats="statsData" />
        <template v-else>
          <BuildPrompt
            v-if="!hasCompareData"
            title="Compare two result sets"
            description="Side-by-side sample matching with ST and locus differences. Open “Alternate workflow: compare two result TSV files” in the sidebar, paste both result tables, then run the comparison."
            action-label="Compare result sets"
            :has-input="canCompare"
            input-hint="Paste both the left and right result TSVs in the sidebar first."
            @action="compareResults"
          />
          <CompareTable
            v-else
            :summary="compareResultsSummary"
            :rows="filteredCompareRows"
            :status-options="compareStatusOptions"
            :status-filter="compareStatusFilter"
            @update:status-filter="compareStatusFilter = $event"
          />
        </template>
      </section>
    </main>
            </div>
            <input
              ref="nodeColorPicker"
              type="color"
              class="hidden-color-picker"
              :value="nodeColorPickerValue"
              @input="applyCustomNodeColor($event.target.value)"
            />
          </template>
