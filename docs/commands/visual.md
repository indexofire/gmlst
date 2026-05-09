[← Command Reference](../commands.md)

# gmlst visual

Launch local visualization tools for profile-table MST exploration.

## web

Start the Flask and Vue web app for local MST visualization.

### Usage
```bash
gmlst visual web [OPTIONS]
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `--host TEXT` | Host address to bind. | `127.0.0.1` |
| `--port INTEGER` | TCP port to bind. | `8787` |
| `--open-browser` | Open the default browser after startup. | `False` |
| `-h, --help` | Show the help message and exit. | - |

### Examples
```bash
gmlst visual web --open-browser
gmlst visual web --port 9000
gmlst visual web --host 0.0.0.0 --port 8787
```

### Notes
- The server runs locally with a Flask backend and a Vue frontend built with Vite.
- The UI builds an MST from profile distances, using per-locus allele differences between samples.
- Missing-token penalties can be toggled for tokens such as `LNF`, `NIPH`, and `NIPHEM`, which changes how incomplete or special-status loci contribute to distance.
- Two layouts are available in the UI: `tree` and `radial`.
- Nodes can be colored by metadata columns from the uploaded table.
- The UI supports SVG export for the rendered graph.
- Input can be pasted or uploaded in native `gmlst` table form or in GrapeTree-compatible form with `#Strain` as the first column.
