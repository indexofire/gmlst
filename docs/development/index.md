# Development

Set up the toolchain, follow the workflow, and extend gmlst without fighting
the existing architecture.

<div class="grid cards" markdown>

-   **Development Setup**

    ---

    Pixi environment, verification commands, and the project map.

    [Setup](setup.md)

-   **Workflow**

    ---

    Branching, the edit loop, lint, tests, and commit conventions.

    [Workflow](workflow.md)

-   **Code Style**

    ---

    Formatting, imports, naming, typing, errors, and Click patterns.

    [Code style](code-style.md)

-   **Extending gmlst**

    ---

    Add an alignment backend, a data provider, or a CLI command.

    [Extending](extending.md)

-   **Testing**

    ---

    Run the suite, write focused tests, and cover regressions.

    [Testing](testing.md)

-   **Documentation**

    ---

    Where docs live, the bilingual convention, and index rules.

    [Documentation](docs.md)

-   **Frontend**

    ---

    Flask/Vue split and the visualization build commands.

    [Frontend](frontend.md)

-   **Pull Requests**

    ---

    What reviewers look for and the checks to run first.

    [Pull requests](pull-requests.md)

-   **Release Process**

    ---

    Version locations, tagging, and publishing.

    [Release](release.md)

</div>

## Getting help

If you are unsure where a change belongs, inspect the nearest existing module first and follow that pattern. For public-facing behaviour, update docs and tests in the same pull request so the repository stays coherent.

Useful entry points:

| Question | Start here |
| --- | --- |
| Where does this code belong? | [Setup](setup.md), [Code style](code-style.md) |
| How do I add a backend/provider/command? | [Extending](extending.md) |
| What should I test? | [Testing](testing.md) |
| How do I write docs? | [Documentation](docs.md) |
| What do reviewers expect? | [Pull requests](pull-requests.md) |
