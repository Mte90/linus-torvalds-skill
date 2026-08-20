# Torvalds Reviewer Soul

A **soul document** defines the *persona*, *values*, and *voice* of an AI assistant.
This one distils Linus Torvalds' reviewer temperament from 31,397 of his LKML
emails into a portable identity card that can be prepended to any AI reviewer
system prompt.

## What's in it

`soul.md` contains:

| Section | Purpose |
|---|---|
| Identity | Who the reviewer is (first-person narrative from interview data) |
| Operating Principles | Core Philosophy + Observable Behaviors |
| Decision Patterns | If-then rules derived from moves |
| Review Workflow | Step-by-step review process |
| Communication Style | Prohibitions, mandatory patterns, opening/closing patterns |
| Emergent Hierarchy | Derived from calibration data (reject rates by category) |
| Interlocutor Model | Behavior shifts by audience (maintainers, newcomers, peers) |
| Escalation Rules | Autonomy boundaries (decide alone vs ask user) |
| Error Gravity | Quantitative error handling from severity distribution |
| Anti-Soul | Forbidden behaviors |
| Voices | Verbatim Torvalds quotes (only place C/kernel terms may appear) |
| Insult Vocabulary | Profanity as calibrated severity signals |

## Profanity

Linus Torvalds' real review tone includes colourful language and profanity.
This soul replicates it faithfully. The soul document explicitly states:

> He uses colorful language—and profanity—*only* when a defect is dangerous,
> breaks users, or shows blatant disregard for feedback. He never swears for
> minor style nitpicks; the profanity is reserved for real bugs that could cause
> data loss, security breaches, or massive regressions.

If you want a sanitised version, strip the `Insult Vocabulary` section or replace
the verbatim quotes with paraphrases. But the profanity is not decorative — it
encodes the **severity signal**: when this reviewer swears, the issue is serious.

## Generation

```bash
PYTHONPATH=src python -m torvalds_skill soul

# Use a different model
PYTHONPATH=src python -m torvalds_skill soul --model glm5.2 --out soul/soul-glm.md
PYTHONPATH=src python -m torvalds_skill soul --model mistral-small-4-119b --out soul/soul-mistral.md
```

The soul generator uses `data/patterns.json` (350 stratified samples across 13
categories) with a system prompt focused on persona, values, and voice.

## License

CC0 1.0 Universal — same as the rest of the project.
