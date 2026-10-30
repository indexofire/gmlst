# Error Messages and Exit Codes

Exit code semantics and fixes for common backend, provider, download, and flag errors.

## Error Messages

### What do exit codes mean?

| Code | Meaning |
| --- | --- |
| 0 | Success, including partial `tgmlst` failures without `--fail-on-error` |
| 1 | Runtime failure (also `scheme update` when any provider or scheme update fails) |
| 2 | Usage error: bad flags or arguments, or an invalid regex in `scheme list --name` |
| 3 | `tgmlst` input stage failure |
| 4 | `tgmlst` assembly stage failure |
| 5 | `tgmlst` prediction stage failure |
| 6 | `tgmlst` unknown stage failure |

The tgmlst stage codes start at 3 so they never collide with the shell-standard usage-error code 2. When several samples fail at different stages, the code reflects the dominant failed stage.

### `Unknown backend 'X'`

You requested a backend that is not registered in `gmlst/aligners/__init__.py`. Check supported backend names:

```bash
gmlst typing mlst --help
gmlst utils check -b blastn
```

### `Unknown provider 'X'`

The provider is not registered in `gmlst/database/providers/__init__.py`.

Check available providers with:

```bash
gmlst scheme list
```

### `No typing result produced for input sample`

This usually means the run failed before a valid typing result was assembled. Check input format, backend compatibility, scheme availability, and command output just before the failure.

### `Failed to download` errors

These usually point to network or provider-side issues. Retry with a different `--download-tool`, then verify the remote host is reachable.

### `--verbose and --quiet cannot be used together`

These flags are mutually exclusive. Pick one:

```bash
gmlst --verbose scheme list
gmlst --quiet scheme list
```

## Use exit codes in scripts

```bash
gmlst typing tgmlst sample.fna --fail-on-error
case $? in
  0) echo "ok" ;;
  2) echo "bad usage" ;;
  3|4|5|6) echo "tgmlst stage failure" ;;
  *) echo "runtime failure" ;;
esac
```

## Error-to-fix table

| Message | Fix |
| --- | --- |
| `Unknown backend 'X'` | `gmlst typing mlst --help`, then `gmlst utils check -b <name>` |
| `Unknown provider 'X'` | `gmlst scheme list`; check the `-p` spelling |
| `Scheme 'X' not found in catalog` | `gmlst scheme search <organism>` |
| `No typing result produced` | rerun with `--format json` and `--verbose` |
| `Failed to download` | retry with `--download-tool curl`, check proxy and rate limits |
| `--verbose and --quiet` | keep only one of the two flags |

When the same failure appears in a batch, run one sample alone with `--verbose`
so warnings are not interleaved.
