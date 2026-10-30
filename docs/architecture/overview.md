# Architecture Overview

Design goals, the system diagram, and the reasoning behind the main structural choices. Start here before the deeper module pages.

## Overview

`gmlst` is a layered Python CLI for MLST, cgMLST, wgMLST, and scheme-free typing. The project combines a stable command surface, backend-agnostic alignment and calling logic, cached scheme databases, and an optional visualization stack.

The main design goals are:

- keep the CLI thin and move decisions into reusable domain code
- support multiple alignment backends behind one normalized result model
- support multiple remote scheme providers behind one provider interface
- cache schemes and indexes so repeated runs work quickly and can run offline
- keep FASTA, FASTQ, and cgMLST-specific policy explicit in code, not hidden in backend implementations

## System architecture diagram

```text
                                +------------------+
                                |  User / Shell    |
                                +--------+---------+
                                         |
                                         v
                                +------------------+
                                | gmlst/cli.py     |
                                | Click entrypoint |
                                +--------+---------+
                                         |
              +--------------------------+---------------------------+
              |                          |                           |
              v                          v                           v
    +------------------+      +------------------+       +------------------+
    | commands/typing  |      | commands/scheme  |       | visual/cli.py    |
    | commands/utils   |      | catalog/cache UX |       | Flask / exports  |
    +--------+---------+      +--------+---------+       +--------+---------+
             |                         |                           |
             v                         v                           v
    +------------------+      +------------------+       +------------------+
    | core/ pipeline   |      | database/cache.py|       | visual/app.py    |
    | calling/         |      | providers/*      |       | visual/mst.py    |
    | novel/           |      | download.py      |       | web/* assets     |
    | schemefree/      |      +------------------+       +------------------+
    +--------+---------+
             |
             v
    +------------------+
    | aligners/*       |
    | readers/*        |
    | external tools   |
    +--------+---------+
             |
             v
    +------------------+
    | Output layer     |
    | TSV / JSON / UI  |
    +------------------+
```

## Key design decisions

### Why use `Protocol`

The aligner and provider systems both use `Protocol` instead of deep inheritance trees. This keeps integrations simple. New implementations only need to satisfy the interface shape, which reduces coupling between orchestration code and concrete backends.

### Why normalize backend output

Without `AlleleMatch` in `gmlst/aligners/base.py`, each downstream calling path would need backend-specific conditionals. Normalization keeps `gmlst/calling/` focused on allele semantics instead of parsing BLAST, KMA, minimap2, or nucmer output formats.

### Why keep FASTQ policy in the CLI layer

The FASTQ cgMLST KMA-first rule is not a generic backend property. It is a product-level policy choice. Keeping it in `gmlst/commands/typing.py` makes the behavior visible and easier to change without rewriting backend modules.

### Why cache catalogs and indexes

The provider list operation and backend indexing are both expensive relative to a normal command parse. Persisting catalogs and indexes reduces repeated network work and repeated index builds.

### Why use Click

Click gives the project consistent option parsing, grouped commands, shell-friendly help output, and straightforward composition across `typing`, `scheme`, `utils`, and `visual` command families.

## Reading guide

| Question | Page |
| --- | --- |
| What are the design goals? | this page |
| Where does a module or new file belong? | [Modules and layers](modules.md) |
| Which command owns a flag or a policy? | [CLI layer](cli.md) |
| How does a sample become a TSV row? | [Typing pipeline](typing-pipeline.md) |
| How do I add a new aligner? | [Alignment backends](backends.md) |
| How are schemes discovered and named? | [Database providers](providers.md) |
| Where is data cached, and how do offline runs work? | [Cache management](cache.md) |
| How do novel alleles and `tgmlst` work? | [Workflows](workflows.md) |
| How is the MST built and served? | [Visualization](visualization.md) |

## Tracing one command through the layers

`gmlst typing mlst -s saureus_1 sample.fna` touches each layer in turn:

| Step | Layer | Code path |
| --- | --- | --- |
| 1. parse `typing mlst -s ...` | CLI | `gmlst/cli.py` → `gmlst/commands/typing.py` |
| 2. resolve `saureus_1` (download if missing) | CLI + infrastructure | `gmlst/commands/typing_scheme.py` → `gmlst/database/cache.py` |
| 3. detect FASTA and plan indexes | infrastructure | `gmlst/readers/sample.py`, `gmlst/core/indexing.py` |
| 4. align alleles | infrastructure | `gmlst/aligners/blastn.py` (MLST default) |
| 5. turn hits into calls | domain | `gmlst/calling/allele.py` |
| 6. assign the ST | domain | `gmlst/calling/st_lookup.py` |
| 7. render TSV | presentation | `gmlst/commands/typing_output.py` |

No layer reaches upwards: `calling/` does not import Click, and `aligners/`
knows nothing about schemes or cache layout. Keeping that direction one-way is
what makes the CLI thin and the domain testable.

## Trade-offs at a glance

| Choice | Benefit | Cost |
| --- | --- | --- |
| `Protocol` interfaces | Backends and providers need no base class | Contracts are documented, not enforced at runtime |
| Normalized `AlleleMatch` | One calling path for every backend | Backend-specific evidence must be mapped explicitly |
| CLI-level FASTQ policy | Behaviour is visible and easy to change | Policy is not reusable outside the CLI |
| Cache-first catalogs and indexes | Fast repeats and offline runs | Invalidation is explicit (`--force-reindex`, `scheme update`) |
