# Start Here

The first note to open, whether you arrived through Obsidian, an AI agent, or a terminal.

New machine? The README's Prerequisites section lists the small tool set you need first
(git, a bash shell, an AI coding agent, a GitHub account).

## First fifteen minutes

1. Read `README.md` for what this OS is and the folder map.
2. Take the example tour in the README: eight short files that show every entity type
   working together around a fictional candle studio.
3. Read `knowledge/ai-architecture/canon/doctrine-card.md`: the one-page projection of the
   whole architecture. Drill into `canon/core-doctrine.md` when you want the full why.
4. Run `bash _system/validate.sh`. It exits 0 with "All checks passed" on a fresh clone;
   keep it that way. It also prints a small set of known warnings on the shipped example
   content: those ship in the box and are not yours to fix. Errors are yours.
5. Read `docs/getting-started.md` and do the walkthrough: read canon, run a command,
   create a note, promote it.

## What this repo is for

Your business's brain: the knowledge, decisions, rules, and procedures your AI agents read
before acting, and the audit trail of what they did. You own every file. The agent vendors
are adapters, not owners.

## What to avoid

- Do not skip frontmatter when creating entities; the validator will tell you.
- Do not let an agent promote its own work to canon; promotion is yours.
- Do not store live numbers, live queues, or secret values here; pointers only.

## Where to go next

- Main browse note (Obsidian): `OBSIDIAN-DASHBOARD.md`
- The walkthrough: `docs/getting-started.md`
- Map your business onto the OS: `docs/onboard-business.md`
- The intake flow: `intake/README.md`
- The architecture: `knowledge/ai-architecture/INDEX.md`
- The OS as an OODA loop (start with the visual):
  `docs/ooda-infinite-brain-map.html`, then
  `knowledge/ai-architecture/synthesis/ooda-architecture-index.md`
- Namespace rules: `_system/namespaces/INDEX.md`

## This brain: ANAC legislation

This working copy is also a personal infinite brain for Brazilian civil aviation law.
Any file-reading AI should treat `knowledge/anac-legislacao/` as the domain namespace.

To answer a legal question: read `knowledge/anac-legislacao/INDEX.md`, then
`support/indexes/keyword-index.yml`, then only the listed fragment YAML files.

To refresh the corpus: `python3 tools/anac_ingest/ingest.py`

Coverage after the 2026-09-14 ingest (Arquivo.pt only): 45 RBAC and 8 IS with
text, 0 IAC, 10177 unique fragments. Gaps live in
`knowledge/anac-legislacao/synthesis/lacunas-de-cobertura.md`.
