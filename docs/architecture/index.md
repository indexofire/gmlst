# Architecture

How gmlst is layered, how a typing run moves through the system, and where
each responsibility lives in the repository.

<div class="grid cards" markdown>

-   **Architecture Overview**

    ---

    Design goals, the system diagram, and the key structural decisions.

    [Overview](overview.md)

-   **Modules and Layers**

    ---

    Source tree, the four layers, and placement and naming conventions.

    [Modules and layers](modules.md)

-   **CLI Layer**

    ---

    Click registration, `typing` dispatch, and command-level policy.

    [CLI layer](cli.md)

-   **Typing Pipeline**

    ---

    Scheme resolution, indexing, prefiltering, alignment, calling, ST lookup,
    and the FASTA/FASTQ split.

    [Typing pipeline](typing-pipeline.md)

-   **Alignment Backends**

    ---

    The `Aligner` protocol, `AlleleMatch` normalization, and the four
    backend adapters.

    [Backends](backends.md)

-   **Database Providers**

    ---

    The `Provider` protocol, runtime registry, and catalog naming rules.

    [Providers](providers.md)

-   **Cache Management**

    ---

    Cache layout, root resolution, index reuse, and offline operation.

    [Cache](cache.md)

-   **Novel and Scheme-free Workflows**

    ---

    Novel allele extraction, custom schemes, and the `tgmlst` engine.

    [Workflows](workflows.md)

-   **Visualization**

    ---

    Flask API, MST computation, and the Vue frontend.

    [Visualization](visualization.md)

</div>
