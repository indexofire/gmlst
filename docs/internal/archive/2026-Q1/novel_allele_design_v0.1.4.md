---
status: archived
archived_date: 2026-04-08
archived_from: docs/internal/design/
archive_reason: "Design implemented in v0.1.4 release"
related_release: v0.1.4
---

# v0.1.4 Novel Allele Detection & Custom Scheme Design

## Overview

Enable detection and management of novel alleles and ST profiles for private/laboratory MLST databases.

## Feature Scope

1. **Typing Enhancement** (`gmlst typing`)
   - `--novel-allele`: Save novel allele sequences to `{locus}_novel.fasta`
   - `--novel-profile`: Save novel ST profiles to `profiles_novel.txt`

2. **Scheme Management** (`gmlst scheme`)
   - `create`: Merge public scheme with novel data to create custom scheme
   - `update`: Add more novel data to existing custom scheme
   - `export --format grapetree`: Convert for GrapeTree visualization

---

## Data Formats

### 1. Novel Allele FASTA Format

**Filename:** `{locus}_novel.fasta`

**Format:**
```fasta
>{locu s}_n{number} sample={sample_name}
{sequence}
```

**Examples:**
```fasta
>dnaN_n1 sample=isolate_A1
ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG
>dnaN_n2 sample=isolate_B2
ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG
```

**Rules:**
- One file per locus
- Numbering: n1, n2, n3... (per-locus sequential)
- Header format: `\u003e{locus}_n{num} sample={name}`
- Multiple samples can share same sequence (deduplicated)

### 2. Novel Profile TSV Format

**Filename:** `profiles_novel.txt`

**Format:**
```tsv
ST\tsample\t<locus1>\t<locus2>\t...
```

**Examples:**
```tsv
ST\tsample\tdnaN\tgyrB\tabcZ\t...\n
N1\tisolate_A1\tn1\t5\t12\t...
N2\tisolate_B2\tn2\t5\t12\t...
```

**Rules:**
- ST numbering: N1, N2, N3... (global sequential)
- Only complete profiles (all loci resolved)
- Known alleles: numbers; Novel alleles: nX format

### 3. Custom Scheme Directory Structure

```
~/.cache/gmlst/local/custom_1/
├── dnaN.tfa              # Merged: original + n1, n2...
├── gyrB.tfa              # Merged: original + novel
├── ...
├── profiles.txt          # Merged: original STs + N1, N2...
└── .meta.json            # Metadata
```

**.meta.json:**
```json
{
  "scheme_name": "custom_1",
  "provider": "local",
  "based_on": "saureus_1",
  "based_on_provider": "pubmlst",
  "scheme_type": "mlst",
  "description": "Lab collection 2024",
  "created_at": "2024-03-18T10:30:00Z",
  "loci": ["dnaN", "gyrB", "abcZ", ...],
  "novel_alleles": {
    "dnaN": ["n1", "n2"],
    "gyrB": ["n1"]
  },
  "novel_profiles": ["N1", "N2"],
  "last_allele_number": {"dnaN": 2, "gyrB": 1}
}
```

---

## Command Specifications

### 1. `gmlst typing --novel-allele`

**Usage:**
```bash
gmlst typing -s saureus_1 --novel-allele sample.fasta
gmlst typing -s saureus_1 --novel-allele --data-dir novel_data/ *.fasta
```

**Output Files:**
- `dnaN_novel.fasta` - Novel sequences for dnaN locus
- `gyrB_novel.fasta` - Novel sequences for gyrB locus
- ...

**Implementation Logic:**
1. Run normal typing pipeline
2. For each locus call with `call_type="novel"`:
   - Extract novel sequence from alignment
   - Check if sequence already exists (deduplication)
   - Assign next available nX number
   - Append to `{locus}_novel.fasta`
3. If `--data-dir` specified, create directory and write files there

**Novel Sequence Extraction:**
- From `AlignmentResult`, extract query/subject sequence
- Store in `LocusCall.novel_sequence`
- Use sequence hash for deduplication

### 2. `gmlst typing --novel-profile`

**Usage:**
```bash
gmlst typing -s saureus_1 --novel-profile sample.fasta
gmlst typing -s saureus_1 --novel-allele --novel-profile *.fasta
```

**Output File:**
- `profiles_novel.txt` - TSV with novel ST profiles

**Implementation Logic:**
1. Must be used with `--novel-allele` (prerequisite)
2. After novel allele assignment, collect complete profiles:
   - All loci have either: known number OR novel nX
   - No missing or partial loci
3. Assign ST numbers (N1, N2...):
   - Sort by locus combination
   - Assign sequential N numbers
   - Deduplicate identical profiles
4. Write to `profiles_novel.txt`

### 3. `gmlst scheme create`

**Usage:**
```bash
gmlst scheme create \
  -t mlst \
  -s saureus_1 \
  --data-dir new-data/ \
  --desc "Lab collection"
```

