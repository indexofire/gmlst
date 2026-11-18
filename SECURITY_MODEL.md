# gmlst security model

Status: draft built from the code at `main` (308fe63). Assumptions marked "assumed" have not yet been confirmed by the maintainer.

## System overview
gmlst is a Python 3.12 CLI that does bacterial MLST/cgMLST typing (scheme-based, scheme-free `tgmlst`, and `--guess` mixed-species). It downloads allele schemes from public providers into a local cache, then types assemblies and reads by calling external aligners (BLAST, minimap2, KMA, MMseqs2, MUMmer, Prodigal/pyrodigal, KMC). `gmlst visual` turns profile tables into MST, distance-matrix, heatmap, compare and locus-diff outputs. It also has a Flask + Vue/D3 single-page web app (`visual web`). The app binds to 127.0.0.1:8787 by default, but `docker-compose.yml` runs it with `--host 0.0.0.0` and publishes 8787.

Distribution: PyPI, bioconda recipe (`recipes/`, `conda/`), and a Docker Hub image `indexofire/gmlst` built by `.github/workflows/docker.yml`.

## Components
| Name | Code | Notes |
|---|---|---|
| CLI & Typing Pipeline | `gmlst/cli.py`, `gmlst/commands/` (except `config.py`, `scheme*`), `gmlst/core/`, `gmlst/calling/`, `gmlst/schemefree/`, `gmlst/novel/`, `gmlst/readers/`, `gmlst/fasta_io.py`, `gmlst/genbank_io.py`, `gmlst/metadata_io.py`, `gmlst/kmer_prefilter.py` | Parses user FASTA/FASTQ/GenBank/metadata and writes results and novel alleles |
| External Tools | `gmlst/aligners/`, `gmlst/gseek_engine.py`, `gmlst/utils.py` (`run_command`), `gmlst/core/gene_predictor.py` | Runs subprocesses with argument lists (no `shell=True` seen) |
| Scheme Providers & Download | `gmlst/database/providers/` (bigsdb, cgmlst, cgmlst_schemes, enterobase), `gmlst/database/download.py`, `gmlst/database/url_guard.py`, `gmlst/commands/scheme*.py`, `gmlst/data/` | HTTP(S) via requests/httpx/aria2c/curl/wget. Unpacks cgMLST.org zip files. SSRF guard on URLs |
| Local Cache & Config | `gmlst/database/cache.py`, `atomic.py`, `schema.py`, `scheme_prefs.py`, `gmlst/scheme_load_cache.py`, `gmlst/config_registry.py`, `gmlst/commands/config.py`, `gmlst/core_config.py` | Cache under `GMLST_CACHE_DIR`/XDG/conda prefix. `env.sh` holds API keys (chmod 0600) |
| Visual Web App | `gmlst/visual/app.py`, `api_routes.py`, `_api_helpers.py`, `gmlst/web/templates/` | Flask JSON API: `/api/mst`, `/api/distance-matrix`, `/api/locus-diff`, `/api/allele-heatmap`, `/api/compare-results`. Same-origin check, CSP, 64 MB cap |
| Web Frontend | `gmlst/web/frontend/src/` (Vue 3 + D3), built to `gmlst/web/static/visual/dist/` | Renders sample IDs and metadata from user tables. Session persistence and table export |
| Visual Exports | `gmlst/visual/cli.py`, `_cli_export.py`, `_cli_helpers.py`, `mst*.py` | Writes HTML/JSON/SVG/TSV exports from profile tables |
| Build & Release | `Dockerfile`, `docker-compose.yml`, `.github/workflows/`, `recipes/`, `conda/`, `scripts/` | Docker Hub push uses `DOCKERHUB_TOKEN`. Image runs as the non-root mamba user |

## Trust boundaries and entry points
1. **Local user to CLI:** command-line arguments and paths. The local user is trusted; the files they pass in may not be.
2. **Input data to parsers:** FASTA/FASTQ/GenBank, metadata TSV, profile/result tables, custom scheme directories (`scheme create`, `update-custom`). These may come from collaborators or public databases.
3. **Network to Scheme Providers:** responses from PubMLST/Pasteur BIGSdb (`rest.pubmlst.org`, Pasteur), cgMLST.org (zip archives), EnteroBase, and an optional private BIGSdb (`GMLST_PRIVATE_BIGSDB_URL`). URLs inside API responses are followed. `url_guard.py` blocks private IPs unless `GMLST_ALLOW_PRIVATE_URLS` is set. Accepted limitations it documents: external downloaders follow redirects without re-validation, and DNS-rebinding TOCTOU.
4. **Browser to Visual Web App:** any web page open in the user's browser can send requests to 127.0.0.1:8787 (CSRF, DNS rebinding). With the docker-compose setup, anyone on the network can reach it. There is no authentication.
5. **Web App to Frontend rendering:** data from user-supplied tables is rendered in the DOM (risk of XSS via sample IDs or metadata).
6. **CI to registries:** release workflows push to Docker Hub and PyPI.

## Assets
- Provider credentials: `GMLST_<PROVIDER>_API_KEY` (BIGSdb X-API-Key), EnteroBase token (Basic auth), stored in env.sh or the environment.
- Integrity of typing results and of the scheme cache. Results feed outbreak and public-health investigations, so a poisoned allele database silently corrupts calls.
- The host: code execution, and arbitrary file writes through extracted archives or output paths.
- Sample metadata loaded into the web app (may be sensitive epidemiological data).
- Release credentials (DOCKERHUB_TOKEN, PyPI publishing).

## Attacker profiles (assumed, not confirmed)
- A malicious or untrusted input file author: crafted FASTA headers, GenBank, metadata or profile tables, or custom scheme directories.
- A compromised or spoofed scheme provider, or a network MITM on the download path.
- A malicious website open in the user's browser while `visual web` runs.
- A network peer, when the web app is bound to 0.0.0.0 (docker-compose).
- Another local user on a shared HPC or workstation (temp dirs, cache permissions).

## Existing controls
- `url_guard.assert_public_url` on fetch/download chokepoints. The requests backend re-validates each redirect hop.
- cgMLST zip extraction uses `Path(member.filename).name` (basename only) and only `.fasta` members.
- Subprocesses run with argument lists.
- Web app: same-origin check on POST/PUT/DELETE/PATCH (Origin/Referer against the Host), loopback Host allowlist with only a warning otherwise, strict CSP (`script-src 'self'`), `X-Frame-Options: DENY`, nosniff, 64 MB body cap, `validate_tsv_scale`.
- `env.sh` is written with mode 0600. Atomic writes for cache files.
- The Docker image drops to a non-root user.

## Out of scope / accepted risk
- Recorded in `url_guard.py` by the maintainer: redirects followed by aria2c/curl/wget without re-validation, DNS-rebinding TOCTOU against the SSRF guard, and the opt-out via `GMLST_ALLOW_PRIVATE_URLS`.
- Nothing else confirmed by the user yet.

## Open questions (asked; unanswered)
- Is `visual web` only used on localhost, on a shared lab or Docker server, or on the internet?
- Are input files trusted (own lab) or untrusted (collaborators, public databases)?
- Out of scope: DoS from huge inputs? A compromised upstream provider? Other users on a shared machine?
- Which matters most: host compromise, result integrity, or credentials?

## Infrastructure
No separate infrastructure repository. Deployment is described by `Dockerfile`, `docker-compose.yml` and `.github/workflows/` in this repo.
