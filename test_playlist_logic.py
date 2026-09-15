"""Regression tests for the Playlist Chaos fixes.

Plain asserts, no test framework needed:  python test_playlist_logic.py
Each test covers one behavior that used to be broken.
"""

import random

from playlist_logic import (
    DEFAULT_PROFILE,
    build_playlists,
    classify_song,
    compute_playlist_stats,
    history_summary,
    lucky_pick,
    merge_playlists,
    most_common_artist,
    normalize_song,
    search_songs,
)


def song(title="T", artist="A", genre="rock", energy=5, tags=None):
    return normalize_song(
        {"title": title, "artist": artist, "genre": genre, "energy": energy,
         "tags": tags or []}
    )


def profile(**overrides):
    p = dict(DEFAULT_PROFILE)
    p.update(overrides)
    return p


# --- search: partial and case-insensitive -----------------------------------

def test_search_matches_partial_query():
    songs = [song(title="Thunderstruck", artist="AC/DC"),
             song(title="Strobe", artist="Deadmau5")]
    assert [s["title"] for s in search_songs(songs, "AC")] == ["Thunderstruck"]
    assert [s["title"] for s in search_songs(songs, "mau")] == ["Strobe"]


def test_search_is_case_insensitive_and_trims():
    songs = [song(title="Blinding Lights", artist="The Weeknd")]
    for query in ("weeknd", "WEEKND", "  Weeknd  "):
        assert len(search_songs(songs, query)) == 1, query


def test_empty_query_returns_everything():
    songs = [song(artist="A"), song(artist="B")]
    assert len(search_songs(songs, "")) == 2


def test_search_no_match_returns_empty():
    assert search_songs([song(artist="AC/DC")], "zz") == []


# --- classification: energy thresholds decide before genre ------------------

def test_calm_song_in_favorite_genre_is_chill():
    calm = song(genre="ambient", energy=2)
    assert classify_song(calm, profile(favorite_genre="ambient")) == "Chill"


def test_low_energy_hype_genre_is_chill():
    assert classify_song(song(genre="rock", energy=1), profile()) == "Chill"


def test_high_energy_is_hype():
    assert classify_song(song(genre="jazz", energy=9), profile()) == "Hype"


def test_middle_energy_uses_genre_and_tag_signals():
    assert classify_song(song(genre="rock", energy=6), profile()) == "Hype"
    assert classify_song(song(genre="pop", energy=5, tags=["sleep"]), profile()) == "Chill"
    assert classify_song(song(genre="pop", energy=5, tags=["party"]), profile()) == "Hype"
    assert classify_song(song(genre="jazz", energy=5), profile()) == "Mixed"


def test_thresholds_respect_the_profile():
    calm = song(genre="jazz", energy=5)
    assert classify_song(calm, profile(chill_max_energy=5)) == "Chill"
    assert classify_song(calm, profile(hype_min_energy=5)) == "Hype"


# --- stats: measured over the whole library ---------------------------------

def test_hype_ratio_is_hype_over_total():
    playlists = build_playlists(
        [song(genre="rock", energy=9), song(genre="ambient", energy=1)], profile()
    )
    stats = compute_playlist_stats(playlists)
    assert stats["total_songs"] == 2
    assert stats["hype_ratio"] == 0.5


def test_avg_energy_covers_every_song():
    playlists = build_playlists(
        [song(genre="rock", energy=10), song(genre="ambient", energy=2)], profile()
    )
    assert compute_playlist_stats(playlists)["avg_energy"] == 6.0


def test_stats_on_empty_library():
    stats = compute_playlist_stats({"Hype": [], "Chill": [], "Mixed": []})
    assert stats["total_songs"] == 0
    assert stats["hype_ratio"] == 0.0
    assert stats["avg_energy"] == 0.0
    assert stats["top_artist"] == ""


def test_top_artist_groups_case_insensitively_and_keeps_casing():
    assert most_common_artist(
        [{"artist": "AC/DC"}, {"artist": "ac/dc"}, {"artist": "Queen"}]
    ) == ("AC/DC", 2)


def test_top_artist_tie_break_is_deterministic():
    tie = [{"artist": "Zed"}, {"artist": "Abe"}]
    assert {most_common_artist(tie) for _ in range(5)} == {("Abe", 1)}


# --- lucky pick: never crashes, can reach every playlist --------------------

def test_lucky_pick_returns_none_when_pool_is_empty():
    assert lucky_pick({"Hype": [], "Chill": [song()], "Mixed": []}, mode="hype") is None
    assert lucky_pick({"Hype": [], "Chill": [], "Mixed": []}, mode="any") is None


def test_lucky_pick_any_can_reach_mixed():
    playlists = build_playlists(
        [song(title="H", genre="rock", energy=9),
         song(title="C", genre="ambient", energy=1),
         song(title="M", genre="jazz", energy=5)], profile()
    )
    assert playlists["Mixed"], "expected a Mixed song in this fixture"
    random.seed(0)
    reachable = {lucky_pick(playlists, mode="any")["title"] for _ in range(300)}
    assert reachable == {"H", "C", "M"}


def test_lucky_pick_respects_mode():
    playlists = build_playlists(
        [song(title="H", genre="rock", energy=9),
         song(title="C", genre="ambient", energy=1)], profile()
    )
    assert {lucky_pick(playlists, mode="chill")["title"] for _ in range(20)} == {"C"}


# --- merge: pure, stable ----------------------------------------------------

def test_merge_does_not_mutate_its_inputs():
    a = {"Hype": [song(title="H1")], "Chill": [], "Mixed": []}
    merged = merge_playlists(a, {"Hype": [song(title="H2")]})
    assert len(a["Hype"]) == 1, "merge mutated the source playlist"
    assert len(merged["Hype"]) == 2
    assert merged["Hype"] is not a["Hype"]


def test_merge_key_order_is_stable():
    a = {"Hype": [], "Chill": [], "Mixed": []}
    orders = {tuple(merge_playlists(a, {"Extra": []}).keys()) for _ in range(5)}
    assert orders == {("Hype", "Chill", "Mixed", "Extra")}


# --- display / history ------------------------------------------------------

def test_artist_capitalization_is_preserved():
    assert song(artist="  AC/DC  ")["artist"] == "AC/DC"


def test_history_counts_unknown_moods_as_mixed():
    assert history_summary(
        [{"mood": "Hype"}, {"mood": "Chill"}, {"mood": "???"}, {}]
    ) == {"Hype": 1, "Chill": 1, "Mixed": 2}


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL  {test.__name__}: {exc or 'assertion failed'}")
        except Exception as exc:  # a crash is a failure, not a reason to stop
            failed += 1
            print(f"  FAIL  {test.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
