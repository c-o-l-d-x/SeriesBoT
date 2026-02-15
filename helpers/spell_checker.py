"""
Spell Checker Module for Series Bot
Provides intelligent spell correction and series name matching
"""

from typing import List, Dict, Optional, Tuple
import re
from difflib import SequenceMatcher
import logging

logger = logging.getLogger(__name__)


class SeriesSpellChecker:
    """
    Intelligent spell checker for series names with fuzzy matching
    """
    
    def __init__(self):
        # Common misspellings and their corrections (expandable)
        self.common_corrections = {
            'stanger': 'stranger',
            'breking': 'breaking',
            'peecmaker': 'peacemaker',
            'walkng': 'walking',
            'ofice': 'office',
            'freinds': 'friends',
            'simpsns': 'simpsons',
            'comunity': 'community',
        }
        
        # Words that indicate non-series queries (ignore these messages)
        self.ignore_keywords = [
            'hi', 'hello', 'hey', 'hii', 'helo', 
            'thanks', 'thank', 'thx', 'thnx',
            'ok', 'okay', 'k',
            'yes', 'no', 'yup', 'nope',
            'good', 'bad', 'nice', 'cool',
            'how', 'what', 'when', 'where', 'why',
            'please', 'pls', 'plz',
            'send', 'give', 'want', 'need',
            'link', 'file', 'movie',
            'admin', 'owner', 'support',
        ]
    
    def should_ignore(self, query: str) -> bool:
        """
        Check if the message should be ignored (not a series search)
        
        Args:
            query: User input text
            
        Returns:
            True if message should be ignored
        """
        if not query or len(query.strip()) < 2:
            return True
        
        # Convert to lowercase for checking
        lower_query = query.lower().strip()
        
        # Check if it's just a greeting or common word
        if lower_query in self.ignore_keywords:
            return True
        
        # Check if message is too short (likely not a series name)
        words = lower_query.split()
        if len(words) == 1 and len(words[0]) < 3:
            return True
        
        # Check for common chat patterns
        chat_patterns = [
            r'^hi+$',  # hi, hii, hiii
            r'^hey+$',  # hey, heyy
            r'^ok+$',  # ok, okk, okkk
            r'^thanks?$',
            r'^\?+$',  # just question marks
            r'^!+$',  # just exclamation marks
        ]
        
        for pattern in chat_patterns:
            if re.match(pattern, lower_query):
                return True
        
        return False
    
    def clean_query(self, query: str) -> str:
        """
        Clean and normalize the search query
        
        Args:
            query: Raw user input
            
        Returns:
            Cleaned query string
        """
        # Remove extra whitespace
        query = ' '.join(query.split())
        
        # Remove special characters but keep alphanumeric and spaces
        query = re.sub(r'[^\w\s]', '', query)
        
        return query.strip()
    
    def apply_common_corrections(self, query: str) -> str:
        """
        Apply common spelling corrections
        
        Args:
            query: User query
            
        Returns:
            Corrected query
        """
        words = query.lower().split()
        corrected_words = []
        
        for word in words:
            # Check if word has a known correction
            if word in self.common_corrections:
                corrected_words.append(self.common_corrections[word])
            else:
                corrected_words.append(word)
        
        return ' '.join(corrected_words)
    
    def calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate similarity ratio between two strings
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Similarity ratio (0.0 to 1.0)
        """
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
    
    def fuzzy_match_series(
        self, 
        query: str, 
        available_series: List[Dict]
    ) -> Optional[Tuple[Dict, float]]:
        """
        Find the best matching series from available series using fuzzy matching
        
        Args:
            query: User search query
            available_series: List of series dicts with 'title' field
            
        Returns:
            Tuple of (best_match_series, similarity_score) or None
        """
        if not available_series:
            return None
        
        query_clean = self.clean_query(query).lower()
        best_match = None
        best_score = 0.0
        
        for series in available_series:
            title = series.get('title', '').lower()
            
            # Calculate direct similarity
            score = self.calculate_similarity(query_clean, title)
            
            # Bonus for exact word matches
            query_words = set(query_clean.split())
            title_words = set(title.split())
            word_match_ratio = len(query_words & title_words) / max(len(query_words), 1)
            
            # Combined score with word match bonus
            final_score = (score * 0.7) + (word_match_ratio * 0.3)
            
            if final_score > best_score:
                best_score = final_score
                best_match = series
        
        # Only return if similarity is above threshold (60%)
        if best_score >= 0.6:
            return (best_match, best_score)
        
        return None
    
    def correct_and_match(
        self, 
        query: str, 
        available_series: List[Dict],
        confidence_threshold: float = 0.75
    ) -> Tuple[Optional[str], Optional[Dict], float]:
        """
        Main method: Correct spelling and find best match
        
        Args:
            query: User input
            available_series: List of available series
            confidence_threshold: Minimum confidence for auto-selection
            
        Returns:
            Tuple of (corrected_query, matched_series, confidence_score)
        """
        # Check if should ignore
        if self.should_ignore(query):
            return (None, None, 0.0)
        
        # Clean the query
        cleaned = self.clean_query(query)
        
        # Apply common corrections
        corrected = self.apply_common_corrections(cleaned)
        
        # Try fuzzy matching
        match_result = self.fuzzy_match_series(corrected, available_series)
        
        if match_result:
            matched_series, score = match_result
            return (corrected, matched_series, score)
        
        return (corrected, None, 0.0)


# Global instance
spell_checker = SeriesSpellChecker()


def check_series_spelling(
    query: str, 
    available_series: List[Dict]
) -> Tuple[bool, Optional[str], Optional[Dict], float]:
    """
    Convenience function to check spelling and match series
    
    Args:
        query: User search query
        available_series: List of available series from database
        
    Returns:
        Tuple of (should_respond, corrected_query, matched_series, confidence)
    """
    corrected, matched, confidence = spell_checker.correct_and_match(
        query, 
        available_series
    )
    
    # Don't respond if query should be ignored
    if corrected is None:
        return (False, None, None, 0.0)
    
    return (True, corrected, matched, confidence)
