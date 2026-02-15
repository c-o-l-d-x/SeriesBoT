import os
import requests
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

TMDB_API_KEY = os.getenv("TMDB_API_KEY", "8c18c4bde8c3c8e1c1c6236d29af7dd7")
OMDB_API_KEY = os.getenv("OMDB_API_KEY", "3939abc8")


class SeriesAPI:
    """Unified API handler for TV series data"""

    def __init__(self, tmdb_key: str = None, omdb_key: str = None):
        self.tmdb_key = tmdb_key or TMDB_API_KEY
        self.omdb_key = omdb_key or OMDB_API_KEY

    # -------------------------------------------------
    # PUBLIC METHODS
    # -------------------------------------------------

    def search_series(self, query: str) -> List[Dict]:
        tmdb = self._search_tmdb(query)
        omdb = self._search_omdb(query)
        imdb = self._search_imdb(query)

        merged = self._merge_results(tmdb, omdb, imdb)

        merged.sort(
            key=lambda x: (
                x.get("type") not in ("tv series", "tv miniseries"),
                -x.get("completeness", 0)
            )
        )
        return merged

    def get_series_details(self, series_id: str) -> Optional[Dict]:
        if "_" not in series_id:
            return None

        source, raw_id = series_id.split("_", 1)

        if source == "tmdb":
            return self._get_tmdb_details(raw_id)

        if source == "imdb":
            return self._get_imdb_details(raw_id.replace("tt", ""))

        if source == "omdb":
            return self._get_omdb_details(raw_id)

        return None

    # -------------------------------------------------
    # SEARCH IMPLEMENTATIONS
    # -------------------------------------------------

    def _search_tmdb(self, query: str) -> List[Dict]:
        try:
            url = "https://api.themoviedb.org/3/search/tv"
            params = {
                "api_key": self.tmdb_key,
                "query": query,
                "language": "en-US",
            }
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()

            results = []
            for item in data.get("results", [])[:10]:
                results.append({
                    "source": "tmdb",
                    "id": f"tmdb_{item['id']}",
                    "tmdb_id": item["id"],
                    "title": item.get("name"),
                    "year": item.get("first_air_date", "")[:4] or None,
                    "type": "tv series",
                    "poster": (
                        f"https://image.tmdb.org/t/p/w500{item['poster_path']}"
                        if item.get("poster_path") else None
                    ),
                    "rating": item.get("vote_average"),
                    "overview": item.get("overview"),
                })
            return results
        except Exception as e:
            logger.error(f"TMDB search error: {e}")
            return []

    def _search_omdb(self, query: str) -> List[Dict]:
        try:
            url = "http://www.omdbapi.com/"
            params = {
                "apikey": self.omdb_key,
                "s": query,
                "type": "series",
            }
            r = requests.get(url, params=params, timeout=10)
            data = r.json()

            if data.get("Response") != "True":
                return []

            results = []
            for item in data.get("Search", [])[:10]:
                results.append({
                    "source": "omdb",
                    "id": f"omdb_{item['imdbID']}",
                    "imdb_id": item["imdbID"],
                    "title": item.get("Title"),
                    "year": item.get("Year", "").split("–")[0],
                    "type": "tv series",
                    "poster": item.get("Poster") if item.get("Poster") != "N/A" else None,
                })
            return results
        except Exception as e:
            logger.error(f"OMDB search error: {e}")
            return []

    def _search_imdb(self, query: str) -> List[Dict]:
        try:
            from imdb import Cinemagoer
            ia = Cinemagoer()
            items = ia.search_movie(query)

            results = []
            for item in items[:15]:
                kind = item.get("kind")
                if kind not in ("tv series", "tv miniseries"):
                    continue

                imdb_id = f"tt{item.movieID}"

                results.append({
                    "source": "imdb",
                    "id": f"imdb_{imdb_id}",
                    "imdb_id": imdb_id,
                    "title": item.get("title"),
                    "year": item.get("year"),
                    "type": kind,
                })
            return results
        except Exception as e:
            logger.error(f"IMDb search error: {e}")
            return []

    # -------------------------------------------------
    # MERGING & SCORING
    # -------------------------------------------------

    def _merge_results(self, *sources) -> List[Dict]:
        merged: Dict[str, Dict] = {}

        for results in sources:
            for r in results:
                key = (
                    r.get("imdb_id")
                    or r.get("tmdb_id")
                    or f"{r.get('title','').lower()}_{r.get('year')}"
                )

                if key not in merged:
                    merged[key] = r
                    merged[key]["sources"] = [r["source"]]
                else:
                    existing = merged[key]
                    for field in (
                        "poster", "rating", "overview",
                        "imdb_id", "tmdb_id"
                    ):
                        if not existing.get(field) and r.get(field):
                            existing[field] = r[field]

                    if r["source"] not in existing["sources"]:
                        existing["sources"].append(r["source"])

        final = []
        for item in merged.values():
            item["completeness"] = self._calculate_completeness(item)
            final.append(item)

        return final

    def _calculate_completeness(self, data: Dict) -> int:
        fields = ("title", "year", "poster", "rating", "overview")
        return sum(20 for f in fields if data.get(f))

    # -------------------------------------------------
    # DETAILS FETCHERS
    # -------------------------------------------------

    def _get_tmdb_details(self, tmdb_id: str) -> Dict:
        try:
            url = f"https://api.themoviedb.org/3/tv/{tmdb_id}"
            params = {"api_key": self.tmdb_key}
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            d = r.json()

            return {
                "title": d.get("name"),
                "year": d.get("first_air_date", "")[:4] or None,
                "genre": ", ".join(g["name"] for g in d.get("genres", [])),
                "rating": d.get("vote_average"),
                "plot": d.get("overview"),
                "poster": (
                    f"https://image.tmdb.org/t/p/w500{d['poster_path']}"
                    if d.get("poster_path") else None
                ),
                "type": "tv series",
            }
        except Exception as e:
            logger.error(f"TMDB details error: {e}")
            return {}

    def _get_imdb_details(self, imdb_numeric_id: str) -> Dict:
        try:
            from imdb import Cinemagoer
            ia = Cinemagoer()
            movie = ia.get_movie(imdb_numeric_id)

            return {
                "title": movie.get("title"),
                "year": movie.get("year"),
                "genre": ", ".join(movie.get("genres", [])) or None,
                "rating": movie.get("rating"),
                "plot": (
                    movie.get("plot outline")
                    or (movie.get("plot", [""])[0] if movie.get("plot") else None)
                ),
                "poster": movie.get("full-size cover url"),
                "type": movie.get("kind"),
            }
        except Exception as e:
            logger.error(f"IMDb details error: {e}")
            return {}

    def _get_omdb_details(self, imdb_id: str) -> Dict:
        try:
            url = "http://www.omdbapi.com/"
            params = {
                "apikey": self.omdb_key,
                "i": imdb_id,
                "plot": "full",
            }
            r = requests.get(url, params=params, timeout=10)
            d = r.json()

            return {
                "title": d.get("Title"),
                "year": d.get("Year", "").split("–")[0],
                "genre": d.get("Genre"),
                "rating": d.get("imdbRating"),
                "plot": d.get("Plot"),
                "poster": d.get("Poster") if d.get("Poster") != "N/A" else None,
                "type": d.get("Type"),
            }
        except Exception as e:
            logger.error(f"OMDB details error: {e}")
            return {}


# -------------------------------------------------
# GLOBAL HELPERS
# -------------------------------------------------

def search_series(query: str, tmdb_key=None, omdb_key=None):
    return SeriesAPI(tmdb_key, omdb_key).search_series(query)


def get_series_details(series_id: str, tmdb_key=None, omdb_key=None):
    return SeriesAPI(tmdb_key, omdb_key).get_series_details(series_id)
