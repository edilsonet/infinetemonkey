---
id: "skill-context-budget"
aliases: ["skill-context-budget", "context-budget"]
type: "Skill"
namespace: "ai-architecture"
lifecycle_state: "research"
summary: "Audit what this repo's entities and adapters cost in session context, and find reducible bloat."
confidence: 0.8
retrieval_class: "domain"
export_class: "internal"
description: "Use this skill when session context feels loaded, when adding entities, or when deciding whether a new skill or agent earns its permanent place."
edges:
  - target: "[[tool-three-layer-standard]]"
    relation: "related_to"
    confidence: 0.8
verified_by: "operator-pending"
created: "2026-09-30"
---

# context-budget

This repo mirrors every entity into every session. `sync-adapters.sh` copies
`entities/{commands,agents,skills,rules}` into `.claude/` and `.codex/`, and agent and
skill descriptions load into context at session start whether or not the skill is used.
Nobody has measured what that costs. Adapted from `skills/context-budget` in
affaan-m/ECC (MIT).

## Use when

- Adding a skill or agent and deciding whether it earns a permanent slot.
- Session start feels heavier than it should, or output quality degrades in long sessions.
- Before adopting a third-party plugin wholesale.

## Do not use when

- A single entity is unusually large and you already know which one. Read it.

## The audit

```bash
# What loads at session start, and how big each file is.
wc -c entities/agents/*.md entities/skills/*.md entities/commands/*.md | sort -n | tail -20

# Description length is what actually costs, since only the frontmatter
# description is needed to decide whether to load the body.
awk '/^description:/{print length($0), FILENAME}' entities/skills/*.md entities/agents/*.md | sort -rn | head -15

# Duplicate copies across the adapter mirrors.
ls .claude/skills/ .codex/skills/ | sort | uniq -d
```

## What to look for

1. **Description bloat.** A 400-character description for a skill nobody invokes spends
   context on every session. The trigger sentence should be one clause.
2. **Overlap.** Two entities that do the same job both cost, and confuse routing. This
   repo already rejected `knowledge-ops` and `contract-first` from ECC for exactly this.
3. **Stale mirrors.** `.claude/` and `.codex/` copies that no longer match `entities/`
   still consume context. `adapter-sync-check.sh` reports drift.
4. **Scope mismatch.** A skill written for application code in a knowledge brain is pure
   overhead. ECC ships 22 language rule directories and this repo has no application
   source.

## The threshold

Before adding a permanent entity, ask whether it changes a decision a future session would
otherwise get wrong. If not, it belongs in a prompt, a session note, or `sessions/`, not in
`entities/`. An entity is a standing claim that this practice matters.

## Output contract

Report:

- files loaded at session start, with total bytes
- the five most expensive, and whether each earns its slot
- recommended removals or merges, each with what would replace it
- projected saving

Proposals only. Removals are canon changes and the operator approves them.