# Playlist Chaos - Debugging Notes

AI110 Week 1 Tinker Lab

Run the app: `streamlit run app.py`
Run the tests: `python test_playlist_logic.py`

## Part 1: what looked wrong

Things I noticed while clicking around:

1. Searching artist for `AC` returns nothing, even though AC/DC is in the list. Only the full name works.
2. Artist names all show up lowercase: `ac/dc`, `the weeknd`.
3. Hype ratio says `1.00` no matter how many Chill songs there are.
4. Average energy says `4.05` when it should be `5.73`, and it drops further when I add *low* energy songs.
5. A rock song at energy 1 gets labeled Hype. Same for calm ambient songs if ambient is my favorite genre.
6. Lucky Pick set to Hype with no Hype songs crashes with `IndexError: Cannot choose from an empty sequence`.
7. Lucky Pick on "any" never returns a Mixed song.
8. Clicking "Add to playlist" with a blank title does nothing at all, no error.
9. The two energy sliders are written as two columns but render stacked.

### The search bug in my own words

`search_songs` already lowercases both sides, so case wasn't the problem. The match was written backwards:

```python
if value and value in q:
```

This asks whether the artist name is inside my query. So `"ac/dc" in "ac"` is False and AC/DC never matches. The only searches that worked were ones that contained a whole artist name, which is why it felt random instead of just broken. Swapping it to `q in value` asks the right question.

**Checkpoint:** the `value in q` condition. It was reversed, so a song only matched when its whole field fit inside the query.

**Write-down answer:** searching `mau` in the Hype playlist gives **Strobe**.

## Part 2: fixes

One fix per commit, each marked `# FIX:` in the code.

**1. Search - `search_songs`.** Reversed containment test. Changed to `q in value`. Checked in the app: `AC` finds Thunderstruck, `mau` finds Strobe, `WEEKND` and `  AC  ` both work, empty query still returns everything.

**2. Classification - `classify_song`.** Two problems. The chill keywords (`lofi`, `ambient`, `sleep`) were matched against the *title*, but those are genre and tag words, so that check never fired. And the Hype branch ran first and included `genre == favorite_genre`, so it short-circuited before any chill check. That's why rock at energy 1 came back Hype.

I made the energy thresholds decide first since they're the most explicit thing in the profile, and left genre/tag signals to break ties for middle energies. Favorite genre is now a nudge instead of an override.

The sliders are independent, so you can set chill max above hype min and get an overlapping band. I made that resolve to Hype on purpose and added a sidebar warning so it isn't a surprise.

Checked: ambient/2 is Chill under both profiles, rock/1 is Chill, Thunderstruck and Strobe stay Hype, jazz/5 with no signal is Mixed.

**3. Stats - `compute_playlist_stats`.** Two bad denominators. `total = len(hype)` made the ratio `len(hype)/len(hype)`, always 1.00. And avg energy summed Hype energies but divided by every song, so adding a quiet song hurt it twice. Both now use the whole library.

Also fixed `most_common_artist`: it counted `AC/DC` and `ac/dc` separately and broke ties by dict order. Now groups case-insensitively and tie-breaks on name.

Checked against an average I worked out separately. App shows 0.50 and 5.73 for the default 22 songs. Adding four low-energy songs to two hype ones moves the ratio 1.00 to 0.33 and the average 9.50 to 3.83.

**4. Lucky Pick - `lucky_pick`.** `random_choice_or_none` called `random.choice` on a possibly empty list, so it never returned the None its name promised. Separately, "any" only pooled Hype + Chill. Both fixed. `app.py` already had a warning branch for None, it just never ran.

Checked: empty Hype returns None instead of crashing, and over 400 seeded draws "any" reaches all three playlists.

**5. `merge_playlists`.** `merged[key] = a.get(key, [])` stored a reference, so extending it modified the caller's playlists. `app.py` merges with `{}` so nothing broke today, but a real merge would have duplicated songs. Also swapped the `set()` key iteration for a stable order. Copying the list fixes both.

**6. `normalize_artist`.** It lowercased the stored value, which mixed up "normalize for comparison" with "normalize for storage". Now it only strips. Search still matches case-insensitively because it lowercases at comparison time.

**7. `app.py`.** Blank title/artist now warns instead of failing silently, the dead `with col1:` column layout is gone, and the favorite genre dropdown no longer hard-codes `index=0`.

## Part 3: refactor

The three mood names were written out in four different functions and three of them flattened the playlist map by hand. Added a `MOOD_LABELS` constant and a `collect_songs()` helper, rewrote the stats counts as a comprehension, and simplified `history_summary`.

**What it made easier:** the mood labels and their order live in one place, so "what counts as all the songs" has one answer instead of three loops you have to compare.

**How I checked it was safe:** committed all the fixes first, then saved a copy of the old module and diffed behavior against it. 3000 random trials across the logic functions with the same RNG seed, plus 64000 search comparisons. No mismatches. Then reloaded the app and re-tested search, tabs, stats and Lucky Pick by hand.

## Tests

`test_playlist_logic.py` has 21 tests, no framework needed.

- Original starter code: 7/21 pass, plus one crash
- After the fixes: 21/21

I ran the same test file against the original `playlist_logic.py` from git history to confirm each test actually fails without its fix.

## Part 4: reflection

AI was most useful for explaining a line I could tell was wrong but couldn't put into words. Once it said the containment check was backwards, the fix was one expression.

Where I disagreed: the lab says a calm ambient song at energy 2 lands in Hype. Under the default profile it doesn't, it's already Chill because `2 <= chill_max_energy`. It only goes to Hype if you set favorite genre to ambient. Reproducing it first stopped me from adjusting a threshold that was fine. The real bug was precedence, and under the default profile it shows up as rock at energy 1 being Hype instead. Fixing the symptom as described would have missed it.

Same thing with `classify_song` in general. The easy move is to let the assistant rewrite the whole function, but a rewrite would have quietly decided things I never asked about, like whether favorite genre matters at all or what happens in the overlap. Small separate commits with tests are checkable. A rewrite you either trust or you don't.

Habit I'm keeping: reproduce it, then read the code, and write the failing test before the fix. The 7/21 to 21/21 split is the actual evidence anything worked.

Takeaway for class: assistants are good at explaining what code does and pretty willing to be confidently wrong about what it should do. Ask for the first, decide the second yourself, and keep the diff small enough to see the difference.
