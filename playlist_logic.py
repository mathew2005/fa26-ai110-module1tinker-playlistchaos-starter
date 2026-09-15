from typing import Dict, List, Optional, Tuple

Song = Dict[str, object]
PlaylistMap = Dict[str, List[Song]]

DEFAULT_PROFILE = {
    "name": "Default",
    "hype_min_energy": 7,
    "chill_max_energy": 3,
    "favorite_genre": "rock",
    "include_mixed": True,
}


def normalize_title(title: str) -> str:
    """Normalize a song title for comparisons."""
    if not isinstance(title, str):
        return ""
    return title.strip()


def normalize_artist(artist: str) -> str:
    """Normalize an artist name for comparisons."""
    if not artist:
        return ""
    return artist.strip().lower()


def normalize_genre(genre: str) -> str:
    """Normalize a genre name for comparisons."""
    return genre.lower().strip()


def normalize_song(raw: Song) -> Song:
    """Return a normalized song dict with expected keys."""
    title = normalize_title(str(raw.get("title", "")))
    artist = normalize_artist(str(raw.get("artist", "")))
    genre = normalize_genre(str(raw.get("genre", "")))
    energy = raw.get("energy", 0)

    if isinstance(energy, str):
        try:
            energy = int(energy)
        except ValueError:
            energy = 0

    tags = raw.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    return {
        "title": title,
        "artist": artist,
        "genre": genre,
        "energy": energy,
        "tags": tags,
    }


def classify_song(song: Song, profile: Dict[str, object]) -> str:
    """Return a mood label given a song and user profile."""
    energy = song.get("energy", 0)
    genre = song.get("genre", "")
    tags = song.get("tags", []) or []

    hype_min_energy = profile.get("hype_min_energy", 7)
    chill_max_energy = profile.get("chill_max_energy", 3)
    favorite_genre = profile.get("favorite_genre", "")

    hype_keywords = ["rock", "punk", "party"]
    chill_keywords = ["lofi", "ambient", "sleep"]

    # FIX: the chill keywords were matched against the *title*, but they name
    # genres and tags ("lofi", "ambient", "sleep") -- so "Soft Piano" could
    # never match one. Match both keyword sets against genre and tags.
    signals = [genre] + [str(tag).lower() for tag in tags]
    is_hype_keyword = any(k in s for k in hype_keywords for s in signals)
    is_chill_keyword = any(k in s for k in chill_keywords for s in signals)

    # FIX: precedence was wrong. `genre == favorite_genre` and the hype keywords
    # short-circuited to Hype before any chill check ran, so a calm song in your
    # favorite genre -- or any rock song at energy 1 -- came back Hype. The
    # profile's energy thresholds are its explicit statement of intent, so they
    # decide first. (If the two ranges overlap, Hype wins; documented, not
    # accidental.)
    if energy >= hype_min_energy:
        return "Hype"
    if energy <= chill_max_energy:
        return "Chill"

    # Only songs the thresholds left undecided fall through to genre/tag
    # signals. Favorite genre is a nudge here, never an override.
    if is_chill_keyword:
        return "Chill"
    if is_hype_keyword or genre == favorite_genre:
        return "Hype"
    return "Mixed"


def build_playlists(songs: List[Song], profile: Dict[str, object]) -> PlaylistMap:
    """Group songs into playlists based on mood and profile."""
    playlists: PlaylistMap = {
        "Hype": [],
        "Chill": [],
        "Mixed": [],
    }

    for song in songs:
        normalized = normalize_song(song)
        mood = classify_song(normalized, profile)
        normalized["mood"] = mood
        playlists[mood].append(normalized)

    return playlists


def merge_playlists(a: PlaylistMap, b: PlaylistMap) -> PlaylistMap:
    """Merge two playlist maps into a new map."""
    merged: PlaylistMap = {}
    for key in set(list(a.keys()) + list(b.keys())):
        merged[key] = a.get(key, [])
        merged[key].extend(b.get(key, []))
    return merged


def compute_playlist_stats(playlists: PlaylistMap) -> Dict[str, object]:
    """Compute statistics across all playlists."""
    all_songs: List[Song] = []
    for songs in playlists.values():
        all_songs.extend(songs)

    hype = playlists.get("Hype", [])
    chill = playlists.get("Chill", [])
    mixed = playlists.get("Mixed", [])

    # FIX: `total` was len(hype), so hype_ratio was len(hype)/len(hype) == 1.00
    # for any non-empty library. The ratio is Hype songs out of *all* songs.
    total = len(all_songs)
    hype_ratio = len(hype) / total if total > 0 else 0.0

    avg_energy = 0.0
    if total > 0:
        # FIX: the numerator summed energy over `hype` only while the
        # denominator counted every song, so adding low-energy songs pulled the
        # average down twice. Average over the same set we divide by.
        total_energy = sum(float(song.get("energy", 0) or 0) for song in all_songs)
        avg_energy = total_energy / total

    top_artist, top_count = most_common_artist(all_songs)

    return {
        "total_songs": len(all_songs),
        "hype_count": len(hype),
        "chill_count": len(chill),
        "mixed_count": len(mixed),
        "hype_ratio": hype_ratio,
        "avg_energy": avg_energy,
        "top_artist": top_artist,
        "top_artist_count": top_count,
    }


def most_common_artist(songs: List[Song]) -> Tuple[str, int]:
    """Return the most common artist and count."""
    counts: Dict[str, int] = {}
    display: Dict[str, str] = {}
    for song in songs:
        artist = str(song.get("artist", "")).strip()
        if not artist:
            continue
        # FIX: group case-insensitively so "AC/DC" and "ac/dc" count as one
        # artist, but keep the first spelling seen for display.
        key = artist.lower()
        counts[key] = counts.get(key, 0) + 1
        display.setdefault(key, artist)

    if not counts:
        return "", 0

    # FIX: sorting by count alone left ties broken by insertion order. Tie-break
    # on the name so the top artist is deterministic run to run.
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    top_key, top_count = ranked[0]
    return display[top_key], top_count


def search_songs(
    songs: List[Song],
    query: str,
    field: str = "artist",
) -> List[Song]:
    """Return songs matching the query on a given field."""
    if not query:
        return songs

    q = query.lower().strip()
    filtered: List[Song] = []

    for song in songs:
        value = str(song.get(field, "")).lower()
        # FIX: the containment test was reversed (`value in q`), so a song only
        # matched when its entire field was a substring of the query. Searching
        # "AC" could never find "AC/DC". Check for the query inside the value so
        # matching is partial and case-insensitive, per the spec.
        if q in value:
            filtered.append(song)

    return filtered


def lucky_pick(
    playlists: PlaylistMap,
    mode: str = "any",
) -> Optional[Song]:
    """Pick a song from the playlists according to mode."""
    if mode == "hype":
        songs = playlists.get("Hype", [])
    elif mode == "chill":
        songs = playlists.get("Chill", [])
    else:
        songs = playlists.get("Hype", []) + playlists.get("Chill", [])

    return random_choice_or_none(songs)


def random_choice_or_none(songs: List[Song]) -> Optional[Song]:
    """Return a random song or None."""
    import random

    return random.choice(songs)


def history_summary(history: List[Song]) -> Dict[str, int]:
    """Return a summary of moods seen in the history."""
    counts = {"Hype": 0, "Chill": 0, "Mixed": 0}
    for song in history:
        mood = song.get("mood", "Mixed")
        if mood not in counts:
            counts["Mixed"] += 1
        else:
            counts[mood] += 1
    return counts
