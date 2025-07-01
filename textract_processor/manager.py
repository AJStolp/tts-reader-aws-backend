"""
Content extraction manager that orchestrates different extraction methods for TTS
"""
import time
import logging
from typing import List, Tuple, Optional
from .config import ExtractionMethod, ContentType, METHOD_SCORES
from .models import ExtractionResult, ExtractionAttempt
from .extractors import TextractExtractor, DOMExtractor
from .utils import URLValidator, ContentTypeDetector

logger = logging.getLogger(__name__)

class ContentExtractorManager:
    """Manager class for orchestrating TTS-optimized content extraction"""
    
    def __init__(self, textract_client=None, config=None):
        self.textract_extractor = TextractExtractor(textract_client, config) if textract_client else None
        self.dom_extractor = DOMExtractor(config)
        self.config = config
        self.extraction_history: List[ExtractionAttempt] = []
    
    async def extract_content(self, url: str, prefer_textract: bool = True) -> Tuple[str, str]:
        """
        Main extraction method with intelligent fallback strategy for TTS
        
        Args:
            url (str): The webpage URL to process
            prefer_textract (bool): Whether to try Textract first
            
        Returns:
            Tuple[str, str]: (extracted_text, extraction_method)
        """
        if not url or not isinstance(url, str):
            raise ValueError("A valid URL string is required")
        
        if not await URLValidator.is_valid_url(url):
            raise ValueError("Invalid URL format")
        
        logger.info(f"Starting intelligent TTS content extraction for: {url}")
        start_time = time.time()
        
        # Detect content type for optimization
        content_type = ContentTypeDetector.detect_from_url(url)
        
        extraction_results = []
        
        # Try Textract first if available and preferred
        if prefer_textract and self.textract_extractor:
            logger.info("Attempting Textract extraction for TTS...")
            textract_result = await self.textract_extractor.extract(url)
            if textract_result:
                extraction_results.append(textract_result)
                self._log_attempt(ExtractionMethod.TEXTRACT, True, textract_result)
            else:
                self._log_attempt(ExtractionMethod.TEXTRACT, False, error="Textract extraction failed")
        
        # Try DOM extraction
        logger.info("Attempting DOM extraction for TTS...")
        dom_result = await self.dom_extractor.extract(url)
        if dom_result:
            extraction_results.append(dom_result)
            self._log_attempt(dom_result.method, True, dom_result)
        else:
            self._log_attempt(ExtractionMethod.DOM_FALLBACK, False, error="All DOM methods failed")
        
        # Select the best result for TTS
        if extraction_results:
            best_result = self._select_best_result(extraction_results)
            
            total_time = time.time() - start_time
            logger.info(
                f"TTS content extraction completed in {total_time:.2f}s. "
                f"Method: {best_result.method.value}, "
                f"Confidence: {best_result.confidence:.2f}, "
                f"TTS Score: {best_result.tts_suitability_score:.2f}, "
                f"Length: {best_result.char_count} chars"
            )
            
            return best_result.text, best_result.method.value
        
        # If all methods fail
        logger.error(f"All extraction methods failed for URL: {url}")
        self._log_attempt(ExtractionMethod.DOM_FALLBACK, False, error="All extraction methods failed")
        raise Exception("Unable to extract TTS content using any available method")
    
    def _select_best_result(self, results: List[ExtractionResult]) -> ExtractionResult:
        """Select the best extraction result based on TTS suitability"""
        if len(results) == 1:
            return results[0]
        
        # Score each result for TTS suitability
        scored_results = []
        
        for result in results:
            score = 0
            
            # Base TTS suitability score (most important factor)
            score += result.tts_suitability_score * 100
            
            # Method-based scoring for TTS
            score += METHOD_SCORES.get(result.method, 0)
            
            # Bonus for high-quality content markers
            if result.is_high_quality:
                score += 20
            
            # Bonus for reasonable text length for TTS
            if 500 <= result.char_count <= 50000:
                score += 15
            elif 200 <= result.char_count <= 100000:
                score += 10
            
            # Bonus for content types that work well with TTS
            content_type_bonuses = {
                ContentType.ARTICLE: 15,
                ContentType.BLOG_POST: 12,
                ContentType.NEWS: 10,
                ContentType.DOCUMENTATION: 8,
                ContentType.UNKNOWN: 0,
                ContentType.E_COMMERCE: -5,
                ContentType.SOCIAL_MEDIA: -10,
                ContentType.FORUM: -5
            }
            score += content_type_bonuses.get(result.content_type, 0)
            
            # Penalty for very fast processing (might indicate shallow extraction)
            if result.processing_time < 1.0:
                score -= 10
            
            scored_results.append((result, score))
        
        # Sort by score and return the best for TTS
        scored_results.sort(key=lambda x: x[1], reverse=True)
        best_result = scored_results[0][0]
        
        logger.info(f"Selected extraction method for TTS: {best_result.method.value} "
                   f"(confidence: {best_result.confidence:.2f}, "
                   f"TTS score: {best_result.tts_suitability_score:.2f})")
        
        return best_result
    
    def _log_attempt(self, method: ExtractionMethod, success: bool, result: ExtractionResult = None, error: str = None):
        """Log extraction attempt for analytics and debugging"""
        attempt = ExtractionAttempt(
            method=method,
            success=success,
            result=result,
            error=error
        )
        
        self.extraction_history.append(attempt)
        
        # Keep only last 100 attempts to prevent memory issues
        if len(self.extraction_history) > 100:
            self.extraction_history = self.extraction_history[-50:]
    
    def get_extraction_analytics(self) -> dict:
        """Get analytics about extraction performance"""
        if not self.extraction_history:
            return {"total_attempts": 0, "success_rate": 0}
        
        successful_attempts = [a for a in self.extraction_history if a.success]
        
        method_stats = {}
        for attempt in self.extraction_history:
            method = attempt.method.value
            if method not in method_stats:
                method_stats[method] = {"total": 0, "successful": 0}
            method_stats[method]["total"] += 1
            if attempt.success:
                method_stats[method]["successful"] += 1
        
        avg_confidence = 0
        avg_tts_score = 0
        if successful_attempts:
            confidences = [a.result.confidence for a in successful_attempts if a.result]
            tts_scores = [a.result.tts_suitability_score for a in successful_attempts if a.result]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            avg_tts_score = sum(tts_scores) / len(tts_scores) if tts_scores else 0
        
        return {
            "total_attempts": len(self.extraction_history),
            "successful_attempts": len(successful_attempts),
            "success_rate": len(successful_attempts) / len(self.extraction_history),
            "method_stats": method_stats,
            "average_confidence": avg_confidence,
            "average_tts_score": avg_tts_score,
            "service_optimized_for": "TTS Reading"
        }
    
    async def extract_with_preview(self, url: str) -> dict:
        """Extract content and return preview without full processing"""
        try:
            # Use DOM extraction for quick preview
            result = await self.dom_extractor.extract(url)
            
            if not result:
                raise Exception("Could not generate preview")
            
            # Create preview (first 500 characters)
            preview = result.text[:500]
            if len(result.text) > 500:
                preview += "..."
            
            return {
                "preview": preview,
                "estimated_length": result.char_count,
                "confidence": result.confidence,
                "tts_score": result.tts_suitability_score,
                "method": result.method.value,
                "content_type": result.content_type.value,
                "word_count": result.word_count,
                "full_available": True,
                "optimized_for_tts": True
            }
            
        except Exception as e:
            logger.error(f"Preview extraction failed for {url}: {str(e)}")
            raise Exception("Failed to generate content preview")
    
    def get_health_status(self) -> dict:
        """Get health status of extraction components"""
        status = {
            "textract_available": self.textract_extractor is not None,
            "dom_extraction_available": True,  # Always available
            "recent_success_rate": 0,
            "status": "healthy",
            "service_type": "TTS Content Extraction"
        }
        
        # Calculate recent success rate (last 10 attempts)
        recent_attempts = self.extraction_history[-10:] if len(self.extraction_history) >= 10 else self.extraction_history
        if recent_attempts:
            recent_successful = sum(1 for a in recent_attempts if a.success)
            status["recent_success_rate"] = recent_successful / len(recent_attempts)
            
            if status["recent_success_rate"] < 0.5:
                status["status"] = "degraded"
        
        return status