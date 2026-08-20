"""paprika_core — the deterministic half of the paprika plugin.

One installed package, imported identically by the CLI, the session hook and
pytest. Everything that must be identical every time lives here; everything that
needs cooking judgement lives in a skill on the far side of the CLI.
"""

__version__ = "0.1.0"
