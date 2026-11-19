"""Code checks for the dcscope package"""
import ast
import pathlib

import dcscope


def test_no_absolute_imports_of_dcscope():
    """dcscope modules must import from dcscope with relative imports

    This also applies to the `*_ui.py` files, which are generated from
    the `.ui` files (use relative module names in the `<header>` of
    custom widgets).
    """
    pkg_dir = pathlib.Path(dcscope.__file__).parent
    found = []
    for path in sorted(pkg_dir.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            else:
                continue
            for name in names:
                if name == "dcscope" or name.startswith("dcscope."):
                    found.append(f"{path.relative_to(pkg_dir)}:{node.lineno}")
    assert not found, f"Absolute imports of dcscope in {found}"
