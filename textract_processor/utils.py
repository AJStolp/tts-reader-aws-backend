"""
Utility functions for TTS content extraction and processing
"""
import re
import logging
from urllib.parse import urlparse
from typing import List, Tuple
from .config import ContentType

logger = logging.getLogger(__name__)

class URLValidator:
    """Utility class for URL validation and analysis"""
    
    @staticmethod
    async def is_valid_url(url: str) -> bool:
        """Enhanced URL validation for web content extraction"""
        try:
            parsed = urlparse(url)
            
            # Allow localhost URLs for development
            is_localhost = parsed.netloc.startswith('localhost') or parsed.netloc.startswith('127.0.0.1')
            
            return all([
                parsed.scheme in ('http', 'https'),
                parsed.netloc,
                len(parsed.netloc) > 3,
                '.' in parsed.netloc or is_localhost  # Allow localhost URLs
            ])
        except Exception:
            return False
    
    @staticmethod
    def get_domain(url: str) -> str:
        """Extract domain from URL"""
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return ""
    
    @staticmethod
    def is_social_media(url: str) -> bool:
        """Check if URL is from a social media platform"""
        social_domains = [
            'twitter.com', 'facebook.com', 'linkedin.com', 
            'instagram.com', 'youtube.com', 'tiktok.com'
        ]
        domain = URLValidator.get_domain(url)
        return any(social in domain for social in social_domains)

class ContentTypeDetector:
    """Utility class for detecting content types from webpage analysis"""
    
    @staticmethod
    def detect_from_url(url: str) -> ContentType:
        """Detect content type from URL patterns"""
        url_lower = url.lower()
        
        # Article indicators
        if any(word in url_lower for word in ['/article/', '/story/', '/news/']):
            return ContentType.ARTICLE
        
        # Blog indicators
        if any(word in url_lower for word in ['/blog/', '/post/', '/posts/']):
            return ContentType.BLOG_POST
        
        # Documentation indicators
        if any(word in url_lower for word in ['/docs/', '/documentation/', '/wiki/', '/help/']):
            return ContentType.DOCUMENTATION
        
        # E-commerce indicators
        if any(word in url_lower for word in ['/product/', '/shop/', '/store/']):
            return ContentType.E_COMMERCE
        
        # Forum indicators
        if any(word in url_lower for word in ['/forum/', '/thread/', '/topic/']):
            return ContentType.FORUM
        
        # Social media
        if URLValidator.is_social_media(url):
            return ContentType.SOCIAL_MEDIA
        
        return ContentType.UNKNOWN
    
    @staticmethod
    def detect_from_metadata(title: str, meta_description: str, schema_types: List[str]) -> ContentType:
        """Detect content type from page metadata"""
        # Check schema.org structured data
        if 'Article' in schema_types:
            return ContentType.ARTICLE
        
        if 'BlogPosting' in schema_types:
            return ContentType.BLOG_POST
        
        if 'Product' in schema_types:
            return ContentType.E_COMMERCE
        
        # Check title and description
        title_desc = f"{title} {meta_description}".lower()
        
        if any(word in title_desc for word in ['article', 'story', 'news']):
            return ContentType.ARTICLE
        
        if any(word in title_desc for word in ['blog', 'post']):
            return ContentType.BLOG_POST
        
        return ContentType.UNKNOWN

