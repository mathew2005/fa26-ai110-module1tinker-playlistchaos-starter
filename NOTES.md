# Playlist Chaos — Debugging Notes

Tinker (Lab) Week 1 — AI110 Foundations of AI Engineering

Run the app: `streamlit run app.py`
Run the regression tests: `python test_playlist_logic.py`

---

## Part 1 — Meet the Chaos

### Things that felt confusing, inconsistent, or strange

| # | What I saw in the app | Where it lives |
|---|---|---|
| 1 | Searching the artist field for `AC` returned nothing, even though AC/DC is right there. Only typing the artist's *entire* name worked. | `search_songs` |
| 2 | Artist names rendered as `ac/dc` and `the weeknd` in every playlist row and in "Most common artist". | `normalize_artist` |
| 3 | **Hype ratio was stuck at `1.00`** no matter how many Chill songs existed. | `compute_playlist_stats` |
| 4 | Average energy read `4.05` when the real average was `5.73`, and it fell further every time I added a *low*-energy song. | `compute_playlist_stats` |
| 5 | A rock song at energy 1 was labelled **Hype**. Setting favorite genre to `ambient` moved calm ambient songs into **Hype** too. | `classify_song` |
| 6 | Lucky Pick set to **Hype** with no Hype songs **crashed the app** with `IndexError: Cannot choose from an empty sequence`. | `random_choice_or_none` |
| 7 | Lucky Pick on `any` never returned a Mixed song, even with 5 Mixed songs in the library. | `lucky_pick` |
| 8 | "Add to playlist" with a blank title did nothing at all — no song, no error. The button looked broken. | `add_song_sidebar` |
| 9 | The two energy sliders were written as a 2-column layout but rendered stacked. | `profile_sidebar` |

### The search bug, in my own words

`search_songs` lower-cases both the query and the field, which is why the
*case-insensitive* half of the spec already worked. The match itself was
written backwards:

```python
if value and value in q:      # asks: is the artist inside my query?
```

That asks whether the **song's whole field** appears inside the **query**, so
`"ac/dc" in "ac"` is `False` and AC/DC never matched. The only queries that
matched were ones that fully contained an artist name — typing `ac/dc` worked,
which is exactly why the bug looked intermittent rather than total. Reversing
it to `q in value` asks the question the spec describes: does the query appear
somewhere inside the field?

**Checkpoint answer — what line or condition caused search to miss AC/DC?**
The `value in q` containment test; it was reversed, so a song matched only when
its entire field was a substring of the query instead of the other way round.

**Write-down answer:** searching the Hype playlist's artist box for `mau`
returns the song **Strobe** (by Deadmau5).

---

## Part 2 — Fixes

Each fix is its own commit, with a comment in the code marked `# FIX:`.

### 1. Search missed partial queries — `search_songs`

- **Source:** the containment test was reversed (`value in q`).
- **Change:** `if q in value`. Also dropped the redundant `value and` guard —
  `q in ""` is already `False`.
- **Tested:** in the app, `AC` → Thunderstruck by AC/DC and `mau` → Strobe.
  Also `ac`, `WEEKND`, and `  AC  ` (whitespace) all match; `zz` matches
  nothing; an empty query still returns everything.

### 2. Calm songs classified as Hype — `classify_song`

- **Source:** two separate defects.
  1. `is_chill_keyword` matched `lofi` / `ambient` / `sleep` against the song's
     **title**, but those words name genres and tags. "Soft Piano" could never
     match, so the chill keyword path was effectively dead code.
  2. Precedence. The Hype branch was checked first and included
     `genre == favorite_genre` and the hype keywords, so it short-circuited
     before any chill check ran. A rock song at energy 1 was Hype because
     `"rock"` is a hype keyword; a calm ambient song was Hype whenever ambient
     was the favorite genre.
