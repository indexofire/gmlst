"""Golden --help snapshots for the typing subcommands.

Captured from the CLI before the shared option-factory consolidation;
flag names, defaults, ordering, and help text must stay byte-identical
(the Usage line is stripped because it varies with the entry point).
"""

from __future__ import annotations

from click.testing import CliRunner

from gmlst.cli import main

MLST_HELP = (
    "\n"
    "  Type samples against MLST schemes only.\n"
    "\n"
    "Options:\n"
    "  -s, --scheme TEXT               MLST scheme name, e.g. 'saureus_1' (omit to\n"
    "                                  auto-detect species).\n"
    "  -n, --organism TEXT             Resolve the scheme by organism or scheme-name\n"
    "                                  substring, e.g. 'bordetella'.\n"
    "  -g, --guess                     Unattended mixed-species typing: detect each\n"
    "                                  assembly's species, pick the scheme\n"
    "                                  automatically (downloading if needed), and\n"
    "                                  never prompt. Incompatible with -s/-n and the\n"
    "                                  novel flags.\n"
    "  -b, --backend [blastn|kma|minimap2|nucmer]\n"
    "                                  Alignment backend to use.  [default: blastn]\n"
    "  --min-id FLOAT                  Minimum percent identity.  [default: 95.0]\n"
    "  --min-cov FLOAT                 Minimum allele coverage (0-1).  [default:\n"
    "                                  0.95]\n"
    "  --min-depth FLOAT               Min read depth (FASTQ only).  [default: 10.0]\n"
    "  --min-join-overlap INTEGER RANGE\n"
    "                                  Minimum allele-coordinate overlap (bp)\n"
    "                                  required to join contig fragments of a split\n"
    "                                  gene into one call.  [default: 10; x>=0]\n"
    "  --minscore FLOAT                Minimum sample quality score (0-100) to\n"
    "                                  report; samples below are dropped from\n"
    "                                  TSV/JSON output. Scores appear in JSON output.\n"
    "                                  [default: 0.0]\n"
    "  --format [tsv|json|pretty]      Output format.  [default: tsv]\n"
    "  -o, --output PATH               Write output to file.\n"
    "  --cache-dir PATH                Override cache directory.\n"
    "  --force-reindex                 Rebuild aligner index.\n"
    "  --no-header                     Suppress TSV header line\n"
    "  -t, --threads INTEGER           Number of alignment threads (backend-\n"
    "                                  dependent).  [default: 1]\n"
    "  --max-workers INTEGER RANGE     Number of samples to type in parallel\n"
    "                                  (mlst/cgmlst).  [default: 1; x>=1]\n"
    "  --count-same-copy               Count same-allele multicopy hits (currently\n"
    "                                  blastn) and show notation like 1,1.\n"
    "  --max-depth FLOAT RANGE         Subsample FASTQ to this depth (0=disabled,\n"
    "                                  FASTQ only).  [default: 100; x>=0]\n"
    "  -q, --quiet                     Suppress non-error logging.\n"
    "  --detail                        Show contig position info in TSV output (FASTA\n"
    "                                  only).\n"
    "  --novel-allele                  Save novel allele sequences to\n"
    "                                  {locus}_novel.fasta files.\n"
    "  --novel-profile                 Save novel ST profiles to profiles_novel.txt\n"
    "                                  (requires --novel-allele).\n"
    "  --data-dir, --output-dir PATH   Directory for novel allele/profile output\n"
    "                                  files (default: cwd).\n"
    "  -h, --help                      Show this message and exit.\n"
)