**Parameters:**
- `-t, --type`: Scheme type (mlst/cgmlst/wgmlst) - only mlst supported initially
- `-s, --source`: Source scheme to extend (e.g., saureus_1)
- `--data-dir`: Directory containing `*_novel.fasta` and `profiles_novel.txt`
- `--desc`: Human-readable description

**Auto-Numbering:**
- Reads `~/.cache/gmlst/_catalog/local.json`
- Finds highest custom_X number
- Assigns next number (custom_1, custom_2...)

**Implementation Logic:**
1. Validate source scheme exists and is cached
2. Load all `*_novel.fasta` files from data directory
3. Parse `profiles_novel.txt`
4. Create new scheme directory:
   - Copy original allele files
   - Append novel alleles to each locus file
   - Merge profiles (original + novel)
   - Write .meta.json
5. Update local catalog

### 4. `gmlst scheme update-custom` (for custom schemes)

**Usage:**
```bash
gmlst scheme update-custom -s custom_1 --data-dir more-data/
```

**Limitation:** Only works with `provider=local`

**Implementation:**
1. Load existing custom scheme metadata
2. Get last used allele numbers from .meta.json
3. Continue numbering from where it left off
4. Merge new novel data

### 5. `gmlst scheme export --format grapetree`

**Usage:**
```bash
gmlst scheme export -s custom_1 --format grapetree -o custom_1_grapetree.tsv
```

**Conversion Logic:**
- nX alleles → large numbers (1000001, 1000002...)
- N1 profiles → ST numbers (1000001, 1000002...)
- Original alleles stay as-is

---

## Data Flow Diagram

```
Step 1: Typing with Novel Detection
===================================
Input: sample.fasta + public_scheme
  |
  v
Typing Pipeline
  |
  +-- Known alleles --> Normal ST lookup
  |
  +-- Novel alleles --> Extract sequence
          |
          v
    dnaN_novel.fasta (n1, n2...)
    gyrB_novel.fasta (n1...)
    profiles_novel.txt (N1, N2...)


Step 2: Create Custom Scheme
============================
Input: public_scheme + novel_data/
  |
  v
Merge
  |
  +-- Original alleles (dnaN_1, dnaN_2...)
  +-- Novel alleles    (dnaN_n1, dnaN_n2...)
  |
  v
Custom scheme: custom_1
(.tfa files, profiles.txt, .meta.json)


Step 3: Use Custom Scheme
=========================
Input: new_sample.fasta + custom_1
  |
  v
Typing
  |
  +-- Matches custom_1 alleles (original + novel)
  +-- Can identify: "This is ST=N1" or "This matches n1 allele"
```

---

## Implementation Phases

### Phase 1: Novel Allele Detection (`--novel-allele`)
- [ ] Add `novel_sequence` field to `LocusCall`
- [ ] Extract sequence from alignment for novel hits
- [ ] Implement `NovelAlleleWriter` class
- [ ] Add CLI flag and integrate

### Phase 2: Novel Profile Generation (`--novel-profile`)
- [ ] Profile collection logic
- [ ] ST numbering (N1, N2...)
- [ ] TSV output writer
- [ ] CLI flag and integration

### Phase 3: Custom Scheme Creation (`scheme create`)
- [ ] Local catalog management (`_catalog/local.json`)
- [ ] Scheme merging logic
- [ ] Auto-numbering (custom_1, custom_2...)
- [ ] CLI command

### Phase 4: Custom Scheme Updates (`scheme update`)
- [ ] Incremental novel data addition
- [ ] Continuation of numbering

### Phase 5: Export for GrapeTree
- [ ] Number conversion logic
- [ ] TSV export

---

## Testing Strategy

See: `test/test_novel_allele.py`

**Key Test Cases:**
1. Novel allele extraction and formatting
2. Sequential numbering (n1, n2, n3)
3. Deduplication (same sequence from different samples)
4. Complete profile detection (all loci resolved)
5. ST numbering (N1, N2)
6. Scheme creation and merging
7. Auto-numbering for custom schemes

---

## Open Questions

1. **Sequence Identity:** What defines a "novel" allele?
   - Current: `call_type="novel"` from aligner
   - Should we add sequence similarity clustering?

2. **Profile Completeness:** Strict or lenient?
   - Current plan: Strict (all loci must be resolved)
   - Alternative: Allow partial with "N1_partial" flag

3. **GrapeTree Large Numbers:**
   - Start from 1000000?
   - Ensure no collision with public ST numbers (max ~10000)

---

## Files to Modify

**New Files:**
- `gmlst/novel/writer.py` - Novel allele and profile writing
- `gmlst/novel/reader.py` - Parse novel data for scheme creation
- `test/test_novel_allele.py` - Test cases

**Modified Files:**
- `gmlst/calling/allele.py` - Add novel_sequence field
- `gmlst/calling/st_lookup.py` - Profile generation
- `gmlst/commands/typing.py` - Add --novel-* flags
- `gmlst/commands/scheme.py` - Add create/update for custom
- `gmlst/database/cache.py` - Local catalog management
- `gmlst/database/schema.py` - Scheme merging
