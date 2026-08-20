"""Print the session primer. Never fails, whatever it finds.

Deliberately thin: everything worth testing lives in ``paprika_core.primer``,
which pytest can reach. This file exists to be the thing a hook can invoke.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    """Print the primer, or nothing at all.

    Returns:
        int: Always zero. A hook that can fail a session is a hook that will
            eventually take Claude Code down with it, and this plugin is not
            worth that.
    """
    try:
        root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(root / "src"))
        from paprika_core.primer import build

        sys.stdout.write(build(root))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
