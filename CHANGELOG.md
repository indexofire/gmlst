# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - Planned

### Planned
- Cache storage optimization: support compressed scheme artifacts for downloaded
  allele/profile data to reduce disk usage.
- Keep backend typing behavior unchanged while adding compression support
  (indexing/typing should continue to use materialized local files).
- Design provider-specific incremental update strategy to avoid full re-downloads:
  - PubMLST/Pasteur (BigsDB): compare remote metadata and fetch only changed
    loci/profile assets when possible.
  - Enterobase/cgMLST: evaluate available metadata/headers and implement
    best-effort incremental sync.
- Extend `.meta.json` schema to track update metadata needed for incremental
  refresh (for example: timestamps/checksums/ETag-like fields).

### Scope Note
- `0.1.x` remains focused on basic functionality verification and stability.
- The compression + incremental-update work is deferred to `0.2.0`.

## [0.1.0] - 2026-03-13

### Added
- Initial release of gmlst
- Multiple alignment backends: BLASTN, minimap2, nucmer, kmerhash
- Support for FASTA (assembled genomes) and FASTQ (raw reads) inputs
- Multiple database providers: PubMLST, Pasteur, Enterobase
- Batch processing capability
- CLI interface compatible with tseemann/mlst output format
- Configurable identity and coverage thresholds
- Thread support for BLASTN backend
- Caching system for schemes and alignment indexes

### Features
- **blastn**: NCBI BLASTN backend for assembled genomes
- **minimap2**: Fast aligner supporting both FASTA and FASTQ
- **nucmer**: MUMmer4 backend for sensitive distant matches
- **kmerhash**: Pure Python backend with no external dependencies

[0.1.0]: https://github.com/yourusername/gmlst/releases/tag/v0.1.0


## [0.1.4] - 2026-03-18

### Added

#### Novel Allele Detection & Custom Schemes
- **`gmlst typing --novel-allele`**: Detect and save novel allele sequences to `{locus}_novel.fasta` files
- **`gmlst typing --novel-profile`**: Generate novel ST profiles and save to `profiles_novel.txt`
- **`gmlst scheme create`**: Create custom schemes by merging public databases with novel data
  - Auto-numbering: custom_1, custom_2, ...
  - Based on existing schemes (e.g., saureus_1 → custom_1)
  - Stores metadata in `.meta.json`
- **`gmlst scheme update`**: Add more novel data to existing custom schemes
  - Continues numbering from where it left off (n3, n4... N3, N4...)
- **`gmlst scheme export --format grapetree`**: Export profiles for GrapeTree MST visualization

#### Custom Database Workflow
Complete pipeline for private/laboratory MLST databases:
```bash
# 1. Type samples and keep JSON output
gmlst typing -s saureus_1 --format json sample.fasta -o typing_results.json

# 2. Extract novel alleles/profiles from typing JSON
gmlst utils extract -i typing_results.json --novel-allele --novel-profile --data-dir novel_data/

# 3. Create custom scheme from novel data
gmlst scheme create -t mlst -s saureus_1 --data-dir novel_data/ --desc "Lab collection"

# 4. Update custom scheme with more data
gmlst scheme update-custom -s custom_1 --data-dir more_novel_data/

# 5. Export for GrapeTree analysis
gmlst scheme export -s custom_1 --format grapetree -o mst.tsv
```

#### Novel Sequence Extraction
- BLASTN aligner now extracts actual sequences from alignments
- Novel alleles (good coverage but low identity) capture sample sequence
- Sequences are saved in FASTA format: `>{locus}_n1 sample=isolate_001`

#### Local Provider Support
- Custom schemes use `provider: local`
- Listed in `gmlst scheme list -p local`
- Stored in `~/.cache/gmlst/local/custom_*/`

### Technical Details

#### Data Formats
- **Novel alleles**: `{locus}_n{number}` format (e.g., `dnaN_n1`)
- **Novel profiles**: `N{number}` ST format (e.g., `N1`, `N2`)
- **GrapeTree export**: TSV with `#Strain` header, compatible with MST visualization

#### File Structure
```
~/.cache/gmlst/local/custom_1/
├── {locus}.tfa          # Merged: original + novel alleles
├── custom_1.txt         # Merged: original + novel profiles
└── .meta.json           # Metadata: based_on, description, novel counts
```

[0.1.4]: https://github.com/yourusername/gmlst/releases/tag/v0.1.4
