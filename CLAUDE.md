# paprika

A Claude Code plugin.

## Agent skills

### Issue tracker

Issues live as GitHub issues in `jeffrichley/paprika`, managed with the `gh` CLI.
See `docs/agents/issue-tracker.md`.

Renovate (the central run in `jeffrichley/runners`) merges its own grouped
non-major pull request once CI is green; majors and vulnerability fixes wait for Jeff.

### Triage labels

The five canonical triage roles, using their default label strings.
See `docs/agents/triage-labels.md`.

### Writing a skill

Read `superpowers:writing-skills` first, then the local supplement.
See `docs/agents/skill-writing.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root (created lazily).
See `docs/agents/domain.md`.
