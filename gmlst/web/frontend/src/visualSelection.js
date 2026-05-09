export function selectedNodeId(inspectedItem) {
  if (inspectedItem && inspectedItem.kind === "node") {
    return inspectedItem.nodeId ?? null;
  }
  return null;
}

export function buildNodeInspection(node) {
  const lines = [];
  if (node.member_count && node.member_count > 1) {
    lines.push(`members: ${node.member_count}`);
    const preview = (node.members || []).slice(0, 8).join(", ");
    if (preview) {
      lines.push(`samples: ${preview}`);
    }
    if ((node.members || []).length > 8) {
      lines.push(`… +${node.members.length - 8} more`);
    }
  }
  for (const [key, value] of Object.entries(node.meta || {})) {
    lines.push(`${key}: ${value}`);
  }

  return {
    kind: "node",
    title: node.label,
    lines,
    nodeId: node.id,
  };
}

export function filterTableRows(rows, query) {
  let filteredRows = rows;
  const normalizedQuery = String(query || "").trim().toLowerCase();
  if (!normalizedQuery) {
    return filteredRows;
  }

  filteredRows = rows.filter((row) => {
    const haystack = [
      row.sample_id,
      row.label,
      row.profile_key,
      ...(row.members || []),
      ...Object.values(row.meta || {}),
    ]
      .map((value) => String(value || "").toLowerCase())
      .join(" ");
    return haystack.includes(normalizedQuery);
  });
  return filteredRows;
}

export function sortTableRows(rows, sortKey, sortDirection) {
  const direction = sortDirection === "desc" ? -1 : 1;
  const valueFor = (row) => {
    if (sortKey in (row.meta || {})) {
      return row.meta?.[sortKey] ?? "";
    }
    return row[sortKey] ?? "";
  };

  return [...rows]
    .map((row, index) => ({ row, index }))
    .sort((left, right) => {
      const leftValue = valueFor(left.row);
      const rightValue = valueFor(right.row);

      const leftNum = Number(leftValue);
      const rightNum = Number(rightValue);
      const bothNumeric = !Number.isNaN(leftNum) && !Number.isNaN(rightNum);

      let cmp = 0;
      if (bothNumeric) {
        cmp = leftNum - rightNum;
      } else {
        cmp = String(leftValue).localeCompare(String(rightValue));
      }

      if (cmp !== 0) {
        return cmp * direction;
      }
      return left.index - right.index;
    })
    .map((item) => item.row);
}

export function visibleTableColumns(metadataFields) {
  const base = [
    { key: "sample_id", label: "Sample" },
    { key: "ST", label: "ST" },
    { key: "cluster_id", label: "Cluster" },
    { key: "member_count", label: "Members" },
    { key: "profile_key", label: "Profile" },
  ];
  const metadataColumns = metadataFields
    .filter((field) => !["ST"].includes(field))
    .map((field) => ({ key: field, label: field }));
  return [...base, ...metadataColumns];
}

export function filterRowsForSelection(rows, selectedId, selectionOnly) {
  if (!selectionOnly || selectedId == null) {
    return rows;
  }
  return rows.filter((row) => row.id === selectedId);
}

export function availableClusterOptions(clusterSummary) {
  return clusterSummary.map((cluster) => ({
    value: String(cluster.cluster_id),
    label: `Cluster ${cluster.cluster_id} (${cluster.sample_count})`,
  }));
}

export function filterRowsByCluster(rows, clusterFilter) {
  if (!clusterFilter) {
    return rows;
  }
  return rows.filter((row) => String(row.cluster_id) === String(clusterFilter));
}

export function valueForColumn(row, key) {
  if (key in (row.meta || {})) {
    return row.meta?.[key] ?? "";
  }
  return row[key] ?? "";
}

export function tableRowsToTsv(rows, columns) {
  const header = columns.map((column) => column.label).join("\t");
  const lines = rows.map((row) =>
    columns.map((column) => String(valueForColumn(row, column.key) || "")).join("\t"),
  );
  return [header, ...lines].join("\n") + "\n";
}