CGMLST_HELP = (
    "\n"
    "  Type samples against cgMLST/wgMLST schemes only.\n"
    "\n"
    "Options:\n"
    "  -s, --scheme TEXT               cgMLST/wgMLST scheme name, e.g.\n"
    "                                  'vparahaemolyticus_3' (omit to auto-detect).\n"
    "  -n, --organism TEXT             Resolve the scheme by organism or scheme-name\n"
    "                                  substring, e.g. 'vibrio'.\n"
    "  -g, --guess                     Unattended mixed-species typing: detect each\n"
    "                                  assembly's species, pick the scheme\n"
    "                                  automatically (downloading if needed), and\n"
    "                                  never prompt. Incompatible with -s/-n and the\n"
    "                                  novel flags.\n"
    "  -b, --backend [blastn|kma|minimap2|nucmer]\n"
    "                                  Alignment backend to use.  [default: minimap2]\n"
    "  --cgmlst-mode [fast|ultrafast|balanced]\n"
    "                                  cgMLST workflow mode.  [default: fast]\n"
    "  --min-id FLOAT                  Minimum percent identity.  [default: 95.0]\n"
    "  --min-cov FLOAT                 Minimum allele coverage (0-1).  [default:\n"
    "                                  0.95]\n"
    "  --min-depth FLOAT               Min read depth (FASTQ only).  [default: 10.0]\n"
    "  --min-join-overlap INTEGER RANGE\n"
    "                                  Minimum allele-coordinate overlap (bp)\n"
    "                                  required to join contig fragments of a split\n"
    "                                  gene into one call.  [default: 10; x>=0]\n"
    "  --minscore FLOAT                Minimum sample quality score (0-100) to\n"
    "                                  report; samples below are dropped from\n"
    "                                  TSV/JSON output. Scores appear in JSON output.\n"
    "                                  [default: 0.0]\n"
    "  --format [tsv|json|pretty]      Output format.  [default: tsv]\n"
    "  -o, --output PATH               Write output to file.\n"
    "  --cache-dir PATH                Override cache directory.\n"
    "  --force-reindex                 Rebuild aligner index.\n"
    "  --no-header                     Suppress TSV header line\n"
    "  -t, --threads INTEGER           Number of alignment threads (backend-\n"
    "                                  dependent).  [default: 1]\n"
    "  --max-workers INTEGER RANGE     Number of samples to type in parallel\n"
    "                                  (mlst/cgmlst).  [default: 1; x>=1]\n"
    "  --count-same-copy               Count same-allele multicopy hits (currently\n"
    "                                  blastn) and show notation like 1,1.\n"
    "  -q, --quiet                     Suppress non-error logging.\n"
    "  --prefilter-k INTEGER RANGE     k-mer length for cgMLST assembly prefilter.\n"
    "                                  [default: 31; x>=11]\n"
    "  --prefilter-top-n INTEGER RANGE\n"
    "                                  Top N allele candidates per locus from\n"
    "                                  prefilter.  [default: 20; x>=1]\n"
    "  --prefilter-min-loci-fraction FLOAT RANGE\n"
    "                                  Minimum loci fraction required to trust\n"
    "                                  prefilter results.  [default: 0.3;\n"
    "                                  0.0<=x<=1.0]\n"
    "  --no-prefilter                  Disable cgMLST assembly prefilter and use\n"
    "                                  full-locus backend indexing.\n"
    "  --novel-allele                  Save novel allele sequences to\n"
    "                                  {locus}_novel.fasta files.\n"
    "  --novel-profile                 Save novel ST profiles to profiles_novel.txt\n"
    "                                  (requires --novel-allele).\n"
    "  --data-dir, --output-dir PATH   Directory for novel allele/profile output\n"
    "                                  files (default: cwd).\n"
    "  --cds-coordinates-out PATH      Write predicted CDS coordinates TSV for\n"
    "                                  alignment with chewBBACA outputs.\n"
    "  --call-policy [default|chewbbaca|chew-exact]\n"
    "                                  Allele decision policy. chewbbaca: chewBBACA\n"
    "                                  labels. chew-exact: forces single mode + CDS\n"
    "                                  gate.  [default: default]\n"
    "  --chew-cds-gate / --no-chew-cds-gate\n"
    "                                  When --call-policy chewbbaca is enabled,\n"
    "                                  require allele evidence to pass predicted-CDS\n"
    "                                  gate before numeric classification.  [default:\n"
    "                                  chew-cds-gate]\n"
    "  -h, --help                      Show this message and exit.\n"
)

TGMLST_HELP = (
    "\n"
    "  Run scheme-free typing pipeline (tgMLST).\n"
    "\n"
    "Options:\n"
    "  --format [tsv|json|pretty]      Output format.  [default: tsv]\n"
    "  -o, --output PATH               Write output to file.\n"
    "  --no-header                     Suppress TSV header line\n"
    "  -q, --quiet                     Suppress non-error logging.\n"
    "  --hash-strategy [safe|fast|ultra|strict|blast]\n"
    "                                  Hash strategy for allele identification.\n"
    "                                  [default: safe]\n"
    "  --save-scheme PATH              Write discovered schemefree scheme JSON.\n"
    "  --load-scheme PATH              Load an existing schemefree scheme JSON before\n"
    "                                  typing.\n"
    "  --stats                         Print pipeline run stats to stderr.\n"
    "  --max-workers INTEGER           Override schemefree max parallel samples.\n"
    "  -t, --threads INTEGER RANGE     MMseqs clustering threads for tgMLST.  [x>=1]\n"
    "  --assemble-timeout FLOAT        Override schemefree assembly timeout seconds.\n"
    "  --error-report PATH             Write per-sample schemefree errors to JSON.\n"
    "  --fail-on-error                 Return non-zero if any schemefree sample\n"
    "                                  fails.\n"
    "  --summary-report PATH           Write machine-readable schemefree run summary\n"
    "                                  JSON.\n"
    "  -h, --help                      Show this message and exit.\n"
)


def _options_section(result_output: str) -> str:
    lines = result_output.splitlines()
    assert lines[0].startswith("Usage:")
    return "\n".join(lines[1:]).rstrip() + "\n"


def test_typing_mlst_help_snapshot() -> None:
    result = CliRunner().invoke(main, ["typing", "mlst", "--help"])
    assert result.exit_code == 0
    assert _options_section(result.output) == MLST_HELP


def test_typing_cgmlst_help_snapshot() -> None:
    result = CliRunner().invoke(main, ["typing", "cgmlst", "--help"])
    assert result.exit_code == 0
    assert _options_section(result.output) == CGMLST_HELP


def test_typing_tgmlst_help_snapshot() -> None:
    result = CliRunner().invoke(main, ["typing", "tgmlst", "--help"])
    assert result.exit_code == 0
    assert _options_section(result.output) == TGMLST_HELP
