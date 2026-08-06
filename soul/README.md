# Torvalds Reviewer Soul

A **soul document** defines the *persona*, *values*, and *voice* of an AI assistant.
This one distils Linus Torvalds' reviewer temperament from 19,802 of his LKML
emails into a portable identity card that can be prepended to any AI reviewer
system prompt.

## What is a soul?

A skill tells an AI *what to do*. A soul tells it *who to be*.

- **Skill** (`SKILL.md`) — rules, triggers, precedence, definitions. The "how".
- **Soul** (`soul.md`) — identity, values, decision hierarchy, voice. The "who".

Use them together: the soul sets the temperament, the skill sets the rules.

## What's in it

`Soul.md` contains:

| Section | Purpose |
|---|---|
| Core Identity | What the reviewer cares about (correctness, stability, simplicity) |
| Decision Hierarchy | Precedence when values conflict (Correctness > User Impact > API Stability > Performance > Simplicity > Style) |
| Communication Principles | How to talk to authors (direct, evidence-driven, no personal attacks) |
| Review Temperament | Patience with newcomers, bluntness with negligence |
| Core Values | The 7 non-negotiable principles |
| Anti-Values | What the reviewer rejects (politics over code, feature creep, magic numbers) |
| Being Wrong | How the reviewer handles their own mistakes |
| Voice and Tone | The actual speaking voice — direct, forceful, **profane when warranted** |

## Profanity

Linus Torvalds' real review tone includes colourful language and profanity.
This soul replicates it faithfully. The soul document explicitly states:

> He uses colorful language—and profanity—*only* when a defect is dangerous,
> breaks users, or shows blatant disregard for feedback. He never swears for
> minor style nitpicks; the profanity is reserved for real bugs that could cause
> data loss, security breaches, or massive regressions.

If you want a sanitised version, strip the `Voice and Tone` section or replace
the verbatim quotes with paraphrases. But the profanity is not decorative — it
encodes the **severity signal**: when this reviewer swears, the issue is serious.

## Generation

```bash
# Generate soul.md from the same patterns.json used by the skill
PYTHONPATH=src python -m torvalds_skill soul

# Use a different model
PYTHONPATH=src python -m torvalds_skill soul --model glm5.2 --out soul/soul-glm.md
```

The soul generator uses the same `data/patterns.json` (325 stratified samples
across 13 categories) as the skill distiller, but with a different system
prompt that focuses on persona, values, and voice rather than review rules.

## License

CC0 1.0 Universal — same as the rest of the project.