export function filterDistanceMatrix(labels, matrix, rows, clusterFilter) {
  if (!clusterFilter) {
    return { labels, matrix };
  }
  const selectedIndexes = rows
    .map((row, index) => ({ row, index }))
    .filter(({ row }) => String(row.cluster_id) === String(clusterFilter))
    .map(({ index }) => index);
  return {
    labels: selectedIndexes.map((index) => labels[index]),
    matrix: selectedIndexes.map((rowIndex) =>
      selectedIndexes.map((colIndex) => matrix[rowIndex][colIndex]),
    ),
  };
}

export function matrixCellTitle(rowLabel, colLabel, value) {
  return `${rowLabel} ↔ ${colLabel}: ${value}`;
}

export function filterAlleleHeatmap(labels, loci, cells, rows, clusterFilter) {
  if (!clusterFilter) {
    return { labels, loci, cells };
  }
  const selectedIndexes = rows
    .map((row, index) => ({ row, index }))
    .filter(({ row }) => String(row.cluster_id) === String(clusterFilter))
    .map(({ index }) => index);
  return {
    labels: selectedIndexes.map((index) => labels[index]),
    loci,
    cells: selectedIndexes.map((index) => cells[index]),
  };
}

export function heatmapCellClass(state) {
  return `heatmap-cell-${state || "unknown"}`;
}

export function heatmapAnnotations(labels, rows, colorBy, colorMap) {
  return labels.map((label) => {
    const row = rows.find((entry) => entry.sample_id === label || entry.label === label);
    const value = row
      ? colorBy === "cluster_id"
        ? String(row.cluster_id)
        : row.meta?.[colorBy] || ""
      : "";
    return {
      label,
      value,
      color: value ? colorMap.get(value) || "#e5e7eb" : "#e5e7eb",
    };
  });
}

export function filterAlleleHeatmapLoci(loci, cells, query) {
  const normalizedQuery = String(query || "").trim().toLowerCase();
  if (!normalizedQuery) {
    return { loci, cells };
  }
  const selectedIndexes = loci
    .map((locus, index) => ({ locus, index }))
    .filter(({ locus }) => String(locus).toLowerCase().includes(normalizedQuery))
    .map(({ index }) => index);
  return {
    loci: selectedIndexes.map((index) => loci[index]),
    cells: cells.map((row) => selectedIndexes.map((index) => row[index])),
  };
}

export function nextCompareSelection(currentLeft, currentRight, candidateLabel) {
  if (!candidateLabel) {
    return { left: currentLeft, right: currentRight };
  }
  if (!currentLeft || currentLeft === candidateLabel) {
    return { left: candidateLabel, right: currentRight === candidateLabel ? "" : currentRight };
  }
  if (!currentRight || currentRight === candidateLabel) {
    return { left: currentLeft, right: candidateLabel };
  }
  return { left: currentRight, right: candidateLabel };
}

export function comparePayloadToJson(comparePayload) {
  return JSON.stringify(comparePayload, null, 2);
}

export function heatmapToTsv(labels, loci, cells) {
  const header = ["Sample", ...loci].join("\t");
  const lines = cells.map((row, index) =>
    [labels[index], ...row.map((cell) => cell.value)].join("\t"),
  );
  return [header, ...lines].join("\n") + "\n";
}

export function heatmapPayloadToJson(payload) {
  return JSON.stringify(payload, null, 2);
}

export function compareSelectionFromPair(currentLeft, currentRight, leftLabel, rightLabel) {
  if (!leftLabel || !rightLabel || leftLabel === rightLabel) {
    return { left: currentLeft, right: currentRight };
  }
  return { left: leftLabel, right: rightLabel };
}

export function compareRequestFromSelection(leftLabel, rightLabel) {
  if (!leftLabel || !rightLabel || leftLabel === rightLabel) {
    return null;
  }
  return {
    left_label: leftLabel,
    right_label: rightLabel,
  };
}

export function compareStatusOptions(rows) {
  const statuses = [...new Set(rows.map((row) => row.status))].sort();
  return statuses.map((status) => ({ value: status, label: status }));
}

export function filterCompareRows(rows, statusFilter) {
  if (!statusFilter) {
    return rows;
  }
  return rows.filter((row) => row.status === statusFilter);
}
