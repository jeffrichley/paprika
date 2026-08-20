#!/usr/bin/env bash
# Inject the paprika primer at the start of a session.
#
# Exits zero no matter what. A hook that can fail a session is a hook that will
# eventually take the whole of Claude Code down with it, and nothing this plugin
# does is worth that.
#
# It calls the installed command rather than running Python of its own. That is
# the fix for #78: this plugin's dependencies live in the environment `uv tool
# install` built, and any other interpreter — a system python3 above all — can
# see the source without being able to import it. The failure was silent, which
# is why "not installed" now has words of its own below.
set +e
root="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# A checkout's own environment first, so a developer sees their uncommitted work
# rather than whatever they last installed.
if [ -x "$root/.venv/bin/paprika" ]; then
  command="$root/.venv/bin/paprika"
elif command -v paprika >/dev/null 2>&1; then
  command="paprika"
else
  # `printf` is a builtin. Reaching for `cat` here would mean the branch that
  # handles "nothing is installed" itself depended on something being installed.
  printf '%s\n' \
    '<EXTREMELY_IMPORTANT>' \
    'The `paprika` command is not on PATH, so nothing in this plugin can run and' \
    'no recipe, plan, shopping list or pantry can be reached this session.' \
    '' \
    'If she asks for any of it, say so plainly, once, and name the step that' \
    'fixes it — installing `uv` first if she has not got it:' \
    '' \
    '    uv tool install git+https://github.com/jeffrichley/paprika' \
    '' \
    'Then a new session. Do not try to reach her recipes any other way, and do' \
    'not run the install on her behalf without asking.' \
    '</EXTREMELY_IMPORTANT>'
  exit 0
fi

"$command" primer --root "$root" 2>/dev/null
exit 0
