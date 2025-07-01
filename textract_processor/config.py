"""
Configuration and constants for TTS content extraction
"""
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List

class ExtractionMethod(Enum):
    """Enumeration of available extraction methods"""
    TEXTRACT = "textract"
    DOM_SEMANTIC = "dom_semantic"
    DOM_HEURISTIC = "dom_heuristic"
    DOM_FALLBACK = "dom_fallback"
    READER_MODE = "reader_mode"

class ContentType(Enum):
    """Enumeration of detected content types"""
    ARTICLE = "article"
    BLOG_POST = "blog_post"
    NEWS = "news"
    DOCUMENTATION = "documentation"
    E_COMMERCE = "e_commerce"
    SOCIAL_MEDIA = "social_media"
    FORUM = "forum"
    UNKNOWN = "unknown"

@dataclass
class ExtractionConfig:
    """Configuration settings for content extraction"""
    # AWS Textract limits and timeouts
    max_pdf_size: int = 10 * 1024 * 1024  # 10MB
    textract_timeout: int = 45  # seconds
    
    # Page loading settings
    page_load_timeout: int = 30000  # 30 seconds
    content_load_wait: int = 3000   # 3 seconds
    
    # Quality thresholds
    min_text_length: int = 100
    max_retries: int = 3
    retry_delay: int = 2  # seconds
    
    # User agents for rotation
    user_agents: List[str] = None
    
    # Content selectors with priority scoring
    content_selectors: Dict[str, int] = None
    
    # Elements to exclude for TTS optimization
    exclude_selectors: List[str] = None
    
    def __post_init__(self):
        if self.user_agents is None:
            self.user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
        
        if self.content_selectors is None:
            self.content_selectors = {
                # Semantic selectors (highest priority)
                'main': 10,
                'article': 10,
                '[role="main"]': 10,
                '[role="article"]': 10,
                
                # Content-specific selectors
                '.article-content': 9,
                '.post-content': 9,
                '.entry-content': 9,
                '.content-body': 9,
                '.article-body': 9,
                '.main-content': 8,
                '.page-content': 8,
                '.content': 7,
                
                # ID-based selectors
                '#main-content': 8,
                '#article-content': 8,
                '#content': 7,
                '#main': 8,
                
                # News/blog specific
                '.story-body': 9,
                '.article-text': 9,
                '.post-body': 8,
                '.entry-text': 8,
                
                # Documentation specific
                '.documentation': 8,
                '.docs-content': 8,
                '.wiki-content': 8,
            }
        
        if self.exclude_selectors is None:
            self.exclude_selectors = [
                'nav', 'header', 'footer', 'aside', '.sidebar', '.navigation',
                '.menu', '.nav', '.header', '.footer', '.advertisement', '.ad',
                '.social', '.share', '.related', '.comments', '.pagination',
                '.breadcrumb', '.widget', '.toolbar', '.banner', '.popup',
                '.modal', '.overlay', '[class*="cookie"]', '[class*="gdpr"]',
                '.skip-link', '.screen-reader-text', '.visually-hidden'
            ]

# Global configuration instance
DEFAULT_CONFIG = ExtractionConfig()

# Method scoring for TTS suitability
METHOD_SCORES = {
    ExtractionMethod.TEXTRACT: 30,
    ExtractionMethod.DOM_SEMANTIC: 25,
    ExtractionMethod.DOM_HEURISTIC: 20,
    ExtractionMethod.READER_MODE: 15,
    ExtractionMethod.DOM_FALLBACK: 5
}

# Confidence mapping for extraction methods
CONFIDENCE_MAPPING = {
    "textract": 0.9,
    "dom_semantic": 0.8,
    "dom_heuristic": 0.7,
    "reader_mode": 0.6,
    "dom_fallback": 0.4
}