- **Change:** the profile's numeric thresholds are its most explicit statement
  of intent, so they decide first: `energy >= hype_min` → Hype,
  `energy <= chill_max` → Chill. Only songs left undecided in the middle fall
  through to genre/tag signals, and favorite genre is a **nudge** there rather
  than an override. Keyword matching now looks at genre *and* tags, which is
  what those keyword lists were clearly written for (it makes a `party`-tagged
  song Hype and a `sleep`-tagged song Chill).
- **Judgement call I made:** the two sliders are independent, so a profile can
  set chill max ≥ hype min and create an overlapping band. I resolved the
  overlap as Hype deliberately rather than by accident, and `app.py` now warns
  in the sidebar when the ranges overlap so the rule is visible instead of
  surprising.
- **Tested:** ambient/energy 2 is Chill under both the default profile *and*
  with favorite genre ambient; rock/energy 1 is Chill; Thunderstruck (rock 9)
  and Strobe (electronic 7) stay Hype; jazz/energy 5 with no signal is Mixed.
  In the app the Chill tab now holds all six low-energy songs including Clair
  de Lune (ambient, energy 2).

### 3. Hype ratio and average energy were wrong — `compute_playlist_stats`

- **Source:** two mismatched denominators.
  - `total = len(hype)`, so `hype_ratio = len(hype) / len(hype)` — pinned at
    `1.00` for any non-empty library. It only ever read `0.00` or `1.00`.
  - `avg_energy` summed energy over `hype` only but divided by
    `len(all_songs)`, so each new low-energy song both left the numerator
    unchanged *and* grew the denominator — the average dropped twice.
- **Change:** both figures are now measured over every song.
- **Also:** `most_common_artist` sorted by count alone, leaving ties broken by
  dict insertion order, and counted `AC/DC` and `ac/dc` as two artists. It now
  groups case-insensitively, keeps the first spelling seen for display, and
  tie-breaks on the name so the result is deterministic run to run.
- **Tested:** against an independently computed average. With the 22 default
  songs the app shows Hype ratio `0.50` and Average energy `5.73`, matching
  `11/22` and the true mean. Adding four low-energy songs to two hype songs
  moves the ratio `1.00 → 0.33` and the average `9.50 → 3.83`, in the
  direction you would expect. An empty library returns `0.0` for both instead
  of dividing by zero.

### 4. Lucky Pick crashed, and could never pick Mixed — `lucky_pick`

- **Source:** `random_choice_or_none` called `random.choice(songs)`
  unconditionally, and `random.choice` raises `IndexError` on an empty list —
  so the function never returned the `None` its own name promised. Separately,
  `mode="any"` built its pool from `Hype + Chill` only, so Mixed songs were
  unreachable.
- **Change:** return `None` for an empty pool; `"any"` now spans every
  playlist. `app.py` already handled `None` with a "No songs available for
  this mode." warning — the fix let that existing branch finally run.
- **Tested:** `mode="hype"` with an empty Hype list returns `None` instead of
  crashing, and a fully empty library does too. Over 400 seeded draws,
  `mode="any"` reaches Hype, Chill **and** Mixed; `mode="chill"` still only
  returns Chill songs. Clicking "Feeling lucky" in the app returns a song and
  records it in History.

### 5. `merge_playlists` mutated its own input

- **Source:** `merged[key] = a.get(key, [])` stored a *reference* to the first
  map's list, so `.extend()` appended into the caller's playlists. `app.py`
  calls `merge_playlists(base_playlists, {})`, which hid the damage today, but
  any real merge would have duplicated songs into the source map. Iterating
  `set(...)` of the keys also gave the merged map an arbitrary key order.
- **Change:** copy the list before extending (`list(a.get(key, []))`), and
  keep a stable key order.
- **Tested:** the source map is unchanged after a merge, `merged["Hype"]` is a
  distinct object, and the key order is identical across repeated runs.

### 6. Artist capitalization was destroyed — `normalize_artist`

- **Source:** `normalize_artist` lower-cased the value it *stored*, conflating
  "normalize for comparison" with "normalize for storage".
- **Change:** storage strips whitespace only. Search and artist counting
  already lower-case at the point of comparison, so nothing needed to become
  case-sensitive to get the display right.
