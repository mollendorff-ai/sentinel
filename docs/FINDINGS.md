# Findings for Forge and Ref

What Sentinel, as a program, found hard about Forge and Ref while it was rebuilt as Forge's demo (ADR-012). Each is reported to that project as a roadmap item or a pull request; this file keeps only those not yet reported.

**Nothing is waiting to be reported (2026-11-15).** What was here went to:

- **Forge, roadmap item T1-PIPELINE-FINDINGS**, fixed on Forge's `main` in pull request #238 after v10.0.0-rc.26: `docs/MCP.md` no longer says a Monte Carlo section needs `enabled: true` or that `forge_functions` lists 173 functions, and a tornado input that cannot move the output now carries a note. Sentinel pins rc.26, so the note reaches a run with the next pin. That `forge validate` on a model never calculated reports a match with nothing to compare was already Forge's T1-AGENT-FRICTION.
- **Ref, pull request #43**: a way to set the user agent, without which SEC EDGAR refuses Ref's requests (HTTP 403). Until it ships, an input is downloaded with `curl` (ADR-012, addendum).
