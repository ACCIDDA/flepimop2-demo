# Contributing to `flepimop2` Demo

This repository serves a dual purpose:

1. Demonstrating the abilities of the `flepimop2` framework.
2. Acting as an integration test to ensure documentation and examples remain current.

As elements of this repository become more fortified they should be migrated to the [`flepimop2` documentation site](https://accidda.github.io/flepimop2/) as standalone guides.

------------------------------------------------------------------------

## Prerequisites

* [`git`](https://git-scm.com/): Version control system for tracking changes to your project files and collaborating with others.
* [`conda`](https://anaconda.org/): Package and environment manager for creating isolated Python/R environments with all required dependencies.
* [`just`](https://just.systems/): Command runner for executing common project tasks like setting up environments, running tests, and building configs.
* [`air`](https://posit-dev.github.io/air/): R code formatter and linter for maintaining consistent R code style in postprocessing scripts. Unlike other linting tools used by this project template this tool cannot be managed via `conda`.

------------------------------------------------------------------------

## Using `just` for Development

This project uses `just` as a command runner to orchestrate common development tasks. The CI workflow defined in `.github/workflows/ci.yaml` runs the following checks:

1. Validates all YAML files in the project.
2. Checks R files are properly formatted with `air`.
3. Checks Python files are properly formatted and linted with `ruff`.

### Running CI Checks Locally

To run the same checks that CI runs:

```bash
just ci
```

This command executes:
- `just yamllint`: Lint YAML files.
- `just ci-air`: Check R file formatting.
- `just ci-ruff`: Check Python file formatting and linting.

### Fixing Formatting Issues

Before committing, you can automatically fix most formatting issues:

```bash
just air    # Format R files
just ruff   # Format and fix Python files
```

Or run all formatters at once (the default target):

```bash
just
```

### Other Useful Commands

```bash
just venv           # Create conda environment
just clean          # Remove generated files and environment
just --list         # Show all available commands
```

------------------------------------------------------------------------

## Integration Tests

This repository includes integration tests that extract code blocks from `README.md` and verify they execute successfully. This ensures the documentation remains accurate and up-to-date as the underlying `flepimop2` framework evolves.

### Running Integration Tests Locally

```bash
just integration-test
```

This executes `.github/scripts/test_readme_commands.py`, which:

- Parses `README.md` for code blocks.
- Executes each code block (unless marked with `<!-- skip-test -->`).
- Reports any failures.

### Automated Integration Testing

Integration tests run automatically via `.github/workflows/integration-test.yaml`:

- On every pull request to `main`.
- Weekly on Mondays at 9:15 AM UTC (which is either 4:15 or 5:15 AM ET).

This weekly schedule ensures breaking changes in dependencies or upstream packages are detected promptly. The workflow can also be triggered manually, primarily for debugging purposes.

------------------------------------------------------------------------

## Contributing to README.md

The `README.md` file serves as both user-facing documentation and executable test suite. When adding new sections, please follow these conventions:

### Style Guidelines

1. **Horizontal rules**: Use exactly 72 hyphens as section dividers:
   ```markdown
   ------------------------------------------------------------------------
   ```

2. **Heading hierarchy**: Use `##` for major sections. Keep headings concise and descriptive.

3. **Code blocks**: Include language identifiers for syntax highlighting:
   ````markdown
   ```python
   # Python code here
   ```

   ```bash
   # Shell commands here
   ```
   ````

4. **Testable commands**: By default, all bash/shell code blocks are executed during integration tests. To exclude a code block from testing, add `<!-- skip-test -->` before it:
   ````markdown
   <!-- skip-test -->
   ```bash
   just venv
   conda activate ./venv
   ```
   ````

5. **Documentation style**:
   - Use clear, concise language.
   - Explain *why* something works, not just *what* it does.
   - Include context about design decisions where relevant.
   - Use bullet points for lists (dash `-` character).

6. **Progressive complexity**: Structure sections to build understanding incrementally, starting from basic concepts and progressing to more advanced usage.

### Testing New Sections

After adding or modifying README content:

1. Run integration tests to verify code blocks execute correctly:
   ```bash
   just integration-test
   ```

2. Run formatting and linting checks:
   ```bash
   just ci
   ```

3. Review the rendered markdown to ensure formatting appears as intended.