- **Tested:** rows render `AC/DC` and `The Weeknd`; searching `AC`, `mau` and
  `WEEKND` all still match, confirming search stayed case-insensitive.

### 7. `app.py` polish

- Adding a song with a blank title or artist silently did nothing; the form now
  warns what's missing and confirms a successful add.
- The two energy sliders were wrapped in `with col1:` / `with col2:` but called
  `st.sidebar.slider`, which always renders in the sidebar root — the columns
  had no effect at all. Removed the dead layout rather than leaving code that
  implies something it doesn't do.
- The favorite-genre selectbox hard-coded `index=0`, ignoring the genre already
  stored in the profile.
- Added the overlapping-threshold warning described in fix 2.

---

## Part 3 — Refactor (behavior-preserving)

`playlist_logic.py` spelled out the three mood names in four different
functions, and three of them flattened the playlist map by hand. I introduced a
`MOOD_LABELS` constant and a `collect_songs()` helper, rebuilt
`compute_playlist_stats` around a dict comprehension instead of six
intermediate locals, and reduced `history_summary`'s `if/else` to one lookup.

**What the refactor made easier to understand without changing the result:**
the mood labels and the order they're visited now live in one place, so
"what counts as all the songs?" has a single answer you can read once instead
of three hand-written loops you have to compare.

**How I confirmed it was safe.** I committed all seven fixes *first*, then
snapshotted the pre-refactor module and ran a differential test: 3000
randomized trials (including junk energies like `"bad"`, blank genres, and
overlapping profile thresholds) comparing `classify_song`, `build_playlists`,
`compute_playlist_stats`, `history_summary`, `merge_playlists` and
`lucky_pick` under an identical RNG seed, plus 64000 `search_songs`
comparisons. **Zero mismatches.** Then I reloaded the app and re-checked
search, the tabs, stats and Lucky Pick by hand.

---

## Verification

`test_playlist_logic.py` holds 21 regression tests, one per behavior above.
The numbers that matter:

| Code | Result |
|---|---|
| Original starter | **7 / 21 passed** (plus one hard crash) |
| After the fixes | **21 / 21 passed** |

Every fix is covered by at least one test that genuinely fails on the starter
code — I verified this by running the same test file against the original
`playlist_logic.py` out of git history, which is the only way to know a test
is testing anything.

---

## Part 4 — Reflection

**Where AI was genuinely useful.** Explaining a line I could already see was
suspicious but couldn't articulate — the reversed `value in q` is obvious once
someone says "this asks whether the artist contains the query, backwards," and
that sentence is what let me fix it with a one-expression change instead of
rewriting the function.

**Where I had to push back.** The lab's own hint says a calm ambient song at
energy 2 "lands in Hype." Under the *default* profile it doesn't — it's already
Chill, because `2 <= chill_max_energy`. It only lands in Hype once favorite
genre is set to `ambient`. Reproducing it first saved me from "fixing" a
threshold that was never broken; the actual defect was **precedence**, and the
same root cause shows up under the default profile as a rock song at energy 1
being called Hype. A fix aimed at the symptom as stated would have missed it.

The same instinct applied to `classify_song` generally: the tempting move is to
let an assistant rewrite the whole function. But a rewrite would have quietly
re-decided things nobody asked about — whether favorite genre matters at all,
what happens in the threshold overlap — and I'd have had no way to tell which
behavior changes were intended. Small, separately committed changes each with a
test are checkable; a rewrite is something you either trust or don't.

**Habit worth keeping.** Reproduce it, then read the code — and *write the test
that fails first*. The `7/21 → 21/21` split is the only real evidence any of
this worked; without running the tests against the original code I'd just be
asserting that my fixes fixed something. Commit before letting anything
restructure working code, so "did this change behavior?" is a question you can
actually answer instead of argue about.

**Class-ready takeaway.** An assistant is very good at explaining code and
quite willing to be confidently wrong about *intent*. Ask it what the code
does; decide for yourself what it should do — and keep the diff small enough
that the difference between those two is still visible.
