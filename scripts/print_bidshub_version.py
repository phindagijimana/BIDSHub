#!/usr/bin/env python3
"""Print BIDSHub version from src/bidshub_version.py (for Docker, CI, shell)."""
import pathlib
import re
import sys

def main() -> None:
    root = pathlib.Path(__file__).resolve().parent.parent
    text = (root / "src" / "bidshub_version.py").read_text()
    m = re.search(
        r"""^__version__\s*=\s*["']([^"']+)["']""", text, re.M
    )
    if not m:
        print("0.0.0", file=sys.stderr)
        sys.exit(1)
    print(m.group(1))


if __name__ == "__main__":
    main()
