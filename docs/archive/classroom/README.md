# Classroom (archived 2026-08-05)

The PropulsionLab Classroom shipped as five hand-written design challenges, one
per engine family, served at `/classroom/`. It was pulled from the live site on
2026-08-05 — not because it was broken, but because five static problems behind
a top-level nav link promised a teaching product the site did not yet have. A
visitor who clicked "Classroom" expecting a course found one exercise per engine
and nothing to do afterwards. Rather than leave that on the nav, the whole page
is parked here until the version worth releasing exists.

The code in this folder is the exact version that was live, moved with `git mv`
so its history is intact.

## What it did

`classroom.js` holds a `CHALLENGES` array of five problems. Each one:

- fixes a flight condition (altitude, Mach) the student cannot change,
- exposes two or three design controls (pressure ratio, bypass ratio, Tt4, …),
- states numeric targets (thrust, TSFC, efficiency) with tolerances,
- grades by POSTing the student's inputs to the **real** `/simulate/<engine>`
  endpoint and comparing the response against those targets,
- offers one static hint.

So grading was already solver-truth — the page never hard-coded an answer. What
it lacked was volume, difficulty control, and any explanation beyond the hint.

`index.html` is self-contained: all CSS is inline, and its only script
dependencies are `/lab/launch.js` and `/lab/classroom/classroom.js`.

## Why it isn't just deleted

The grading architecture is the good part and should survive into whatever
replaces this. The planned successor (see the note below) keeps the
"grade against the live solver" idea and fixes the three gaps:

1. **Question bank** — generate problems procedurally *from* the solver instead
   of writing them by hand: draw a design point, run the cycle, build the
   question around the computed result. The answer is then correct by
   construction, solvability is verified before the question is shown, and
   difficulty becomes measurable (sample the control space, report the fraction
   of settings that hit the targets) rather than a label someone guessed.
2. **Explanations** — `app/engine_core/sensitivity.py` already computes local
   derivatives, so a wrong answer can be explained with the student's own
   numbers ("Tt3 rose 620 → 710 K when you moved PR 10 → 14") instead of one
   fixed hint string.
3. **Tutor** — optional conversational layer, grounded on the numbers the
   deterministic layer computed, never computing physics itself.

Only step 3 needs a paid API. Steps 1 and 2 run entirely on code already in
this repo.

## How to restore it

1. `git mv docs/archive/classroom/index.html app/static/classroom/index.html`
   and the same for `classroom.js` (create `app/static/classroom/` first).
2. In `app/main.py`, re-add the route:

   ```python
   @app.get("/classroom", include_in_schema=False)
   @app.get("/classroom/", include_in_schema=False)
   def classroom() -> FileResponse:
       """Serve the PropulsionLab Classroom (guided design challenges)."""

       return FileResponse(STATIC_PATH / "classroom" / "index.html")
   ```

3. In the same file, add `"/classroom", "/classroom/"` back to the clean-route
   tuple in the `cache_control` middleware, or the page will be served with the
   immutable-asset policy and go stale on the next edit.
4. Re-add nav links. They were removed from four places:
   - `app/static/index.html` — mission bar (next to "3D viewer") and the
     Resources column in the footer,
   - `app/static/methodology.html` — page nav and the "See it in action" links,
   - `app/static/m/index.html` — the mobile "more" sheet,
   - `app/static/privacy.html` — page nav.
5. Bump the `?v=` token on `classroom.js` in `index.html`. Versioned assets are
   served `immutable` for a year, so an unchanged token means returning visitors
   keep the old file.
6. `tests/test_methodology.py` currently asserts the Classroom is archived and
   unlinked. Replace those assertions with the route/coverage tests that were
   there before (see this file's history).

## Related

- `docs/` has no other archived pages yet; this is the first.
- The successor design is recorded in the project memory note
  `classroom-question-generator-plan`.
