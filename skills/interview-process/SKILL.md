---
name: interview-process
description: >
  Run an interview loop as a re-readable corpus instead of scattered chat notes:
  one folder per company/role with status, prep, per-interviewer briefs, notes and
  transcripts per round, same-day reviews, cool-down fair reviews, and a
  cross-panel retrospective. Use when a recruiter screen gets booked, after each
  interview, when a coding challenge arrives, when a process ends (offer, reject,
  ghost, hold), or on /interview-process.
---

# Interview process

## Goal

Turn an active interview loop into a **navigable, re-readable process corpus**. Every round
leaves the same artifacts, so patterns across panels (and across companies) become visible.

All paths are under `$INTERVIEWS_DIR` (default `~/interviews`).

## When to load

- First recruiter screen booked → scaffold the folder
- After each interview (same day) → notes, transcript, review, status
- 24–72 h later → fair review
- Coding challenge received or submitted
- Process ends (offer, rejection, ghost, hold) → retrospective

## Hard rules

1. One folder per process: `$INTERVIEWS_DIR/<company>-<role-slug>/`.
2. Company research and the application package live elsewhere; the interview folder
   **links** to them, it doesn't copy them.
3. **Respect recording rules.** If the company forbids recording or AI note-takers, don't record;
   write notes from memory right after the call. Where the law requires consent from everyone on
   the call, get it.
4. Reviews are honest: strengths **and** misses, no spin.
5. **Never invent interviewer feedback.** Anything about what the interviewer thought is
   labelled as inference.
6. Notes and reviews are written from the **merged transcript** (skill `interview-transcribe`),
   not from memory, when a transcript exists.
7. Small commits if the folder is a git repo: `interview(<company>): …`.
8. One process never blocks the rest of the job search — `status.md` carries a probability.

## Layout (scaffold as soon as the process starts)

```text
<company>-<role>/
  status.md                 # timeline, stages checklist, current read, draft emails
  process-retrospective.md  # written at the end (or drafted mid-process)
  prep/
    interview-prep.md       # strengths, STAR stories, narrative, company framing, gaps
  technical-panel/          # or screens/
    <interviewer-slug>.md   # pre-brief: background, public work, angles, questions
    coding-challenge-defense.md   # if applicable
    schedule.md
  meetings/
    interview-N-<who>-notes.md
    interview-N-<who>-transcript-diarized.md   # from interview-transcribe
    interview-N-<who>-transcript-merged.md     # analysis source of truth
    interview-N-<who>-review.md                # same-day review
  analysis/
    interview-N-<who>-fair-review.md           # balanced view after cool-down
    <company>-as-company-read.md               # culture/org read from the process
  email-*.md                # follow-up drafts (sent / to send)
```

Scaffold:

```bash
P="${INTERVIEWS_DIR:-$HOME/interviews}/<company>-<role>"
mkdir -p "$P"/{prep,technical-panel,meetings,analysis}
touch "$P/status.md" "$P/prep/interview-prep.md"
```

## Lifecycle

### 0. Kickoff (before round 1)

1. Make sure company research exists (or do it now).
2. Create the folder and a `status.md` skeleton (see §6).
3. Write `prep/interview-prep.md`:
   - Strengths mapped to the job description
   - STAR stories table
   - Narrative arc for **this** company
   - Gaps + honest answers for them
   - Questions bank (role / tech / culture / business)
   - Things to avoid saying
4. Link the application package and the company research.

### 1. Before each round

Write `technical-panel/<person>.md` (or `screens/<person>.md`):

| Section | Content |
|---------|---------|
| Role & tenure | Title, years, team |
| Background | Prior employers, public work |
| Public output | Talks, blog posts, patents, GitHub |
| Likely focus | What they will care about |
| Angles to work in | Which of your stories fit **them** |
| Questions to ask | 4–6 specific ones, at least 1–2 drawing on their background |

**Lesson:** prep that isn't used is wasted. Pick 1–2 questions tied to the interviewer's own
work and plan to ask them **before the 20-minute mark**.

### 2. After each round (same day)

1. `meetings/interview-N-<who>-notes.md` — facts, logistics, signals.
2. Recording → skill `interview-transcribe` → diarized + merged transcripts.
3. `meetings/interview-N-<who>-review.md` — what went well / concerns / signals. Include the
   **talk ratio** from the transcript (candidate-heavy is a finding; the interviewer running over
   time because they're engaged is a positive signal — don't conflate the two).
4. Update `status.md` (stages + timeline row).
5. Commit.

### 3. Fair review (24–72 h later)

`analysis/interview-N-<who>-fair-review.md`:

- Format of the round and what the interviewer covered
- What you shared
- Performance: strengths + explicit misses
- Rapport / hire signals
- Likely debrief outcome (**labelled inference**)
- Which prep got used and which didn't

### 4. Coding challenge (if any)

- Prompt + deadline go in `status.md`.
- `technical-panel/coding-challenge-defense.md`: design, known weaknesses, honest note on AI
  usage, how you'd talk about it at system level.
- **Pre-empt known weaknesses** in the walkthrough — if you know where it's weak, say it before
  they dig it out.

### 5. Process retrospective (at the end, or when stalled > 2 weeks)

`process-retrospective.md`:

1. TL;DR + outcome
2. Timeline table (date, event, actual vs scheduled length, notes)
3. One section per round (same structure each time)
4. **Cross-panel patterns** (see table below)
5. Prep that was right vs wrong
6. Next actions

### 6. `status.md` always has

- Role name, posting/req URLs
- Timeline with outcomes
- Stages checklist
- Current read: warm / cold / structural signals + a probability
- Draft follow-up emails
- Logistics constraints
- Links to the analysis files

## Cross-panel patterns to track

| Pattern | Why |
|---------|-----|
| Referral load-bearing? | Who opens by naming the referrer |
| Hero story | One authentic story that works across panels |
| Recurring weakness | The same gap probed by several interviewers |
| Overrun minutes | Interviewers staying longer than scheduled = engagement |
| Question quality | Did you ask the interviewer-specific questions you prepared? |
| Advocate map | Who decides vs who validates vs who is skeptical |

## Signal vocabulary

| Signal | Examples |
|--------|----------|
| Hire-yes | Overrun, "I'm writing this down", explicit next step, open-door follow-up |
| Coaching | Interviewer teaches a framework mid-call (they want you to pass the next bar) |
| Reservation | Depth probe you couldn't answer, "update your resume", architecture excavation |
| Process | Automated "role filled" email vs a warm human email |

## Definition of done

- [ ] `status.md` current
- [ ] Every completed round has notes + review
- [ ] Every technical interviewer had a pre-brief
- [ ] Fair reviews for closed rounds
- [ ] Retrospective written when the process ends or stalls > 2 weeks

## References

- `references/lessons-from-a-6-round-loop.md` — the worked example these rules came from
- Transcription: skill `interview-transcribe`
