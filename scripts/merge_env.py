"""Merge conda environment YAML files with user pip overrides.

This script generates `.environment.yaml` from:

- `environment.yaml` (base)
- `environment.user.yaml` (optional user overlay)

Policy:
- `environment.user.yaml` may only contribute pip requirements.
- pip requirements are merged such that user entries override base entries when
  they resolve to the same distribution name.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_YAML_IMPORT_ERROR_MSG = (
    "ERROR: PyYAML is required to merge environment files.\n"
    "Install it with one of:\n"
    "  pip install pyyaml\n"
    "  conda install -c conda-forge pyyaml\n"
)

_DEPS_NOT_LIST_MSG = "ERROR: dependencies must be a YAML list."
_PIP_DEPS_NOT_LIST_MSG = "ERROR: dependencies.pip must be a YAML list."
_USER_NONPIP_MSG_PREFIX = (
    "ERROR: environment.user.yaml should only contain pip overrides.\n"
    "Found non-pip dependencies: "
)


try:
    import yaml  # type: ignore[import-not-found]
except Exception as exc:  # pragma: no cover
    raise SystemExit(_YAML_IMPORT_ERROR_MSG) from exc


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file that must be a mapping at the top level.

    Args:
        path: Path to the YAML file.

    Returns:
        Parsed YAML as a dictionary. Empty mapping if file is empty.

    Raises:
        SystemExit: If the top-level YAML object is not a mapping.

    """
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        msg = f"ERROR: {path} must be a YAML mapping at the top level."
        raise SystemExit(msg)
    return data


def split_deps(deps: object) -> tuple[list[object], list[str]]:
    """Split conda dependencies into non-pip entries and pip requirements.

    The conda environment `dependencies` field is a list with mixed entries:
    - strings (conda packages)
    - dicts like {"pip": [...]} (pip requirements)

    Args:
        deps: The raw `dependencies` value from YAML.

    Returns:
        (nonpip, pip_list) where:
          - nonpip contains all non-pip dependency entries
          - pip_list is the flattened list of pip requirement strings

    Raises:
        SystemExit: If the YAML structure is not as expected.

    """
    if deps is None:
        return [], []
    if not isinstance(deps, list):
        raise SystemExit(_DEPS_NOT_LIST_MSG)

    nonpip: list[object] = []
    pip_list: list[str] = []

    for item in deps:
        if isinstance(item, dict) and "pip" in item:
            pip_val = item.get("pip") or []
            if not isinstance(pip_val, list):
                raise SystemExit(_PIP_DEPS_NOT_LIST_MSG)
            pip_list.extend([str(x) for x in pip_val])
        else:
            nonpip.append(item)

    return nonpip, pip_list


def _normalize_name(name: str) -> str:
    """Normalize a distribution name for comparison.

    This is PEP 503-style normalization-ish:
    - lowercase
    - treat '-' and '_' as equivalent

    Args:
        name: Raw distribution name.

    Returns:
        Normalized name.

    """
    return name.strip().lower().replace("-", "_")


def dist_name(req: str) -> str | None:
    """Extract distribution name from a pip requirement string (best-effort).

    Supported patterns:
      - "name @ git+https://..."
      - "name==1.2", "name>=1", "name[extra]>=1"
      - "name" (bare)

    Returns:
        Normalized distribution name, or None if it cannot be determined
        (e.g., unnamed VCS URL like "git+https://...").

    """
    s = req.strip()

    # Named direct reference: "name @ url"
    if "@" in s:
        left, _right = s.split("@", 1)
        left = left.strip()
        if left and "://" not in left and not left.startswith("git+"):
            name = left.split("[", 1)[0].strip()
            if name:
                return _normalize_name(name)

    # Unnamed VCS URL: cannot reliably dedupe
    if s.startswith("git+"):
        return None

    # Requirement with version specifiers (take the head)
    seps = ["==", ">=", "<=", "~=", "!=", ">", "<", " "]
    head = s
    for sep in seps:
        if sep in s:
            head = s.split(sep, 1)[0].strip()
            break

    name = head.split("[", 1)[0].strip()
    if not name or "://" in name:
        return None
    return _normalize_name(name)


def merge_pip(base: list[str], user: list[str]) -> list[str]:
    """Merge pip requirements with user override precedence.

    User entries override base entries when both resolve to the same
    distribution name. Unnamed VCS URLs are appended and not deduplicated.

    Args:
        base: Base pip requirement strings.
        user: User pip requirement strings.

    Returns:
        Merged pip requirements list.

    """
    out: list[str] = []
    idx: dict[str, int] = {}

    for req in base:
        name = dist_name(req)
        if name is None:
            out.append(req)
            continue
        idx[name] = len(out)
        out.append(req)

    for req in user:
        name = dist_name(req)
        if name is None:
            out.append(req)
            continue
        if name in idx:
            out[idx[name]] = req
        else:
            idx[name] = len(out)
            out.append(req)

    return out


def main() -> None:
    """Entry point for merging environment.yaml and environment.user.yaml."""
    base_path = Path("environment.yaml")
    user_path = Path("environment.user.yaml")
    out_path = Path(".environment.yaml")

    base = load_yaml(base_path)

    if not user_path.exists():
        out_path.write_text(
            yaml.safe_dump(base, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
        return

    user = load_yaml(user_path)

    base_nonpip, base_pip = split_deps(base.get("dependencies"))
    user_nonpip, user_pip = split_deps(user.get("dependencies"))

    if user_nonpip:
        msg = f"{_USER_NONPIP_MSG_PREFIX}{user_nonpip!r}"
        raise SystemExit(msg)

    merged_pip = merge_pip(base_pip, user_pip)

    deps_out: list[object] = list(base_nonpip)
    if merged_pip:
        deps_out.append({"pip": merged_pip})

    base["dependencies"] = deps_out
    out_path.write_text(
        yaml.safe_dump(base, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
