from __future__ import annotations

from pathlib import Path

try:
    import yaml  # type: ignore
except Exception as e:
    raise SystemExit(
        "ERROR: PyYAML is required to merge environment files.\n"
        "Install it with one of:\n"
        "  pip install pyyaml\n"
        "  conda install -c conda-forge pyyaml\n"
    ) from e


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text())
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise SystemExit(f"ERROR: {path} must be a YAML mapping at the top level.")
    return data


def split_deps(deps: object) -> tuple[list[object], list[str]]:
    if deps is None:
        return [], []
    if not isinstance(deps, list):
        raise SystemExit("ERROR: dependencies must be a YAML list.")

    nonpip: list[object] = []
    pip_list: list[str] = []

    for item in deps:
        if isinstance(item, dict) and "pip" in item:
            pip_val = item.get("pip") or []
            if not isinstance(pip_val, list):
                raise SystemExit("ERROR: dependencies.pip must be a YAML list.")
            pip_list.extend([str(x) for x in pip_val])
        else:
            nonpip.append(item)

    return nonpip, pip_list


def _normalize_name(name: str) -> str:
    # PEP 503 normalization-ish: treat hyphen/underscore as equivalent.
    return name.strip().lower().replace("-", "_")


def dist_name(req: str) -> str | None:
    """
    Best-effort extraction of distribution name from a pip requirement string.

    Supports:
      - 'name @ git+https://...'
      - 'name==1.2', 'name>=1', 'name[extra]>=1'
      - 'name' (bare)
    Returns None for unnamed VCS URLs like 'git+https://...'.
    """
    s = req.strip()

    # Named direct reference: "name @ url"
    if "@" in s:
        left, _right = s.split("@", 1)
        left = left.strip()
        if left and "://" not in left and not left.startswith("git+"):
            # strip extras: name[extra]
            name = left.split("[", 1)[0].strip()
            if name:
                return _normalize_name(name)

    # Unnamed VCS URL: cannot reliably dedupe
    if s.startswith("git+"):
        return None

    # Requirement with version specifiers (take the head)
    # e.g. "foo>=1", "foo == 1", "foo[bar]~=2"
    seps = ["==", ">=", "<=", "~=", "!=", ">", "<", " "]
    head = s
    for sep in seps:
        if sep in s:
            head = s.split(sep, 1)[0].strip()
            break

    # Strip extras: foo[extra]
    name = head.split("[", 1)[0].strip()
    if not name or "://" in name:
        return None
    return _normalize_name(name)


def merge_pip(base: list[str], user: list[str]) -> list[str]:
    """
    Merge pip requirement lists where user entries override base entries
    when they resolve to the same distribution name.
    """
    out: list[str] = []
    idx: dict[str, int] = {}

    # Add base first, recording positions for named requirements.
    for r in base:
        name = dist_name(r)
        if name is None:
            out.append(r)
            continue
        idx[name] = len(out)
        out.append(r)

    # Apply user overrides (replace if same name, else append).
    for r in user:
        name = dist_name(r)
        if name is None:
            out.append(r)
            continue
        if name in idx:
            out[idx[name]] = r
        else:
            idx[name] = len(out)
            out.append(r)

    return out


def main() -> None:
    base_path = Path("environment.yaml")
    user_path = Path("environment.user.yaml")
    out_path = Path(".environment.yaml")

    base = load_yaml(base_path)

    # If there is no user override file, just copy base through.
    if not user_path.exists():
        out_path.write_text(
            yaml.safe_dump(base, sort_keys=False, default_flow_style=False)
        )
        return

    user = load_yaml(user_path)

    base_nonpip, base_pip = split_deps(base.get("dependencies"))
    user_nonpip, user_pip = split_deps(user.get("dependencies"))

    # Policy: user file is an overlay for pip only.
    if user_nonpip:
        raise SystemExit(
            "ERROR: environment.user.yaml should only contain pip overrides.\n"
            f"Found non-pip dependencies: {user_nonpip!r}"
        )

    merged_pip = merge_pip(base_pip, user_pip)

    deps_out: list[object] = list(base_nonpip)
    if merged_pip:
        deps_out.append({"pip": merged_pip})

    base["dependencies"] = deps_out
    out_path.write_text(yaml.safe_dump(base, sort_keys=False, default_flow_style=False))


if __name__ == "__main__":
    main()
