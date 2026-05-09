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

const PALETTE = [
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

const LAYOUT_CENTER_X = 700;
const LAYOUT_CENTER_Y = 450;
const LAYOUT_MAX_RADIUS = 380;

export default {
  name: "VisualApp",
  data() {
    return {
      title: window.GMLST_VISUAL_TITLE || "gmlst visual web",
      _building: false,
      sidebarCollapsed: false,
      tsvText: "",
      metadataText: "",
      includeMissing: false,
      aggregateProfiles: true,
      showEdgeLabels: true,
      scaleNodeSize: true,
      overlapRelief: true,
      analysisView: "graph",
      viewTabs: [
        { id: "graph", label: "Graph" },
        { id: "matrix", label: "Matrix" },
        { id: "heatmap", label: "Heatmap" },
        { id: "compare", label: "Compare" },
      ],
      layoutMode: "tree",
      edgeLengthMode: "linear",
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
      suggestedColorFields: [],
      maxWeight: "",
      edgeWeightMax: 0,
      edgeWeightThreshold: 0,
      aggregateNodes: false,
      correctnessOverlay: true,
      viewFilterMode: "all",
      statusMessage: "Waiting for input",
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
      const colorMap = this.colorMapFor(this.tableRows, this.colorBy);
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
      if (!this.lastData?.edges?.length) return "0";
      let min = Infinity;
      for (const edge of this.lastData.edges) {
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
      return nodes.filter((node) =>
        String(node.label || "").toLowerCase().includes(query),
      ).length;
    },
    nodeSearchTotal() {
      return Array.isArray(this.currentRenderedGraph?.nodes)
        ? this.currentRenderedGraph.nodes.length
        : 0;
    },
    collapsedNodeSet() {
      const graph = this.currentCollapseSourceGraph || this.currentRenderedGraph;
      return this.resolveCollapsedNodeSet(
        graph?.nodes || [],
        graph?.edges || [],
        this.currentLayout?.parent,
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
  },
  mounted() {
    this._boundCanvas = null;
    this._pendingNodeClick = null;
    this._debounceTimer = null;
    this._dragRaf = null;
    this.syncCanvasInteraction();
    window.addEventListener("mousemove", this.onMouseMove);
    window.addEventListener("mouseup", this.onMouseUp);
    window.addEventListener("touchmove", this.onTouchMove, { passive: false });
    window.addEventListener("touchend", this.onTouchEnd);
    this._boundKeydown = (event) => this.handleGlobalKeydown(event);
    window.addEventListener("keydown", this._boundKeydown);
    this._beforeUnload = (event) => {
      if (this.lastData && Object.keys(this.nodePositionOverrides).length > 0) {
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
    if (this._pendingNodeClick) {
      window.clearTimeout(this._pendingNodeClick);
      this._pendingNodeClick = null;
    }
    if (this._beforeUnload) {
      window.removeEventListener("beforeunload", this._beforeUnload);
    }
  },
  methods: {
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
      if (!mod && event.key === "Escape") {
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
        if (Array.isArray(this.lastData?.nodes) && Array.isArray(this.lastData?.edges)) {
          this.redrawFromLastData();
        }
      });
    },
    switchAnalysisView(viewId) {
      this.analysisView = viewId;
    },
    async onFileChange(event) {
      const file = event.target.files?.[0];
      if (!file) {
        return;
      }
      this.tsvText = await file.text();
      this.setStatus("ok", "Profile loaded");
    },
    async onMetadataFileChange(event) {
      const file = event.target.files?.[0];
      if (!file) {
        return;
      }
      this.metadataText = await file.text();
      this.setStatus("ok", "Metadata loaded");
    },
    async onSessionFileChange(event) {
      const file = event.target.files?.[0];
      if (!file) {
        return;
      }
      try {
        const payload = JSON.parse(await file.text());
        this.applySessionPayload(payload);
        this.setStatus("ok", "Session restored");
      } catch (error) {
        this.setStatus("error", `Failed to load session: ${error.message}`);
      }
    },
    setStatus(kind, message) {
      this.statusKind = kind;
      this.statusMessage = message;
    },
    clearSvg() {
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
    parseMaxWeight() {
      const raw = this.maxWeight.trim();
      if (!raw) {
        return null;
      }
      const parsed = Number(raw);
      if (!Number.isFinite(parsed) || parsed < 0) {
        return null;
      }
      return Math.floor(parsed);
    },
    resolveCollapsedNodeSet(nodes, edges, parentMap) {
      const manual = new Set(
        Object.keys(this.collapsedNodes).filter((id) => this.collapsedNodes[id]),
      );
      if (this.collapseThreshold <= 0 || !nodes.length || !edges.length || !parentMap) {
        return manual;
      }
      const edgeByKey = new Map();
      for (const edge of edges) {
        edgeByKey.set(this.edgeKey(edge.source, edge.target), edge);
      }
      for (const node of nodes) {
        if (manual.has(String(node.id))) {
          continue;
        }
        const parentId = parentMap.get(node.id);
        if (parentId === undefined || parentId === -1) {
          continue;
        }
        const edge = edgeByKey.get(this.edgeKey(node.id, parentId));
        if (edge && Number(edge.weight) > this.collapseThreshold) {
          manual.add(String(parentId));
        }
      }
      return manual;
    },
    filteredEdges(edges) {
      const maxWeight = this.parseMaxWeight();
      if (maxWeight === null) {
        return edges;
      }
      return edges.filter((edge) => Number(edge.weight) <= maxWeight);
    },
    aggregateGraph(nodes, edges) {
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
    },
    colorMapFor(nodes, colorField) {
      if (!colorField) {
        return new Map();
      }
      const schemes = {
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
      const activePalette = schemes[this.colorScheme] || PALETTE;
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
      const nodes = this.lastData?.nodes || [];
      let count = 0;
      for (const node of nodes) {
        if (this._colorValueForNode(node, this.colorBy) === value) {
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
      const isHidden = this.hiddenLegendValues[item.value];
      return {
        background: isHidden ? "#e2e8f0" : `${item.color}18`,
        borderColor: isHidden ? "#cbd5e1" : `${item.color}66`,
        color: isHidden ? "#94a3b8" : "#1f2937",
        cursor: "pointer",
      };
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
      const bbox = this.graphGroup.getBBox();
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
      const lines = [
        `distance: ${edge.weight}`,
        `source: ${edge.source_label}`,
        `target: ${edge.target_label}`,
        `mismatch loci: ${mismatchLoci.length}`,
      ];
      if (mismatchLoci.length) {
        lines.push(`loci: ${mismatchLoci.join(", ")}`);
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
    nodeRadius(node) {
      const count = Number(node.member_count || 1);
      if (!this.scaleNodeSize) {
        return count > 1 ? 11 : 8;
      }
      return Math.min(22, 7 + Math.sqrt(Math.max(1, count)) * 3);
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
      this.tsvText = payload.inputs?.tsv || "";
      this.metadataText = payload.inputs?.metadata_tsv || "";
      this.includeMissing = Boolean(payload.options?.include_missing);
      this.aggregateProfiles = payload.options?.aggregate_profiles !== false;
      this.layoutMode = payload.options?.layout_mode || "tree";
      this.edgeLengthMode = payload.options?.edge_length_mode || "linear";
      this.edgeLengthScale = Number(payload.options?.edge_length_scale ?? 50) || 50;
      this.longBranchMode = payload.options?.long_branch_mode || "normal";
      this.longBranchThreshold = Number(payload.options?.long_branch_threshold ?? 0) || 0;
      this.colorBy = payload.options?.color_by || "";
      this.maxWeight = payload.options?.max_weight ?? "";
      this.showEdgeLabels = payload.options?.show_edge_labels !== false;
      this.scaleNodeSize = payload.options?.scale_node_size !== false;
      this.aggregateNodes = Boolean(payload.options?.aggregate_nodes);
      this.correctnessOverlay = payload.options?.correctness_overlay !== false;
      this.viewFilterMode = payload.options?.view_filter_mode || "all";
      this.manualRootId = payload.options?.manual_root_id ?? null;
      this.overlapRelief = payload.options?.overlap_relief !== false;
      this.nodePositionOverrides = payload.options?.node_position_overrides || {};
      this.nodeSearchQuery = payload.options?.node_search_query || "";
      this.nodeSearchActive = Boolean(this.nodeSearchQuery.trim());
      this.collapsedNodes = payload.options?.collapsed_nodes || {};
      this.collapseThreshold = payload.options?.collapse_threshold || 0;
      this.hiddenLegendValues = payload.options?.hidden_legend_values || {};
      this._hiddenNodeIds = payload.options?.hidden_node_ids || {};
      this._customNodeColors = payload.options?.custom_node_colors || {};
      this.hoveredLegendValue = null;
      this.lastData = payload.response || null;
      this.currentLayout = null;
      this.currentRenderedGraph = null;
      this.currentEdgeWeightGraph = null;
      this.currentCollapseSourceGraph = null;
      this.metadataFields = this.lastData?.metadata_fields || [];
      this.tableRows = this.lastData?.table_rows || [];
      this.clusterSummary = this.lastData?.cluster_summary || [];
      this.clusterFilter = payload.options?.cluster_filter ?? "";
      this.analysisView = payload.options?.analysis_view || "graph";
      this.distanceMatrix = this.lastData?.matrix || [];
      this.matrixLabels = this.lastData?.labels || [];
      this.heatmapLoci = this.lastData?.loci || [];
      this.heatmapCells = this.lastData?.cells || [];
      this.compareLeftLabel = payload.options?.compare_left_label || "";
      this.compareRightLabel = payload.options?.compare_right_label || "";
      this.locusDiff = payload.response?.locus_diff || null;
      this.suggestedColorFields = this.lastData?.suggested_color_fields || [];
      this.edgeWeightThreshold = payload.options?.max_weight ? Number(payload.options.max_weight) : 0;
      this.fitView();
      if (this.lastData) {
        this.$nextTick(() => {
          this.redrawFromLastData();
        });
      }
    },
    _colorValueForNode(node, field) {
      if (!field) return "";
      return String(field === "cluster_id" ? node.cluster_id ?? "" : node.meta?.[field] ?? "");
    },
    _edgeLength(weight) {
      const w = Math.max(1, Number(weight) || 1);
      const scale = Number(this.edgeLengthScale) || 50;
      if (this.edgeLengthMode === "log") {
        return scale * Math.log2(w + 1);
      }
      if (this.edgeLengthMode === "sqrt") {
        return scale * Math.sqrt(w);
      }
      return scale * w;
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

      let barWeight = candidates[0];
      let bestInRange = null;
      let bestFallback = null;

      for (const value of candidates) {
        const renderedLength = this._edgeLength(value) * viewScale;
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

      const barLen = this._edgeLength(barWeight) * viewScale;
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
      bg.setAttribute("fill", "rgba(255,255,255,0.85)");
      bg.setAttribute("stroke", "rgba(203,213,225,0.6)");
      bg.setAttribute("stroke-width", "0.8");
      g.appendChild(bg);

      const line = document.createElementNS(ns, "line");
      line.setAttribute("x1", "0");
      line.setAttribute("y1", "0");
      line.setAttribute("x2", String(barLen));
      line.setAttribute("y2", "0");
      line.setAttribute("stroke", "#475569");
      line.setAttribute("stroke-width", "2");
      g.appendChild(line);

      const leftTick = document.createElementNS(ns, "line");
      leftTick.setAttribute("x1", "0");
      leftTick.setAttribute("y1", "-5");
      leftTick.setAttribute("x2", "0");
      leftTick.setAttribute("y2", "5");
      leftTick.setAttribute("stroke", "#475569");
      leftTick.setAttribute("stroke-width", "2");
      g.appendChild(leftTick);

      const rightTick = document.createElementNS(ns, "line");
      rightTick.setAttribute("x1", String(barLen));
      rightTick.setAttribute("y1", "-5");
      rightTick.setAttribute("x2", String(barLen));
      rightTick.setAttribute("y2", "5");
      rightTick.setAttribute("stroke", "#475569");
      rightTick.setAttribute("stroke-width", "2");
      g.appendChild(rightTick);

      const text = document.createElementNS(ns, "text");
      text.setAttribute("x", String(barLen / 2));
      text.setAttribute("y", "-7");
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("font-size", "11");
      text.setAttribute("fill", "#475569");
      text.setAttribute("font-family", '"IBM Plex Sans", sans-serif');
      text.setAttribute("font-weight", "500");
      text.textContent = `${barWeight} allele${barWeight > 1 ? "s" : ""}`;
      g.appendChild(text);

      svg.appendChild(g);
    },
    _getDescendants(nodeId, parentMap) {
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
            radius: this.nodeRadius(node),
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
            .distance((edge) => this._edgeLength(edge.weight) * 0.6)
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
    _greedyRadialLayout(nodes, edges, rootId, depthMap) {
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
    },
    _correctBranchLengths(nodes, edges, positions, depthMap) {
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
            depth.set(next.id, (depth.get(current) || 0) + this._edgeLength(next.weight));
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

      const buildHierarchyNode = (nodeId) => ({
        id: nodeId,
        label: nodeById.get(nodeId)?.label || String(nodeId),
        nodeRef: nodeById.get(nodeId),
        children: (children.get(nodeId) || []).map((childId) => buildHierarchyNode(childId)),
      });

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
        const maxTreeY = Math.max(...descendants.map((node) => node.y), 1) * 180;
        descendants.forEach((node) => {
          const weightedDepth = depth.get(node.data.id) || 0;
          node.y = maxWeightedDepth > 0 ? (weightedDepth / maxWeightedDepth) * maxTreeY : node.y * 180;
        });
        const minX = Math.min(...descendants.map((node) => node.x), 0);
        descendants.forEach((node) => {
          positions.set(node.data.id, [node.y, node.x - minX + 90]);
        });
        Object.entries(this.nodePositionOverrides).forEach(([nodeId, point]) => {
          if (positions.has(Number(nodeId))) {
            positions.set(Number(nodeId), point);
          }
        });
        return {
          positions: this.applyOverlapRelief(nodes, edges, positions),
          rootId: effectiveRoot,
          parent,
          depth,
          componentByNode,
          componentCount: componentRoots.length,
        };
      }

      let radialPositions = this._greedyRadialLayout(nodes, edges, effectiveRoot, depth);
      radialPositions = this._correctBranchLengths(nodes, edges, radialPositions, depth);
      const componentByNodeRadial = componentByNode;
      const componentCountRadial = componentRoots.length;
      Object.entries(this.nodePositionOverrides).forEach(([nodeId, point]) => {
        if (radialPositions.has(Number(nodeId))) {
          radialPositions.set(Number(nodeId), point);
        }
      });
      return {
        positions: this.applyOverlapRelief(nodes, edges, radialPositions),
        rootId: effectiveRoot,
        parent,
        depth,
        componentByNode: componentByNodeRadial,
        componentCount: componentCountRadial,
      };
    },
    edgeKey(source, target) {
      const left = Math.min(source, target);
      const right = Math.max(source, target);
      return `${left}:${right}`;
    },
    highlightedPathEdges(nodeId, parentMap) {
      const edgeKeys = new Set();
      let current = nodeId;
      while (parentMap.has(current) && parentMap.get(current) !== -1) {
        const parent = parentMap.get(current);
        edgeKeys.add(this.edgeKey(current, parent));
        current = parent;
      }
      return edgeKeys;
    },
    highlightedPathNodes(nodeId, parentMap) {
      const nodeIds = new Set([nodeId]);
      let current = nodeId;
      while (parentMap.has(current) && parentMap.get(current) !== -1) {
        const parent = parentMap.get(current);
        nodeIds.add(parent);
        current = parent;
      }
      return nodeIds;
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
        const visibleNodeIds = this.highlightedPathNodes(this.inspectedItem.nodeId, layoutData.parent);
        const visibleEdgeKeys = this.highlightedPathEdges(this.inspectedItem.nodeId, layoutData.parent);
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
        ? this.aggregateGraph(rawNodes, rawEdges)
        : { nodes: rawNodes, edges: rawEdges };
      const visibleEdges = this.filteredEdges(activeGraph.edges);
      const fullLayoutData = this.computePositions(
        activeGraph.nodes,
        visibleEdges,
        this.layoutMode,
        this.lastData?.layout?.root_id,
      );
      const collapseSet = this.resolveCollapsedNodeSet(
        activeGraph.nodes,
        visibleEdges,
        fullLayoutData.parent,
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
          this.lastData?.layout?.root_id,
        )
        : fullLayoutData;
      const colorMap = this.colorMapFor(activeGraph.nodes, this.colorBy);
      const selectedNode = selectedNodeId(this.inspectedItem);
      const highlightedEdgeKeys =
        this.correctnessOverlay && this.inspectedItem?.kind === "node"
          ? this.highlightedPathEdges(this.inspectedItem.nodeId, layoutData.parent)
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
          const legendValue = this._colorValueForNode(node, this.colorBy);
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
            radius: this.nodeRadius(node),
            isRoot,
            sameComponent,
            isSelected: selectedNode === node.id,
            searchMatch,
            searchDimmed: hasSearch ? !searchMatch : false,
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
          const edgeKey = this.edgeKey(edge.source, edge.target);
          const inHighlightedPath = highlightedEdgeKeys.has(edgeKey);
          const sameComponent =
            layoutData.componentByNode.get(edge.source) === layoutData.componentByNode.get(edge.target);
          return {
            ...edge,
            sourcePoint,
            targetPoint,
            midX: (sourcePoint[0] + targetPoint[0]) / 2,
            midY: (sourcePoint[1] + targetPoint[1]) / 2,
            edgeKey,
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
        edges: this.filteredEdges(edgeWeightGraph.edges),
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
      const edgeStroke = (edge) => {
        if (edge.inHighlightedPath) {
          return "#dc2626";
        }
        if (!edge.sameComponent) {
          return "#d5dee9";
        }
        const shade = edgeShade(Number(edge.weight) || 0);
        return d3.interpolateRgb("#d6e1ee", "#334155")(shade);
      };
      const edgeStrokeWidth = (edge) => {
        if (edge.inHighlightedPath) {
          return 3.2;
        }
        const normalized = ((Number(edge.weight) || 0) - minEdgeWeight) / edgeWeightSpan;
        return 3.1 - normalized * 1.8;
      };
      const edgeStrokeDasharray = (edge) => {
        if (longBranchMode === "shorten" && isLongBranch(edge)) {
          return "3 6";
        }
        const normalized = ((Number(edge.weight) || 0) - minEdgeWeight) / edgeWeightSpan;
        return normalized >= 0.72 ? "5 4" : null;
      };
      const edgeGroup = graph.append("g").attr("class", "edges");
      const edgeSelection = this.layoutMode === "tree"
        ? edgeGroup
          .selectAll("path")
          .data(finalGraph.edges)
          .enter()
          .append("path")
          .attr("d", (edge) => {
            const x1 = edge.sourcePoint[0];
            const y1 = edge.sourcePoint[1];
            const x2 = edge.targetPoint[0];
            const y2 = edge.targetPoint[1];
            const midX = (x1 + x2) / 2;
            return `M${x1},${y1} C${midX},${y1} ${midX},${y2} ${x2},${y2}`;
          })
          .attr("fill", "none")
        : edgeGroup
          .selectAll("line")
          .data(finalGraph.edges)
          .enter()
          .append("line")
          .attr("x1", (edge) => edge.sourcePoint[0])
          .attr("y1", (edge) => edge.sourcePoint[1])
          .attr("x2", (edge) => edge.targetPoint[0])
          .attr("y2", (edge) => edge.targetPoint[1]);
      edgeSelection
        .attr("stroke", edgeStroke)
        .attr("stroke-width", edgeStrokeWidth)
        .attr("stroke-dasharray", edgeStrokeDasharray)
        .attr("stroke-linecap", "round")
        .attr("stroke-opacity", edgeOpacity)
        .on("mousemove", (_event, edge) => {
          setTooltipAccent("#334155");
          this.showEdgeTooltip(edge, _event);
        })
        .on("mouseleave", this.hideTooltip);
    },
    _renderEdgeLabels(graph, finalGraph, context) {
      const { setTooltipAccent } = context;
      const edgeLabelGroup = graph
        .append("g")
        .attr("class", "edge-labels")
        .selectAll("g")
        .data(finalGraph.edges)
        .enter()
        .append("g")
        .attr("class", "edge-label")
        .attr("transform", (edge) => `translate(${edge.midX}, ${edge.midY - 7})`)
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
        .attr("stroke", "#ffffff")
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
        .attr("fill", "#475569")
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
          return "rgba(15, 23, 42, 0.35)";
        })
        .attr("stroke", (node) =>
          node.isSelected ? "#fbbf24" : "rgba(15, 23, 42, 0.5)",
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
          .attr("data-legend-value", (node) => this._colorValueForNode(node, this.colorBy))
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
        .append("circle")
        .attr("r", (node) => node.radius + (node.isSelected ? 2 : 0))
        .attr("fill", (node) => node.color)
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
      const { labelOpacity } = context;
      const labelGroup = graph
        .append("g")
        .attr("class", "labels")
        .selectAll("g")
        .data(finalGraph.nodes)
        .enter()
        .append("g")
        .attr("transform", (node) => `translate(${node.x + node.radius + 5}, ${node.y})`)
        .attr("opacity", labelOpacity);
      labelGroup
        .append("rect")
        .attr("x", -3)
        .attr("y", (node) => (node.isRoot ? -11 : -10))
        .attr("width", (node) => node.label.length * 7 + 10)
        .attr("height", (node) => (node.isRoot ? 18 : 16))
        .attr("rx", 8)
        .attr("fill", "rgba(255, 255, 255, 0.86)")
        .attr("stroke", "rgba(203, 213, 225, 0.9)")
        .attr("stroke-width", 0.7);
      labelGroup
        .append("text")
        .attr("x", 2)
        .attr("y", 4)
        .attr("font-size", (node) => (node.isRoot ? 12.8 : 12))
        .attr("fill", (node) => (node.isRoot ? "#0f172a" : "#1f2937"))
        .attr("font-weight", (node) => (node.isRoot ? 700 : 500))
        .text((node) => node.label);
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
          if (this._pendingNodeClick) {
            window.clearTimeout(this._pendingNodeClick);
          }
          this._pendingNodeClick = window.setTimeout(() => {
            this._pendingNodeClick = null;
            this.setManualRoot(node.id);
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
              const descendants = this._getDescendants(node.id, layout.parent);
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
        this.lastData?.sample_count || rawNodes.length,
      );
      this._drawScaleBar(svg);
      this._applyLegendHover();
      if (this.view.scale === 1 && this.view.tx === 0 && this.view.ty === 0) {
        this.$nextTick(() => {
          this.fitView();
        });
      }
    },
    redrawFromLastData() {
      if (
        !this.lastData ||
        !Array.isArray(this.lastData.nodes) ||
        !Array.isArray(this.lastData.edges)
      ) {
        this.clearSvg();
        return;
      }
      this.drawGraph(this.lastData.nodes, this.lastData.edges);
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
        const response = await fetch("/api/mst", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            tsv: this.tsvText,
            metadata_tsv: this.metadataText,
            include_missing: this.includeMissing,
            aggregate_profiles: this.aggregateProfiles,
          }),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "request failed");
        }

        this._resetViewState(data, "graph");
        this.manualRootId = null;
        this.nodePositionOverrides = {};
        this.clusterSummary = data.cluster_summary || [];
        this.distanceMatrix = [];
        this.matrixLabels = [];
        this.heatmapLoci = [];
        this.heatmapCells = [];
        this.heatmapLocusQuery = "";
        this.edgeWeightThreshold = this.maxWeight ? Number(this.maxWeight) : 0;
        this.fitView();
        await this.$nextTick();
        this.redrawFromLastData();
        this.setStatus(
          "ok",
          this.aggregateProfiles ? "Profile MST rendered" : "Sample MST rendered",
        );
      } catch (error) {
        this.statsLine = `Error: ${error.message}`;
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
        const response = await fetch("/api/distance-matrix", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            tsv: this.tsvText,
            metadata_tsv: this.metadataText,
            include_missing: this.includeMissing,
            aggregate_profiles: this.aggregateProfiles,
          }),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "request failed");
        }

        this._resetViewState(data, "matrix");
        this.clusterSummary = data.cluster_summary || [];
        this.distanceMatrix = data.matrix || [];
        this.matrixLabels = data.labels || [];
        this.heatmapLoci = [];
        this.heatmapCells = [];
        this.clearSvg();
        this.updateSummary(this.matrixLabels.length, "-", this.matrixLabels.length);
        this.statsLine = `Rendered ${this.matrixLabels.length} × ${this.matrixLabels.length} distance matrix.`;
        this.setStatus("ok", "Distance matrix rendered");
      } catch (error) {
        this.statsLine = `Error: ${error.message}`;
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
        const response = await fetch("/api/allele-heatmap", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            tsv: this.tsvText,
            metadata_tsv: this.metadataText,
            aggregate_profiles: this.aggregateProfiles,
          }),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "request failed");
        }

        this._resetViewState(data, "heatmap");
        this.clusterSummary = [];
        this.distanceMatrix = [];
        this.matrixLabels = data.labels || [];
        this.heatmapLoci = data.loci || [];
        this.heatmapCells = data.cells || [];
        this.heatmapLocusQuery = "";
        this.clearSvg();
        this.updateSummary(this.matrixLabels.length, this.heatmapLoci.length, this.matrixLabels.length);
        this.statsLine = `Rendered ${this.matrixLabels.length} × ${this.heatmapLoci.length} allele heatmap.`;
        this.setStatus("ok", "Allele heatmap rendered");
      } catch (error) {
        this.statsLine = `Error: ${error.message}`;
        this.setStatus("error", error.message || "Failed to build allele heatmap");
        this.clearSvg();
      } finally {
        this._building = false;
      }
    },
    async compareResults() {
      if (this._building) return;
      this._building = true;
      try {
        this.setStatus("ok", "Comparing result sets...");
        const response = await fetch("/api/compare-results", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            left_tsv: this.compareLeftTsv,
            right_tsv: this.compareRightTsv,
          }),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "request failed");
        }

        this.analysisView = "compare";
        this.currentRenderedGraph = null;
        this.currentEdgeWeightGraph = null;
        this.currentCollapseSourceGraph = null;
        this.compareResultsSummary = data.summary;
        this.compareResultRows = data.rows || [];
        this.compareStatusFilter = "";
        this.clearSvg();
        this.statsLine = `Compared ${data.rows.length} samples across two result sets.`;
        this.setStatus("ok", "Comparison summary rendered");
      } catch (error) {
        this.statsLine = `Error: ${error.message}`;
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
    },
    downloadJson(filename, payload) {
      this._downloadBlob(
        filename,
        new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" }),
      );
    },
    _buildNewick(nodeId, parent, weightMap, childrenMap, visited) {
      visited.add(nodeId);
      const kids = childrenMap.get(nodeId) || [];
      const label = this.currentRenderedGraph.nodes.find((n) => n.id === nodeId)?.label || String(nodeId);
      const childNewicks = [];
      for (const kidId of kids) {
        if (!visited.has(kidId)) {
          childNewicks.push(this._buildNewick(kidId, nodeId, weightMap, childrenMap, visited));
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
    },
    exportNewick() {
      if (!this.currentLayout || !this.currentRenderedGraph) {
        this.setStatus("error", "Build a graph before exporting Newick");
        return;
      }
      const layout = this.currentLayout;
      const parentMap = layout.parent;
      const childrenMap = new Map();
      for (const [nodeId, parentId] of parentMap) {
        if (parentId !== -1 && parentId !== undefined) {
          if (!childrenMap.has(parentId)) {
            childrenMap.set(parentId, []);
          }
          childrenMap.get(parentId).push(nodeId);
        }
      }
      const edges = this.currentRenderedGraph.edges || [];
      const weightMap = new Map();
      for (const edge of edges) {
        const sourceId = Number(edge.source);
        const targetId = Number(edge.target);
        const parentId = parentMap.get(sourceId);
        if (parentId === targetId) {
          weightMap.set(String(sourceId), Number(edge.weight));
        }
        const parentId2 = parentMap.get(targetId);
        if (parentId2 === sourceId) {
          weightMap.set(String(targetId), Number(edge.weight));
        }
      }
      const roots = [];
      for (const [nodeId, parentId] of parentMap) {
        if (parentId === -1 || parentId === undefined) {
          roots.push(nodeId);
        }
      }
      if (roots.length === 0) {
        this.setStatus("error", "No root node found for Newick export");
        return;
      }
      const parts = [];
      for (const root of roots) {
        const visited = new Set();
        parts.push(this._buildNewick(root, null, weightMap, childrenMap, visited));
      }
      const newick = parts.join("\n") + ";";
      this._downloadBlob("gmlst_tree.nwk", new Blob([newick], { type: "text/plain;charset=utf-8" }));
      this.setStatus("ok", "Newick tree exported");
    },
    exportGraphJson() {
      if (!this.lastData || !this.currentRenderedGraph) {
        this.setStatus("error", "Build a graph before exporting JSON");
        return;
      }
      this.downloadJson("gmlst_graph.json", {
        schema_version: this.lastData.export?.schema_version || "gmlst-visual-v1",
        exported_from: "gmlst visual",
        graph: this.currentRenderedGraph,
      });
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
        const response = await fetch("/api/locus-diff", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            tsv: this.tsvText,
            metadata_tsv: this.metadataText,
            include_missing: this.includeMissing,
            left_label: this.compareLeftLabel,
            right_label: this.compareRightLabel,
          }),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "request failed");
        }
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
      if (!this.lastData) {
        this.setStatus("error", "Build a graph before exporting session JSON");
        return;
      }
      this.downloadJson("gmlst_session.json", {
        schema_version: this.lastData.export?.schema_version || "gmlst-visual-v1",
        exported_from: "gmlst visual",
        inputs: {
          tsv: this.tsvText,
          metadata_tsv: this.metadataText,
        },
        options: {
          analysis_view: this.analysisView,
          include_missing: this.includeMissing,
          aggregate_profiles: this.aggregateProfiles,
          overlap_relief: this.overlapRelief,
          layout_mode: this.layoutMode,
          edge_length_mode: this.edgeLengthMode,
          edge_length_scale: this.edgeLengthScale,
          long_branch_mode: this.longBranchMode,
          long_branch_threshold: this.longBranchThreshold,
          color_by: this.colorBy,
          max_weight: this.maxWeight,
          collapsed_nodes: this.collapsedNodes,
          collapse_threshold: this.collapseThreshold,
          hidden_legend_values: this.hiddenLegendValues,
          node_search_query: this.nodeSearchQuery,
          show_edge_labels: this.showEdgeLabels,
          scale_node_size: this.scaleNodeSize,
          aggregate_nodes: this.aggregateNodes,
          correctness_overlay: this.correctnessOverlay,
          manual_root_id: this.manualRootId,
          view_filter_mode: this.viewFilterMode,
          cluster_filter: this.clusterFilter,
          node_position_overrides: this.nodePositionOverrides,
          hidden_node_ids: this._hiddenNodeIds,
          custom_node_colors: this._customNodeColors,
        },
        response: this.lastData,
      });
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
      <nav v-if="lastData" class="view-tabs" aria-label="Analysis view switcher">
        <button
          v-for="tab in viewTabs"
          :key="tab.id"
          class="view-tab"
          :class="{ active: analysisView === tab.id }"
          :aria-label="tab.label"
          :aria-pressed="String(analysisView === tab.id)"
          :title="tab.label"
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
            v-model="tsvText"
            placeholder="Paste cgMLST TSV or #Strain profile here"
            aria-label="TSV profile data input"
          ></textarea>

          <details class="foldout">
            <summary>Optional metadata and saved session</summary>
            <div class="foldout-body">
              <label class="field-label" for="metadata-file-input">Metadata TSV/CSV file</label>
              <input id="metadata-file-input" type="file" @change="onMetadataFileChange" />
              <label class="field-label" for="metadata-input">Or paste metadata text</label>
              <textarea
                id="metadata-input"
                v-model="metadataText"
                placeholder="Optional metadata table with ID column or first-column sample IDs"
                aria-label="Metadata TSV input"
              ></textarea>
              <label class="field-label" for="session-file-input">Restore session JSON</label>
              <input id="session-file-input" type="file" @change="onSessionFileChange" />
            </div>
          </details>

          <details class="foldout">
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
            <div class="metric"><span>Nodes</span><strong>{{ summary.nodes }}</strong></div>
            <div class="metric"><span>Edges</span><strong>{{ summary.edges }}</strong></div>
            <div class="metric">
              <span>Meta</span><strong>{{ summary.metaFields }}</strong>
            </div>
          </div>
          <div class="summary-note">
            <strong>Current view</strong>
            <span>{{ statsLine }}</span>
          </div>
          <p class="tip compact-tip">
            View controls below affect only the rendered result, not the uploaded TSV itself.
          </p>
        </section>

        <section v-if="lastData && analysisView !== 'compare'" class="workflow-section">
          <p class="section-title">4. View controls</p>

          <template v-if="analysisView === 'graph'">
            <label class="field-label" for="layout-mode">Layout mode</label>
            <select id="layout-mode" v-model="layoutMode" @change="redrawFromLastData">
              <option value="tree">Tree layout</option>
              <option value="radial">Radial layout</option>
            </select>

            <label class="field-label" for="edge-length-mode">Edge length mode</label>
            <select id="edge-length-mode" v-model="edgeLengthMode" @change="redrawFromLastData">
              <option value="linear">Linear (MLST)</option>
              <option value="log">Logarithmic (cgMLST)</option>
              <option value="sqrt">Square root (cgMLST)</option>
            </select>

            <label class="field-label" for="long-branch-mode">Long branches</label>
            <select id="long-branch-mode" v-model="longBranchMode" @change="debouncedRedraw">
              <option value="normal">Show all</option>
              <option value="shorten">Shorten + dash</option>
              <option value="hide">Hide</option>
            </select>
            <div v-if="longBranchMode !== 'normal'" class="threshold-slider-row">
              <span class="threshold-bound">Min</span>
              <input
                type="range"
                min="1"
                :max="edgeWeightMax || 1"
                step="1"
                v-model.number="longBranchThreshold"
                @input="debouncedRedraw"
              />
              <span class="threshold-bound">{{ edgeWeightMax || '-' }}</span>
            </div>

            <label class="field-label" for="edge-length-scale">
              Edge length scale: {{ edgeLengthScale }}
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
          </template>

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
          </template>

          <label class="field-label" for="cluster-filter">Cluster filter</label>
          <select id="cluster-filter" v-model="clusterFilter" @change="redrawFromLastData">
            <option value="">All clusters</option>
            <option v-for="option in clusterOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>

          <template v-if="analysisView === 'graph'">
            <label class="field-label">
              Collapse threshold
              <span v-if="collapseThreshold > 0" class="threshold-badge">{{ collapseThreshold }}</span>
              <span v-else class="threshold-badge threshold-none">Off</span>
            </label>
            <div class="threshold-slider-row">
              <span class="threshold-bound">Off</span>
              <input
                type="range"
                min="0"
                :max="edgeWeightMax || 1"
                step="1"
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

            <div class="switch-grid">
              <label class="switch">
                <input type="checkbox" v-model="showEdgeLabels" @change="toggleEdgeLabels" />
                Show edge weights
              </label>
              <label class="switch">
                <input type="checkbox" v-model="overlapRelief" @change="redrawFromLastData" />
                Reduce node overlap automatically
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
                <input type="checkbox" v-model="scaleNodeSize" @change="redrawFromLastData" />
                Scale node size by member count
              </label>
              <label class="switch">
                <input
                  type="checkbox"
                  v-model="aggregateNodes"
                  @change="redrawFromLastData"
                />
                Collapse identical profiles after rendering
              </label>
            </div>

            <div class="button-row action-row-tight">
              <button class="btn btn-secondary btn-chip" @click="fitView">Fit view</button>
              <button class="btn btn-secondary btn-chip" @click="clearManualRoot">Reset root</button>
              <button class="btn btn-secondary btn-chip" @click="clearDraggedLayout">
                Reset drag layout
              </button>
            </div>
          </template>
        </section>

        <details v-if="lastData" v-show="analysisView === 'graph'" class="foldout">
          <summary>Inspection details</summary>
          <div class="foldout-body">
            <div v-if="inspectedItem" class="inspect-panel">
              <div class="inspect-title">{{ inspectedItem.title }}</div>
              <div class="inspect-kind">{{ inspectedItem.kind }}</div>
              <div v-for="line in inspectedItem.lines" :key="line" class="inspect-line">
                {{ line }}
              </div>
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
                    @click="toggleTableSort(column.key)"
                  >
                    {{ column.label }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in filteredTableRows"
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
        <div class="viz-header">
          <div class="viz-title-block">
            <h2 class="viz-title">
              {{
                analysisView === 'matrix'
                  ? 'Distance matrix'
                  : analysisView === 'heatmap'
                    ? 'Allele heatmap'
                    : analysisView === 'compare'
                      ? 'Result comparison'
                    : 'Minimum spanning tree'
              }}
            </h2>
            <p class="viz-stats">{{ statsLine }}</p>
          </div>
          <div class="legend">
            <div v-if="legendItems.length === 0" class="legend-title">Legend: fixed node color</div>
            <template v-else>
              <div class="legend-header">
                <span class="legend-title">Legend · {{ colorBy }}</span>
                <button
                  v-if="Object.keys(hiddenLegendValues).length > 0"
                  class="legend-reset"
                  @click="showAllLegendValues"
                >Show all</button>
              </div>
              <span
                v-for="item in legendItems"
                :key="item.value"
                class="legend-item"
                :class="{ 'legend-hidden': hiddenLegendValues[item.value], 'legend-hovered': hoveredLegendValue === item.value }"
                :style="legendItemStyle(item)"
                tabindex="0"
                role="button"
                :aria-pressed="String(!!hiddenLegendValues[item.value])"
                :aria-label="item.value"
                @click="toggleLegendValue(item.value)"
                @keydown.enter="toggleLegendValue(item.value)"
                @keydown.space.prevent="toggleLegendValue(item.value)"
                @contextmenu.prevent="selectNodesByLegendValue(item.value)"
                @mouseenter="hoveredLegendValue = item.value"
                @mouseleave="hoveredLegendValue = null"
              >
                <span class="dot" :style="{ background: hiddenLegendValues[item.value] ? '#94a3b8' : item.color }"></span>
                {{ item.value }}
                <span class="legend-count">{{ item.count }}</span>
              </span>
            </template>
          </div>
        </div>
        <div v-if="analysisView === 'graph'" ref="canvas" class="canvas" role="region" aria-label="Graph viewport — drag to pan, scroll to zoom, right-click nodes to hide">
          <div v-if="_building" class="loading-overlay">
            <div class="loading-spinner"></div>
            <span class="loading-text">Processing...</span>
          </div>
          <template v-if="lastData">
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
          <div v-else class="empty-state">
            <div class="empty-state-intro">
              <div class="empty-state-badge">Start analysis</div>
              <h3>Build a view from your profile table</h3>
              <p>
                The right panel becomes your analysis surface after you build a result. Start by
                loading a profile TSV on the left, then generate an MST for the clearest first-pass
                overview.
              </p>
            </div>
            <div class="empty-state-workflow">
              <p class="section-title">Workflow</p>
              <div class="workflow-steps workflow-steps-analysis">
                <div class="workflow-step is-active">1. Load profile TSV</div>
                <div class="workflow-step">2. Build MST or another view</div>
                <div class="workflow-step is-muted">3. Inspect, filter, and compare samples</div>
              </div>
            </div>
            <div class="empty-state-entry-grid">
              <button
                class="empty-state-entry empty-state-entry-primary"
                :disabled="!hasProfileInput"
                @click="buildMst"
              >
                <span class="empty-state-entry-label">Recommended first view</span>
                <strong>Build MST</strong>
                <span>
                  Best default when you want to understand overall sample relationships quickly.
                </span>
              </button>
              <button
                class="empty-state-entry"
                :disabled="!hasProfileInput"
                @click="buildDistanceMatrix"
              >
                <span class="empty-state-entry-label">Dense comparison</span>
                <strong>Distance matrix</strong>
                <span>Use when you want exact pairwise distances between samples.</span>
              </button>
              <button
                class="empty-state-entry"
                :disabled="!hasProfileInput"
                @click="buildAlleleHeatmap"
              >
                <span class="empty-state-entry-label">Locus-level scan</span>
                <strong>Allele heatmap</strong>
                <span>Use when you want to inspect allele patterns across many loci.</span>
              </button>
            </div>
            <div class="empty-state-help-grid">
              <div class="empty-state-help-card">
                <strong>Recommended first pass</strong>
                <ul class="empty-state-list">
                  <li>Upload or paste a profile TSV</li>
                  <li>Add metadata only if you need coloring or filtering</li>
                  <li>Build MST for the clearest first-pass result</li>
                </ul>
              </div>
              <div class="empty-state-help-card">
                <strong>Before you build</strong>
                <ul class="empty-state-list">
                  <li v-if="hasProfileInput">Your profile TSV is loaded and ready for analysis</li>
                  <li v-else>Load or paste a profile TSV to enable the analysis entry points above</li>
                  <li>Add metadata only when you want coloring, filtering, or labels</li>
                  <li>Use result comparison for comparing two separate TSV outputs</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
        <div v-else-if="analysisView === 'matrix'" class="matrix-panel">
          <div v-if="matrixTruncated" class="status-message warn">
            Showing first {{ matrixRenderLimit }} of {{ matrixTruncatedCount }} rows. Export JSON for full data.
          </div>
          <table class="matrix-table">
            <thead>
              <tr>
                <th></th>
                <th v-for="label in filteredDistanceMatrixView.labels" :key="label">{{ label }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, rowIndex) in filteredDistanceMatrixView.matrix"
                :key="filteredDistanceMatrixView.labels[rowIndex] || rowIndex"
              >
                <th>{{ filteredDistanceMatrixView.labels[rowIndex] || rowIndex }}</th>
                <td v-for="(value, colIndex) in row" :key="`${rowIndex}-${colIndex}`">
                  <div
                    class="matrix-cell"
                    :style="{
                      backgroundColor: `rgba(30, 93, 168, ${Number(value) === 0 ? 0.06 : Math.max(0.1, ((Number(value) || 0) / matrixMaxValue) * 0.62)})`,
                      color:
                        ((Number(value) || 0) / matrixMaxValue) > 0.62
                          ? '#f8fafc'
                          : '#1e293b',
                    }"
                    :title="matrixTitle(filteredDistanceMatrixView.labels[rowIndex], filteredDistanceMatrixView.labels[colIndex], value)"
                    @click="triggerCompareFromPair(filteredDistanceMatrixView.labels[rowIndex], filteredDistanceMatrixView.labels[colIndex])"
                  >
                    {{ value }}
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else-if="analysisView === 'heatmap'" class="matrix-panel">
          <div class="table-toolbar">
            <input
              v-model="heatmapLocusQuery"
              class="table-search"
              type="text"
              placeholder="Filter loci"
            />
            <button class="btn btn-secondary btn-chip" @click="exportHeatmapTsv">
              Export heatmap TSV
            </button>
            <button class="btn btn-secondary btn-chip" @click="exportHeatmapJson">
              Export heatmap JSON
            </button>
          </div>
          <div v-if="heatmapTruncated" class="status-message warn">
            Showing first {{ matrixRenderLimit }} of {{ heatmapTruncatedCount }} rows. Export JSON for full data.
          </div>
          <div v-if="heatmapLociTruncated" class="status-message warn">
            Showing first {{ lociRenderLimit }} of {{ heatmapLociTruncatedCount }} loci. Use locus filter to narrow.
          </div>
          <table class="matrix-table">
            <thead>
              <tr>
                <th></th>
                <th v-if="colorBy">{{ colorBy }}</th>
                <th v-for="locus in filteredHeatmapLociView.loci" :key="locus">{{ locus }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, rowIndex) in filteredHeatmapLociView.cells"
                :key="filteredHeatmapView.labels[rowIndex] || rowIndex"
              >
                <th
                  @click="fillCompareFromPair(filteredHeatmapView.labels[rowIndex], compareRightLabel || filteredHeatmapView.labels[rowIndex])"
                  @dblclick="triggerCompareFromPair(compareLeftLabel || filteredHeatmapView.labels[rowIndex], filteredHeatmapView.labels[rowIndex])"
                >
                  {{ filteredHeatmapView.labels[rowIndex] || rowIndex }}
                </th>
                <td v-if="colorBy">
                  <div
                    class="matrix-cell annotation-cell"
                    :style="{ background: heatmapAnnotationRows[rowIndex]?.color || '#e5e7eb' }"
                    :title="`${filteredHeatmapView.labels[rowIndex]} · ${colorBy}: ${heatmapAnnotationRows[rowIndex]?.value || '-'}`"
                  >
                    {{ heatmapAnnotationRows[rowIndex]?.value || '-' }}
                  </div>
                </td>
                <td v-for="(cell, cellIndex) in row" :key="`${rowIndex}-${cellIndex}`">
                  <div
                    class="matrix-cell"
                    :class="heatmapClass(cell.state)"
                    :title="`${filteredHeatmapView.labels[rowIndex]} · ${filteredHeatmapLociView.loci[cellIndex]}: ${cell.value} (${cell.state})`"
                  >
                    {{ cell.value }}
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="matrix-panel">
          <div v-if="compareResultsSummary" class="compare-summary-grid">
            <div class="metric"><span>Matched</span><strong>{{ compareResultsSummary.matched_samples }}</strong></div>
            <div class="metric"><span>Same ST</span><strong>{{ compareResultsSummary.same_st }}</strong></div>
            <div class="metric"><span>Different ST</span><strong>{{ compareResultsSummary.different_st }}</strong></div>
            <div class="metric"><span>Locus diff</span><strong>{{ compareResultsSummary.samples_with_locus_differences }}</strong></div>
            <div class="metric"><span>Left only</span><strong>{{ compareResultsSummary.left_only }}</strong></div>
            <div class="metric"><span>Right only</span><strong>{{ compareResultsSummary.right_only }}</strong></div>
          </div>
          <div class="table-toolbar">
            <select v-model="compareStatusFilter">
              <option value="">All statuses</option>
              <option v-for="option in compareStatusOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </div>
          <table class="isolate-table">
            <thead>
              <tr>
                <th>Sample</th>
                <th>Left ST</th>
                <th>Right ST</th>
                <th>Diff loci</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in filteredCompareRows" :key="row.sample_id">
                <td>{{ row.sample_id }}</td>
                <td>{{ row.left_st || '-' }}</td>
                <td>{{ row.right_st || '-' }}</td>
                <td>{{ row.differing_loci_count }}</td>
                <td>{{ row.status }}</td>
              </tr>
            </tbody>
          </table>
        </div>
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