class TextCleaner:
    """Utility class for cleaning and optimizing text for TTS"""
    
    @staticmethod
    def clean_for_tts(text: str) -> str:
        """Enhanced text cleaning and normalization for TTS reading"""
        if not text:
            return ""
        
        # Normalize whitespace for better TTS flow
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        # Remove excessive punctuation that disrupts TTS
        text = re.sub(r'[.]{3,}', '...', text)
        text = re.sub(r'[-]{3,}', '---', text)
        text = re.sub(r'[_]{3,}', '', text)
        
        # Remove common web artifacts that interfere with TTS
        web_artifacts = [
            r'Cookie Policy\s*', r'Accept Cookies\s*', r'Privacy Policy\s*',
            r'Terms of Service\s*', r'Subscribe to Newsletter\s*',
            r'Follow us on\s*', r'Share this article\s*', r'Print this page\s*',
            r'Read more\s*', r'Continue reading\s*', r'Click here\s*',
            r'Skip to content\s*', r'Jump to navigation\s*', r'Show more\s*',
            r'Load more\s*', r'View all\s*'
        ]
        
        for artifact in web_artifacts:
            text = re.sub(artifact, '', text, flags=re.IGNORECASE)
        
        # Remove URLs and email addresses (not suitable for TTS)
        text = re.sub(r'https?://[^\s]+', '', text)
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', text)
        
        # Remove social media handles (not suitable for TTS)
        text = re.sub(r'@\w+', '', text)
        text = re.sub(r'#\w+', '', text)
        
        # Convert excessive capitalization to proper case for better TTS
        text = re.sub(r'\b[A-Z]{4,}\b', lambda m: m.group().capitalize(), text)
        
        # Clean up spacing after removals
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        return text.strip()
    
    @staticmethod
    def filter_navigation_content(body_text: str) -> str:
        """Filter body content to remove navigation and metadata for TTS"""
        if not body_text:
            return ""
        
        lines = body_text.split('\n')
        filtered_lines = []
        
        for line in lines:
            line = line.strip()
            if not line or len(line) < 20:
                continue
            
            # Skip lines that look like navigation or metadata (bad for TTS)
            navigation_keywords = [
                'home', 'about', 'contact', 'menu', 'login', 'register',
                'privacy', 'terms', 'copyright', '©', 'all rights reserved',
                'follow us', 'subscribe', 'newsletter', 'cookies', 'gdpr',
                'skip to', 'jump to', 'accessibility'
            ]
            
            if any(keyword in line.lower() for keyword in navigation_keywords):
                continue
            
            # Skip lines with high punctuation density
            if len(line) > 0:
                punct_density = (line.count('|') + line.count('•') + 
                               line.count('→') + line.count('»')) / len(line)
                if punct_density > 0.2:
                    continue
            
            # Skip lines that are mostly uppercase (likely headings or navigation)
            if len(line) > 10 and line.isupper():
                continue
            
            filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)
    
    @staticmethod
    def calculate_readability_metrics(text: str) -> dict:
        """Calculate basic readability metrics for TTS optimization"""
        if not text:
            return {"words": 0, "sentences": 0, "characters": 0, "avg_word_length": 0}
        
        words = text.split()
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return {
            "words": len(words),
            "sentences": len(sentences),
            "characters": len(text),
            "avg_word_length": sum(len(word) for word in words) / max(len(words), 1),
            "avg_sentence_length": len(words) / max(len(sentences), 1)
        }

class ContentAnalyzer:
    """Utility class for analyzing content quality for TTS"""
    
    @staticmethod
    def calculate_link_density(text: str, link_text: str) -> float:
        """Calculate the ratio of link text to total text"""
        if not text:
            return 1.0
        return len(link_text) / len(text)
    
    @staticmethod
    def is_likely_navigation(text: str, class_id: str = "") -> bool:
        """Determine if text content is likely navigation (bad for TTS)"""
        if len(text) < 20:
            return True
        
        # Check for navigation indicators in class/id
        nav_indicators = [
            'nav', 'navigation', 'menu', 'sidebar', 'header', 'footer',
            'breadcrumb', 'pagination', 'widget', 'toolbar'
        ]
        
        class_id_lower = class_id.lower()
        if any(indicator in class_id_lower for indicator in nav_indicators):
            return True
        
        # Check text content patterns
        nav_patterns = [
            r'^(home|about|contact|menu|login|register)$',
            r'^\s*(previous|next|back|forward)\s*$',
            r'^\s*page \d+ of \d+\s*$'
        ]
        
        text_lower = text.lower().strip()
        return any(re.match(pattern, text_lower) for pattern in nav_patterns)
    
    @staticmethod
    def estimate_reading_time(text: str, wpm: int = 200) -> int:
        """Estimate reading time in minutes for TTS planning"""
        if not text:
            return 0
        
        word_count = len(text.split())
        return max(1, round(word_count / wpm))
    
    @staticmethod
    def score_content_quality(text: str, method: str) -> float:
        """Score content quality for TTS suitability (0-1)"""
        if not text:
            return 0.0
        
        metrics = TextCleaner.calculate_readability_metrics(text)
        score = 0.5  # Base score
        
        # Length scoring
        if 500 <= metrics["characters"] <= 50000:
            score += 0.2
        elif metrics["characters"] < 200:
            score -= 0.3
        
        # Word length scoring (shorter words are better for TTS)
        if 3 <= metrics["avg_word_length"] <= 6:
            score += 0.1
        
        # Sentence length scoring (moderate length is best for TTS)
        if 10 <= metrics["avg_sentence_length"] <= 25:
            score += 0.1
        
        # Method-based scoring
        method_bonuses = {
            "textract": 0.1,
            "dom_semantic": 0.05,
            "dom_heuristic": 0.0,
            "reader_mode": -0.05,
            "dom_fallback": -0.1
        }
        score += method_bonuses.get(method, 0)
        
        return min(1.0, max(0.0, score))