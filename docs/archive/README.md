# Historical documentation archive

Normative documentation for Colosseum is:

- [docs/scope.md](../scope.md) — implemented behavior and deferred items
- [docs/sphinx/source/guides/](../sphinx/source/guides/) — user guides (built by
  docgen)
- Runtime code, tests, and docs (`python scripts/docgen/build_all.py`)

Early planning documents (ADRs, FFOs, DDDs) were removed from the tracked tree
to reduce
feature-creep and doc drift. Recover them from git history when needed, for
example:

```bash
git log --oneline -- docs/archive/planning/
git show <commit>:docs/archive/planning/design/ddd-equipment-vsg-speca.md
```
