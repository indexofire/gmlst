---
status: archived
archived_date: 2026-04-08
archived_from: docs/internal/analysis/
archive_reason: "Investigation completed with final root-cause conclusions"
---

# chewBBACA vs gmlst Allele Discrepancy Analysis (22VPA0001)

This document records the completed root-cause analysis for allele-number
differences between chewBBACA and gmlst on the same sample (`22VPA0001`).

## Scope and Inputs

- Sample: `tests/fastq/fna/22VPA0001.fna` (same biological sample used in all
  compared outputs)
- Consolidated comparison table: `tests/fastq/1.csv`
- chewBBACA calls: `tests/fastq/chewbbaca/results_alleles.tsv`
- Per-locus sequence/mapping evidence:
  - `tests/fastq/chewbbaca_vs_gmlst_numeric_diff_with_sequences_correct_db.tsv`
  - `tests/fastq/chewbbaca_vs_gmlst_numeric_diff_summary.txt`
  - `tests/fastq/chewbbaca_vs_gmlst_numeric_diff_reason.tsv`

## Executive Summary

1. Numeric allele differences exist, but they are not random caller noise.
2. All analyzed numeric-diff loci map as full-identity matches to the same
   contig region, with different start/end boundaries.
3. The dominant reason class is CDS boundary selection differences
   (5' or 3' boundary shift), not within-interval sequence disagreement.
4. VP0004 is representative: both calls are valid full matches, but with
   different 5' start boundary and different allele definitions.

## Verified Counts

From `tests/fastq/chewbbaca_vs_gmlst_numeric_diff_summary.txt`:

- `total_numeric_diff = 214`
- `chew_maps_full = 214`
- `gmlst_maps_full = 214`
- `chew_allele_missing_in_db = 0`
- `gmlst_allele_missing_in_db = 0`

From `tests/fastq/chewbbaca_vs_gmlst_numeric_diff_reason.tsv`:

- `five_prime_boundary_shift + chew_shorter = 92`
- `three_prime_boundary_shift + chew_shorter = 54`
- `five_prime_boundary_shift + gmlst_shorter = 37`
- `three_prime_boundary_shift + gmlst_shorter = 31`

Total: `214` loci.

## VP0004 Deep-Dive Conclusion

Evidence row: `VP0004` in
`tests/fastq/chewbbaca_vs_gmlst_numeric_diff_with_sequences_correct_db.tsv`
and `tests/fastq/chewbbaca_vs_gmlst_numeric_diff_reason.tsv`.

- chewBBACA call: allele `68`, length `324`
- gmlst call: allele `1`, length `357`
- Both are full genome matches on `contig00026` at 100% identity.
- Coordinate relationship shows a 5' boundary shift:
  - chew: `28659..28982`
  - gmlst: `28626..28982`

Interpretation: this is a start-boundary choice difference for the same genomic
region (not a random mismatch and not a failed alignment).

## Why This Pattern Is Expected

chewBBACA allele calling is CDS-centric and depends on predicted CDS
boundaries, while alignment-first workflows can recover longer/alternate
boundaries in the same region.

References:

- chewBBACA AlleleCall (CDS requirement and classes):
  https://chewbbaca.readthedocs.io/en/latest/user/modules/AlleleCall.html
- Prodigal start-site modeling and alternative start selection:
  https://pmc.ncbi.nlm.nih.gov/articles/PMC2848648/
- Prodigal edge/partial behavior:
  https://github.com/hyattpd/Prodigal/wiki/Understanding-the-Prodigal-Output
- chewBBACA method overview (DNA exact + protein-level strategy):
  https://pmc.ncbi.nlm.nih.gov/articles/PMC5885018/

## Final Root-Cause Statement (All Non-VP0004 Numeric-Diff Loci)

For this sample and this scheme/database combination, the non-VP0004 numeric
allele discrepancies follow the same mechanism as VP0004: boundary-shifted
allele definitions/calls on the same mapped locus interval family.

In this analysis set, every one of the 214 numeric-diff loci is explained by
5' or 3' boundary shifts; no additional mismatch class was required.
