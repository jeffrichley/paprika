"""paprika_core — the deterministic half of the paprika plugin.

One installed package, reached only through the CLI — by a skill, by the session
hook and by pytest alike. Everything that must be identical every time lives
here; everything that needs cooking judgement lives in a skill on the far side
of the CLI.
"""

__version__ = "0.5.0"
