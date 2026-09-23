# Species Fingerprint Database

The fingerprint database enables `gmlst typing mlst sample.fna` (zero-argument species auto-detection) by matching genome k-mer sketches against per-organism fingerprints.

## Design Rationale

### MLST-Only Source (v0.3.2+)

Fingerprints are built exclusively from **MLST schemes** (7 housekeeping genes per organism). cgMLST schemes are deliberately excluded:

| Aspect | MLST source | cgMLST source |
|---|---|---|
| Download time | Seconds | Minutes per scheme |
| Disk usage | KB per scheme | Hundreds of MB |
| Species discrimination | Sufficient (housekeeping genes are species-specific) | No improvement for species-level ID |
| Fingerprint build | < 5 minutes total | 30+ minutes with rate-limit retries |

**Key insight**: For species *identification* (not typing), 7 housekeeping genes provide the same discrimination as 2000+ core genome loci. Using cgMLST data for fingerprints wastes download time and disk without improving detection accuracy.

### Organism Name Matching

The catalog groups schemes by exact `organism` string. Some organisms appear under different names across providers (e.g., "Escherichia coli" vs "Escherichia spp."), which may cause an organism to appear as "no MLST available" when a matching scheme exists under a variant name. Improving fuzzy organism matching is a future enhancement.

## Coverage

~140-145 species (MLST scheme holders in the combined PubMLST + Pasteur + Enterobase catalog).

The full species list is included in the bundled database file. See `gmlst/data/species_fingerprints.json.gz` (included in the package).

### Not Covered

Organisms without any MLST scheme in the catalog, including:

- cgMLST/wgMLST-only species (e.g., *Enterobacter hormaechei*, *Morganella morganii*)
- Organisms with naming mismatches across providers
- Organisms whose data requires PubMLST authentication or has been removed server-side

## Technical Parameters

| Parameter | Value | Description |
|---|---|---|
| k-mer size | 21 | Canonical (two-bit encoded) k-mers |
| Sample rate | 7 | Every 7th k-mer is hashed (reduces fingerprint size) |
| Max hashes/species | 5,000 | Uniform cap regardless of source scheme size |
| Scoring | Containment | \|query ∩ fingerprint\| / \|fingerprint\| |
| Unique detection | top ≥ 0.3 AND top ≥ 2×runner-up | Margin rule for unambiguous matches |

## File Locations

| Location | Path | Purpose |
|---|---|---|
| User-built | `<cache>/species_fingerprints.json.gz` | Freshest data (via `update-fingerprints`) |
| Bundled | `gmlst/data/species_fingerprints.json.gz` | Ships with package (~1 MB) |
| Format | zlib-compressed JSON | 80 MB raw → ~1 MB compressed |

## Lookup Order

When `typing` omits `-s`/`-n`:

1. `<cache>/species_fingerprints.json.gz` (user-built)
2. `gmlst/data/species_fingerprints.json.gz` (bundled)
3. Interactive prompt to build now (TTY only, declines to exit 2)

## Regeneration

```bash
# Full rebuild (downloads missing MLST schemes)
gmlst scheme update-fingerprints -y [-x N]

# Specific organisms only
gmlst scheme update-fingerprints -o "Bordetella pertussis,Staphylococcus aureus"
```

### Notes

- PubMLST API key recommended: `gmlst config set GMLST_PUBMLST_API_KEY <key>`
- Already-cached schemes are skipped (rebuilds are incremental)
- Rate-limited servers may cause transient failures; re-run to retry
- Build time: < 5 minutes when schemes are cached
