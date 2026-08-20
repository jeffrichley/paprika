#!/usr/bin/env bash
# Inject the paprika primer at the start of a session.
#
# Exits zero no matter what. A hook that can fail a session is a hook that will
# eventually take the whole of Claude Code down with it, and nothing this plugin
# does is worth that.
set +e
root="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# The plugin's own interpreter first: it is the one that has the package
# installed. A bare python3 is the fallback, and finding neither is silence
# rather than an error.
for candidate in "$root/.venv/bin/python" "$(command -v python3)"; do
  if [ -x "$candidate" ]; then
    "$candidate" "$root/hooks/session_start.py" 2>/dev/null
    break
  fi
done
exit 0
