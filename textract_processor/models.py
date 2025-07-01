"""
Data models for TTS content extraction
"""
from dataclasses import dataclass
from typing import Dict, Any
from datetime import datetime, timezone
from .config import ExtractionMethod, ContentType

@dataclass
class ExtractionResult:
    """Result of content extraction with metadata optimized for TTS"""
    text: str
    method: ExtractionMethod
    content_type: ContentType
    confidence: float
    word_count: int
    char_count: int
    processing_time: float
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for API responses"""
        return {
            "text": self.text,
            "method": self.method.value,
            "content_type": self.content_type.value,
            "confidence": self.confidence,
            "word_count": self.word_count,
            "char_count": self.char_count,
            "processing_time": self.processing_time,
            "metadata": self.metadata,
            "tts_optimized": True
        }
    
    @property
    def is_high_quality(self) -> bool:
        """Check if extraction meets high quality standards for TTS"""
        return (
            self.confidence >= 0.7 and
            self.char_count >= 200 and
            self.word_count >= 50 and
            4 <= (self.char_count / max(self.word_count, 1)) <= 8
        )
    
    @property
    def tts_suitability_score(self) -> float:
        """Calculate suitability score for TTS conversion (0-1)"""
        base_score = self.confidence
        
        # Bonus for good length
        if 500 <= self.char_count <= 50000:
            base_score += 0.1
        elif self.char_count < 200:
            base_score -= 0.2
        
        # Bonus for good word-to-char ratio
        if self.word_count > 0:
            ratio = self.char_count / self.word_count
            if 4 <= ratio <= 8:
                base_score += 0.1
        
        return min(1.0, max(0.0, base_score))

@dataclass
class PageAnalysis:
    """Analysis of webpage structure and content for TTS optimization"""
    url: str
    title: str
    content_type: ContentType
    has_semantic_markup: bool
    link_density: float
    text_to_markup_ratio: float
    estimated_reading_time: int  # minutes
    language: str = "en"
    
    @property
    def is_tts_friendly(self) -> bool:
        """Determine if page structure is friendly for TTS extraction"""
        return (
            self.has_semantic_markup or
            self.link_density < 0.3 or
            self.text_to_markup_ratio > 0.6
        )

@dataclass
class ExtractionAttempt:
    """Record of a single extraction attempt"""
    method: ExtractionMethod
    success: bool
    result: ExtractionResult = None
    error: str = None
    attempt_time: datetime = None
    
    def __post_init__(self):
        if self.attempt_time is None:
            self.attempt_time = datetime.now(timezone.utc)