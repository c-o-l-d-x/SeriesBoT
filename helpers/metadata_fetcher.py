import aiohttp
import asyncio
from typing import Dict, List
from info import TMDB_API_KEY, OMDB_API_KEY

class MetadataFetcher:
    
    def __init__(self):
        self.tmdb_api_key = TMDB_API_KEY
        self.omdb_api_key = OMDB_API_KEY
        self.cache = {}  # Cache to store fetched metadata
        
        # TMDB TV Genre ID to Name mapping
        self.tmdb_genres = {
            10759: "Action & Adventure",
            16: "Animation",
            35: "Comedy",
            80: "Crime",
            99: "Documentary",
            18: "Drama",
            10751: "Family",
            10762: "Kids",
            9648: "Mystery",
            10763: "News",
            10764: "Reality",
            10765: "Sci-Fi & Fantasy",
            10766: "Soap",
            10767: "Talk",
            10768: "War & Politics",
            37: "Western"
        }
        
    async def search_tmdb(self, query: str) -> List[Dict]:
        """Search TMDB for TV series only (no movies)"""
        results = []
        try:
            url = f"https://api.themoviedb.org/3/search/tv"
            params = {"api_key": self.tmdb_api_key, "query": query}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        for item in data.get('results', [])[:5]:
                            tmdb_id = str(item.get('id', ''))
                            
                            # Convert genre IDs to genre names
                            genre_ids = item.get('genre_ids', [])
                            genre_names = [self.tmdb_genres.get(gid, '') for gid in genre_ids[:3]]
                            genre_names = [g for g in genre_names if g]  # Remove empty strings
                            genre_string = ', '.join(genre_names) if genre_names else ''
                            
                            results.append({
                                'id': f"tmdb_{tmdb_id}",
                                'source': 'TMDB',
                                'title': item.get('name', ''),
                                'year': item.get('first_air_date', '')[:4] if item.get('first_air_date') else '',
                                'poster': f"https://image.tmdb.org/t/p/w500{item['poster_path']}" if item.get('poster_path') else '',
                                'genre': genre_string,
                                'rating': str(item.get('vote_average', '')),
                                'overview': item.get('overview', '')
                            })
        except Exception as e:
            print(f"TMDB search error: {e}")
        return results
    
    async def search_omdb(self, query: str) -> List[Dict]:
        """Search OMDB for TV series and mini-series only (no movies)"""
        results = []
        try:
            url = "http://www.omdbapi.com/"
            params = {"apikey": self.omdb_api_key, "s": query, "type": "series"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('Response') == 'True':
                            for item in data.get('Search', [])[:3]:
                                imdb_id = item.get('imdbID', '')
                                detail_params = {"apikey": self.omdb_api_key, "i": imdb_id}
                                async with session.get(url, params=detail_params) as detail_response:
                                    if detail_response.status == 200:
                                        d = await detail_response.json()
                                        
                                        # Only include if Type is "series" (TV Series or Mini-Series)
                                        item_type = d.get('Type', '').lower()
                                        if item_type == 'series':
                                            results.append({
                                                'id': f"omdb_{imdb_id}",
                                                'source': 'OMDB',
                                                'title': d.get('Title', ''),
                                                'year': d.get('Year', '').split('–')[0] if d.get('Year') else '',
                                                'poster': d.get('Poster', '') if d.get('Poster') != 'N/A' else '',
                                                'genre': d.get('Genre', ''),
                                                'rating': d.get('imdbRating', ''),
                                                'overview': d.get('Plot', '')
                                            })
        except Exception as e:
            print(f"OMDB search error: {e}")
        return results
    
    async def search_all(self, query: str) -> List[Dict]:
        """Search all sources and return TV series/mini-series results only with completeness calculated"""
        tmdb_results, omdb_results = await asyncio.gather(
            self.search_tmdb(query), 
            self.search_omdb(query),
            return_exceptions=True
        )
        
        if isinstance(tmdb_results, Exception): 
            tmdb_results = []
        if isinstance(omdb_results, Exception): 
            omdb_results = []
        
        all_results = []
        seen = set()
        
        # Combine results and avoid duplicates
        for result in tmdb_results + omdb_results:
            key = f"{result['title']}_{result['year']}"
            if key not in seen:
                seen.add(key)
                # Calculate completeness percentage
                result['completeness'] = self.calculate_completeness(result)
                # Store in cache for later retrieval
                self.cache[result['id']] = result
                all_results.append(result)
        
        # Sort by completeness (highest first)
        all_results.sort(key=lambda x: x['completeness'], reverse=True)
        return all_results[:10]
    
    def calculate_completeness(self, metadata: Dict) -> int:
        """Calculate how complete the metadata is (0-100%)"""
        score = 0
        if metadata.get('poster') and metadata['poster'] not in ['', 'N/A']: 
            score += 20
        if metadata.get('title'): 
            score += 20
        if metadata.get('year'): 
            score += 20
        if metadata.get('genre') and metadata['genre'] not in ['', 'N/A']: 
            score += 20
        if metadata.get('rating') and metadata['rating'] not in ['', 'N/A', '0']: 
            score += 20
        return score
    
    def format_button(self, metadata: Dict) -> str:
        """Format button text with title, year, and completeness%"""
        title = metadata.get('title', 'Unknown')
        year = metadata.get('year', 'Unknown')
        comp = metadata.get('completeness', 0)
        
        # If 100% complete, don't show percentage
        if comp == 100:
            return f"{title} ({year})"
        else:
            # Show percentage to identify incomplete metadata
            return f"{title} ({year}) - {comp}%"
    
    async def fetch_metadata(self, result_id: str) -> Dict:
        """Fetch full metadata from cache"""
        return self.cache.get(result_id, {})

metadata_fetcher = MetadataFetcher()
