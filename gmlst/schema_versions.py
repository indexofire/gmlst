"""Schema version constants for gmlst CLI JSON outputs.

Every JSON document emitted to stdout or to an output file by the gmlst CLI
is wrapped in a versioned envelope:

    {"schema_version": "<constant>", "data": <payload>}

Agents that parse CLI output programmatically can read ``schema_version``
to detect format changes before interpreting ``data``. TSV/CSV/text/jsonl
outputs are not enveloped.
"""

from __future__ import annotations

# typing commands (`typing mlst` / `typing cgmlst --format json`): list of
# per-sample result dicts.
TYPING_RESULTS_V1 = "gmlst-typing-v1"

# `typing tgmlst --format json`: list of scheme-free profile dicts.
TGMLST_PROFILES_V1 = "gmlst-tgmlst-profiles-v1"

# `typing tgmlst --stats` (emitted on stderr): run statistics dict.
TGMLST_STATS_V1 = "gmlst-tgmlst-stats-v1"

# `scheme list` / `scheme search --format json`: list of scheme dicts.
SCHEME_LIST_V1 = "gmlst-scheme-list-v1"

# `scheme show --format json`: single scheme detail dict.
SCHEME_SHOW_V1 = "gmlst-scheme-show-v1"

# Write-operation summaries for `scheme download`, `scheme update`,
# `scheme create`, and `scheme update-custom --format json`.
SCHEME_OP_V1 = "gmlst-scheme-op-v1"

# `utils benchmark --format json`: benchmark metrics document.
BENCHMARK_V1 = "gmlst-benchmark-v1"

# `visual mst --format json` / `--format summary` payloads.
VISUAL_MST_V1 = "gmlst-visual-mst-v1"
VISUAL_MST_SUMMARY_V1 = "gmlst-visual-mst-summary-v1"

# `visual matrix --format json`: pairwise distance matrix payload.
VISUAL_MATRIX_V1 = "gmlst-visual-matrix-v1"

# `visual heatmap --format json`: allele heatmap payload.
VISUAL_HEATMAP_V1 = "gmlst-visual-heatmap-v1"

# `visual compare --format json`: two-result comparison payload.
VISUAL_COMPARE_V1 = "gmlst-visual-compare-v1"

# `visual locus-diff --format json`: pairwise locus diff payload.
VISUAL_LOCUS_DIFF_V1 = "gmlst-visual-locus-diff-v1"

# `config get --format json`: single configuration value snapshot.
CONFIG_GET_V1 = "gmlst-config-get-v1"
