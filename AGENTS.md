# Forge Studio development instructions

Before planning, editing, or testing Forge Studio, read [docs/FORGE_ANA_GELISTIRME_LISTESI.md](docs/FORGE_ANA_GELISTIRME_LISTESI.md) in this branch and follow its current active stage, acceptance criteria and evidence requirements.

- Only work on the first unfinished stage. Do not start the next stage until all required functional, regression and visual checks pass and the current stage is recorded as complete. If blocked, document the blocker and try alternatives within the same stage. Only the user's explicit instruction may change the order/scope.
- Forge is a general-purpose true 3D and semantic part generation studio, not a fixed humanoid or fantasy-character template generator. Keep working code intact; no fake output.
- /GÖRSEL-DENETİM is mandatory for every significant update: inspect actual outputs and save evidence. Do not claim untested work is complete.
- Record changes, tests, visuals, commit links, blockers and current stage in the canonical roadmap after each work session.
- Do not touch Arena Forge Pro or Kırık Mühür. Do not initiate paid services without approval or expose secrets.

User-authorized temporary parallel work (2026-11-28): F02 only in forge-f02-segmentation-lab while Claude works on F01 separately. F01 remains open; do not merge into F01 or main, do not touch existing generation code, do not start F03. Use independent modules and stable input GLB contract; integration requires user-supplied F01 ZIP and regression checks. Canonical F02 lab status: docs/F02_PARALLEL_LAB.md.
