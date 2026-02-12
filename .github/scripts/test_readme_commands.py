# ruff: noqa: T201
"""Integration test for bash/shell code blocks from README.md.

Code blocks preceded by <!-- skip-test --> will be skipped. Exit code 0
indicates all tests passed.

"""

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple


class CodeBlock(NamedTuple):
    """Class representing a code block extracted from README.md.

    Attributes:
        code: The content of the code block.
        line: The line number where the code block starts.
        skip: Whether this block should be skipped.

    """

    code: str
    line: int
    skip: bool


def extract_code_blocks(readme_lines: list[str]) -> list[CodeBlock]:
    """Extract bash/shell code blocks from README.md.

    Args:
        readme_lines: List of lines from README.md.

    Returns:
        List of code blocks with their content, starting line number, and skip status.

    """
    code_blocks = []
    in_code_block = False
    current_block = []
    block_start_line = 0
    skip_next = False

    for i, line in enumerate(readme_lines, start=1):
        # Check for skip marker
        if line.strip() == "<!-- skip-test -->":
            skip_next = True
            continue

        # Check for code block start
        if re.match(r"^```(bash|shell)\s*$", line):
            in_code_block = True
            block_start_line = i + 1
            current_block = []
            continue

        # Check for code block end
        if in_code_block and line.startswith("```"):
            code_blocks.append(
                CodeBlock(
                    code="".join(current_block), line=block_start_line, skip=skip_next
                )
            )
            in_code_block = False
            skip_next = False
            continue

        # Collect code block content
        if in_code_block:
            current_block.append(line + "\n")

    return code_blocks


def execute_code_block(
    code: str, block_num: int, line_num: int, *, dry_run: bool = False
) -> bool:
    """Execute a code block using bash.

    Args:
        code: The code to execute.
        block_num: The block number for display purposes.
        line_num: The line number where the block starts.
        dry_run: If True, only print the code without executing.

    Returns:
        True if execution succeeded (exit code 0), False otherwise.
        In dry-run mode, always returns True.

    """
    print(f"> Executing code block #{block_num} (line {line_num}):")
    # Print each line of code with $ prefix
    for line in code.strip().split("\n"):
        print(f"$ {line}")

    # In dry-run mode, just print and return
    if dry_run:
        print(f"> Code block #{block_num} (dry-run)")
        return True

    try:
        # S603, S607: Executing bash with user-provided code is intentional
        result = subprocess.run(  # noqa: S603
            ["bash", "-c", code],  # noqa: S607
            check=False,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
    except subprocess.TimeoutExpired:
        print(f"> Code block #{block_num} timed out after 5 minutes")
        return False
    except OSError as e:
        print(f"> Code block #{block_num} failed with exception: {e}")
        return False

    # Only show STDOUT if non-empty
    if result.stdout:
        print("STDOUT:")
        for line in result.stdout.splitlines():
            print(f"  {line}")

    # Only show STDERR if non-empty
    if result.stderr:
        print("STDERR:")
        for line in result.stderr.splitlines():
            print(f"  {line}")

    if result.returncode == 0:
        print(f"> Code block #{block_num} passed")
    else:
        print(f"> Code block #{block_num} failed with exit code {result.returncode}")

    return result.returncode == 0


def execute_all_blocks(
    code_blocks: list[CodeBlock], *, dry_run: bool = False
) -> list[bool]:
    """Execute all non-skipped code blocks and return results.

    Args:
        code_blocks: List of code blocks to execute.
        dry_run: If True, only print code without executing.

    Returns:
        List of boolean results for each executed block.

    """
    results = []

    # Print opening separator
    print(f"{'=' * 70}")

    for i, block in enumerate(code_blocks, start=1):
        if block.skip:
            continue

        success = execute_code_block(block.code, i, block.line, dry_run=dry_run)
        results.append(success)

        # Print separator after each block
        print(f"{'=' * 70}")

    return results


def print_execution_summary(code_blocks: list[CodeBlock], results: list[bool]) -> None:
    """Print execution summary with pass/fail counts."""
    total_blocks = len(code_blocks)
    skipped_blocks = sum(1 for block in code_blocks if block.skip)
    executed_count = len(results)

    print(f"""Total blocks found: {total_blocks}
Blocks executed: {executed_count}
Blocks skipped: {skipped_blocks}
Passed: {sum(results)}/{executed_count}
Failed: {executed_count - sum(results)}/{executed_count}""")


def main() -> None:
    """Execute code blocks from README.md."""
    parser = argparse.ArgumentParser(
        description="Extract and execute bash/shell code blocks from README.md"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract and display code blocks without executing them",
    )
    args = parser.parse_args()

    # Find README.md (assume script is in .github/scripts/)
    readme_path = Path(__file__).parent.parent.parent / "README.md"
    if not readme_path.exists():
        print(f"Error: README.md not found at {readme_path}")
        sys.exit(1)

    print(f"Extracting code blocks from {readme_path}")
    readme_lines = readme_path.read_text().splitlines()
    code_blocks = extract_code_blocks(readme_lines)

    total_blocks = len(code_blocks)
    skipped_blocks = sum(1 for block in code_blocks if block.skip)
    executable_blocks = total_blocks - skipped_blocks

    print(f"""Found {total_blocks} code blocks:
  - {executable_blocks} will be executed
  - {skipped_blocks} will be skipped""")

    # List skipped blocks
    if skipped_blocks > 0:
        print("Skipped blocks:")
        for i, block in enumerate(code_blocks, start=1):
            if block.skip:
                print(f"  - Block #{i} (line {block.line})")

    # Execute non-skipped blocks (or dry-run)
    results = execute_all_blocks(code_blocks, dry_run=args.dry_run)

    # Summary
    print_execution_summary(code_blocks, results)

    # Exit with appropriate code
    if all(results):
        print("All tests passed!")
        sys.exit(0)

    print("Some tests failed!")
    sys.exit(1)


if __name__ == "__main__":
    main()
