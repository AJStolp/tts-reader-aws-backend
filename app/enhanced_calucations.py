"""
Enhanced extraction service with highlighting integration
"""
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

from sqlalchemy.orm import Session
from fastapi import HTTPException

from .models import ExtractResponseEnhanced, ExtractionProgress
from .services import extraction_service as base_extraction_service
from textract_processor import ContentExtractorManager, ExtractionResult
from textract_processor.highlighting import (
    HighlightGenerator, HighlightMap, create_basic_highlight_map,
    optimize_text_for_highlighting
)
from models import User

logger = logging.getLogger(__name__)

class EnhancedExtractionService:
    """Enhanced extraction service with highlighting and advanced TTS features"""
    
    def __init__(self):
        self.extraction_manager = ContentExtractorManager()
        self.highlight_generator = HighlightGenerator()
        self.extraction_progress: Dict[str, List[ExtractionProgress]] = {}
        self.highlight_cache: Dict[str, HighlightMap] = {}
    
    async def extract_with_highlighting(
        self,
        url: str,
        user: User,
        db: Session,
        prefer_textract: bool = True,
        include_metadata: bool = False,
        highlighting_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Extract content with automatic highlighting generation"""
        
        extraction_id = str(uuid.uuid4())
        
        try:
            logger.info(f"Enhanced extraction with highlighting for user {user.username}: {url}")
            
            # Initialize progress
            self._update_progress(extraction_id, ExtractionProgress(
                status="starting",
                message="Initializing enhanced TTS extraction with highlighting...",
                progress=0.0
            ))
            
            # Step 1: Extract content
            self._update_progress(extraction_id, ExtractionProgress(
                status="processing",
                message="Extracting and analyzing content...",
                progress=0.2
            ))
            
            start_time = time.time()
            extracted_text, method = await self.extraction_manager.extract_content(
                url, prefer_textract=prefer_textract
            )
            
            if not extracted_text:
                raise ValueError("Could not extract content from the provided URL")
            
            text_length = len(extracted_text)
            
            # Check character limits
            if not user.deduct_characters(text_length):
                raise ValueError(f"Text length ({text_length}) exceeds remaining character limit ({user.remaining_chars})")
            
            # Step 2: Optimize text for highlighting
            self._update_progress(extraction_id, ExtractionProgress(
                status="processing",
                message="Optimizing text for TTS highlighting...",
                progress=0.4,
                method=method
            ))
            
            optimized_text = optimize_text_for_highlighting(extracted_text)
            
            # Step 3: Generate highlighting map
            self._update_progress(extraction_id, ExtractionProgress(
                status="processing",
                message="Generating highlighting map for TTS synchronization...",
                progress=0.6
            ))
            
            highlighting_opts = highlighting_options or {}
            segment_type = highlighting_opts.get("segment_type", "sentence")
            
            highlight_map = self.highlight_generator.create_highlight_map(
                optimized_text,
                extraction_method=method,
                segment_type=segment_type
            )
            
            # Step 4: Create reading chunks for long content
            self._update_progress(extraction_id, ExtractionProgress(
                status="processing",
                message="Creating optimized reading chunks...",
                progress=0.8
            ))
            
            reading_chunks = []
            if text_length > 3000:  # Create chunks for long content
                reading_chunks = self.highlight_generator.create_reading_chunks(
                    optimized_text,
                    max_chunk_size=highlighting_opts.get("chunk_size", 3000),
                    overlap_sentences=highlighting_opts.get("overlap_sentences", 1)
                )
            
            # Step 5: Validate highlighting
            validation_result = self.highlight_generator.validate_highlight_map(highlight_map)
            
            # Commit character deduction
            db.commit()
            processing_time = time.time() - start_time
            
            # Final progress update
            self._update_progress(extraction_id, ExtractionProgress(
                status="completed",
                message="Enhanced TTS extraction with highlighting completed successfully",
                progress=1.0,
                method=method
            ))
            
            # Cache the highlighting map
            cache_key = f"{url}_{method}_{hash(optimized_text)}"
            self.highlight_cache[cache_key] = highlight_map
            
            logger.info(f"Enhanced extraction completed for user {user.username}: "
                       f"{text_length} characters, {len(highlight_map.segments)} segments in {processing_time:.2f}s")
            
            # Prepare enhanced response
            response_data = {
                "text": optimized_text,
                "characters_used": text_length,
                "remaining_chars": user.remaining_chars,
                "extraction_method": method,
                "word_count": len(optimized_text.split()),
                "processing_time": processing_time,
                
                # Highlighting data
                "highlight_map": highlight_map.to_dict(),
                "reading_chunks": reading_chunks,
                "validation": validation_result,
                
                # TTS optimization info
                "tts_optimized": True,
                "segment_count": len(highlight_map.segments),
                "estimated_reading_time": highlight_map.total_duration / 1000 / 60,  # minutes
            }
            
            # Add metadata if requested
            if include_metadata:
                response_data["metadata"] = {
                    "url": url,
                    "extraction_id": extraction_id,
                    "user_id": str(user.user_id),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "prefer_textract": prefer_textract,
                    "highlighting_options": highlighting_opts,
                    "cache_key": cache_key
                }
            
            self._cleanup_progress_data()
            return response_data
            
        except Exception as e:
            logger.error(f"Enhanced extraction error for user {user.username}: {str(e)}", exc_info=True)
            
            self._update_progress(extraction_id, ExtractionProgress(
                status="failed",
                message=f"Enhanced extraction failed: {str(e)}",
                progress=1.0
            ))
            
            db.rollback()
            raise
    
    async def extract_with_speech_marks(
        self,
        url: str,
        user: User,
        db: Session,
        voice_id: str = "Joanna",
        engine: str = "neural",
        prefer_textract: bool = True
    ) -> Dict[str, Any]:
        """Extract content and generate speech marks for precise highlighting"""
        
        extraction_id = str(uuid.uuid4())
        
        try:
            logger.info(f"Extraction with speech marks for user {user.username}: {url}")
            
            # Step 1: Extract content
            self._update_progress(extraction_id, ExtractionProgress(
                status="processing",
                message="Extracting content for speech mark generation...",
                progress=0.1
            ))
            
            extracted_text, method = await self.extraction_manager.extract_content(
                url, prefer_textract=prefer_textract
            )
            
            if not extracted_text:
                raise ValueError("Could not extract content")
            
            text_length = len(extracted_text)
            
            # Check character limits (double charge for speech marks)
            required_chars = text_length * 2  # Extract + TTS synthesis
            if not user.deduct_characters(required_chars):
                raise ValueError(f"Required characters ({required_chars}) exceeds limit")
            
            # Step 2: Optimize text
            self._update_progress(extraction_id, ExtractionProgress(
                status="processing", 
                message="Optimizing text for speech synthesis...",
                progress=0.3
            ))
            
            optimized_text = optimize_text_for_highlighting(extracted_text)
            
            # Step 3: Generate speech marks using Polly
            self._update_progress(extraction_id, ExtractionProgress(
                status="processing",
                message="Generating speech marks with AWS Polly...",
                progress=0.5
            ))
            
            speech_marks_data = await self._generate_speech_marks(
                optimized_text, voice_id, engine
            )
            
            # Step 4: Create precise highlighting with speech marks
            self._update_progress(extraction_id, ExtractionProgress(
                status="processing",
                message="Creating precise highlighting with speech timing...",
                progress=0.8
            ))
            
            highlight_map = self.highlight_generator.create_highlight_map(
                optimized_text,
                speech_marks_data=speech_marks_data,
                extraction_method=f"{method}_with_speech_marks"
            )
            
            db.commit()
            
            self._update_progress(extraction_id, ExtractionProgress(
                status="completed",
                message="Speech mark extraction completed successfully",
                progress=1.0
            ))
            
            return {
                "text": optimized_text,
                "characters_used": required_chars,
                "remaining_chars": user.remaining_chars,
                "extraction_method": method,
                "highlight_map": highlight_map.to_dict(),
                "speech_marks_raw": speech_marks_data,
                "voice_used": voice_id,
                "engine_used": engine,
                "precise_timing": True
            }
            
        except Exception as e:
            logger.error(f"Speech mark extraction error: {str(e)}")
            db.rollback()
            raise
    
    async def _generate_speech_marks(
        self, 
        text: str, 
        voice_id: str, 
        engine: str
    ) -> str:
        """Generate speech marks using AWS Polly"""
        try:
            from .services import aws_service
            
            # Split text into chunks if too long
            chunks = aws_service.split_text_smart(text, 3000)
            all_marks = []
            cumulative_time = 0
            
            for chunk in chunks:
                # Generate speech marks for this chunk
                response = await asyncio.to_thread(
                    aws_service.polly.synthesize_speech,
                    Text=chunk,
                    OutputFormat="json",
                    VoiceId=voice_id,
                    Engine=engine,
                    SpeechMarkTypes=["word", "sentence"]
                )
                
                marks_text = response['AudioStream'].read().decode('utf-8')
                chunk_marks = [json.loads(line) for line in marks_text.splitlines() if line.strip()]
                
                # Adjust timing for concatenated chunks
                for mark in chunk_marks:
                    mark['time'] += cumulative_time
                    all_marks.append(mark)
                
                # Estimate chunk duration for next offset
                chunk_duration = max([mark['time'] for mark in chunk_marks], default=0) + 1000
                cumulative_time += chunk_duration
            
            # Convert back to newline-separated JSON
            return '\n'.join([json.dumps(mark) for mark in all_marks])
            
        except Exception as e:
            logger.error(f"Error generating speech marks: {str(e)}")
            raise
    
    def get_cached_highlight_map(self, cache_key: str) -> Optional[HighlightMap]:
        """Retrieve cached highlight map"""
        return self.highlight_cache.get(cache_key)
    
    def analyze_extraction_quality(self, url: str, result: ExtractionResult) -> Dict[str, Any]:
        """Analyze the quality of extracted content for TTS"""
        
        analysis = {
            "url": url,
            "extraction_method": result.method.value,
            "content_type": result.content_type.value,
            "confidence": result.confidence,
            "tts_score": result.tts_suitability_score,
            "character_count": result.char_count,
            "word_count": result.word_count,
            "processing_time": result.processing_time
        }
        
        # Add quality metrics
        if result.word_count > 0:
            analysis["avg_word_length"] = result.char_count / result.word_count
            analysis["reading_complexity"] = self._assess_reading_complexity(result.text)
        
        # Add recommendations
        recommendations = []
        if result.confidence < 0.7:
            recommendations.append("Consider trying a different extraction method")
        if result.tts_suitability_score < 0.6:
            recommendations.append("Text may need additional cleaning for optimal TTS")
        if result.char_count < 200:
            recommendations.append("Content may be too short for effective TTS")
        if result.char_count > 50000:
            recommendations.append("Consider breaking into smaller chunks for better TTS performance")
        
        analysis["recommendations"] = recommendations
        analysis["overall_grade"] = self._calculate_overall_grade(result)
        
        return analysis
    
    def _assess_reading_complexity(self, text: str) -> str:
        """Assess reading complexity for TTS optimization"""
        sentences = text.split('.')
        if not sentences:
            return "unknown"
        
        avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
        
        if avg_sentence_length < 10:
            return "simple"
        elif avg_sentence_length < 20:
            return "moderate"
        else:
            return "complex"
    
    def _calculate_overall_grade(self, result: ExtractionResult) -> str:
        """Calculate overall grade for extraction quality"""
        score = 0
        
        # Confidence scoring (40% weight)
        score += result.confidence * 0.4
        
        # TTS suitability scoring (40% weight)
        score += result.tts_suitability_score * 0.4
        
        # Length scoring (20% weight)
        if 500 <= result.char_count <= 10000:
            score += 0.2  # Ideal length
        elif 200 <= result.char_count <= 50000:
            score += 0.1  # Acceptable length
        
        # Convert to letter grade
        if score >= 0.9:
            return "A"
        elif score >= 0.8:
            return "B"
        elif score >= 0.7:
            return "C"
        elif score >= 0.6:
            return "D"
        else:
            return "F"
    
    def _update_progress(self, extraction_id: str, progress: ExtractionProgress):
        """Update extraction progress"""
        if extraction_id not in self.extraction_progress:
            self.extraction_progress[extraction_id] = []
        self.extraction_progress[extraction_id].append(progress)
    
    def _cleanup_progress_data(self):
        """Clean up old progress data"""
        if len(self.extraction_progress) > 100:
            # Keep only the latest 50
            sorted_keys = sorted(
                self.extraction_progress.keys(),
                key=lambda k: self.extraction_progress[k][-1].timestamp if self.extraction_progress[k] else datetime.min,
                reverse=True
            )
            
            keys_to_keep = sorted_keys[:50]
            keys_to_remove = [k for k in self.extraction_progress.keys() if k not in keys_to_keep]
            
            for key in keys_to_remove:
                del self.extraction_progress[key]
    
    def get_extraction_progress(self, extraction_id: str) -> Dict[str, Any]:
        """Get extraction progress"""
        if extraction_id not in self.extraction_progress:
            raise ValueError("Extraction progress not found")
        
        progress_list = self.extraction_progress[extraction_id]
        latest = progress_list[-1] if progress_list else None
        
        return {
            "extraction_id": extraction_id,
            "current_status": latest.status if latest else "unknown",
            "current_message": latest.message if latest else "No progress data",
            "progress": latest.progress if latest else 0.0,
            "method": latest.method if latest else None,
            "history": [p.dict() for p in progress_list[-5:]]
        }

class HighlightingDebugger:
    """Debug and test highlighting functionality"""
    
    def __init__(self):
        self.highlight_generator = HighlightGenerator()
    
    def test_text_processing(self, text: str) -> Dict[str, Any]:
        """Test text processing pipeline"""
        from textract_processor.highlighting import TextProcessor
        
        processor = TextProcessor()
        
        # Test normalization
        normalized = processor.normalize_text_for_highlighting(text)
        
        # Test segmentation
        sentences = processor.create_sentence_segments(normalized)
        paragraphs = processor.create_paragraph_segments(normalized)
        words = processor.extract_words_with_positions(normalized)
        
        return {
            "original_length": len(text),
            "normalized_length": len(normalized),
            "sentence_count": len(sentences),
            "paragraph_count": len(paragraphs),
            "word_count": len(words),
            "normalization_changes": text != normalized,
            "sample_sentences": sentences[:3],
            "sample_words": words[:10]
        }
    
    def test_highlight_generation(self, text: str) -> Dict[str, Any]:
        """Test highlight generation"""
        try:
            # Generate basic highlighting
            highlight_map = self.highlight_generator.create_highlight_map(
                text, extraction_method="test"
            )
            
            # Validate highlighting
            validation = self.highlight_generator.validate_highlight_map(highlight_map)
            
            # Test reading chunks
            chunks = self.highlight_generator.create_reading_chunks(text)
            
            return {
                "success": True,
                "highlight_map": highlight_map.to_dict(),
                "validation": validation,
                "chunk_count": len(chunks),
                "total_duration": highlight_map.total_duration,
                "segments": len(highlight_map.segments),
                "words": len(highlight_map.words)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def benchmark_extraction_methods(self, url: str) -> Dict[str, Any]:
        """Benchmark different extraction methods"""
        from textract_processor import ContentExtractorManager
        
        manager = ContentExtractorManager()
        results = {}
        
        # Test each method individually if possible
        methods_to_test = ["textract", "dom_semantic", "dom_heuristic", "reader_mode"]
        
        for method in methods_to_test:
            try:
                start_time = time.time()
                # This would need method-specific extraction calls
                # For now, just use the general extraction
                text, actual_method = asyncio.run(manager.extract_content(url))
                processing_time = time.time() - start_time
                
                if text:
                    highlight_test = self.test_highlight_generation(text)
                    
                    results[method] = {
                        "success": True,
                        "text_length": len(text),
                        "processing_time": processing_time,
                        "actual_method": actual_method,
                        "highlighting_success": highlight_test["success"],
                        "segment_count": highlight_test.get("segments", 0)
                    }
                else:
                    results[method] = {
                        "success": False,
                        "error": "No text extracted"
                    }
                    
            except Exception as e:
                results[method] = {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
        
        return {
            "url": url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": results,
            "best_method": self._find_best_method(results)
        }
    
    def _find_best_method(self, results: Dict[str, Any]) -> str:
        """Find the best extraction method from benchmark results"""
        successful_methods = {
            method: data for method, data in results.items() 
            if data.get("success", False)
        }
        
        if not successful_methods:
            return "none"
        
        # Score methods based on multiple factors
        scored_methods = []
        for method, data in successful_methods.items():
            score = 0
            
            # Text length score (longer is better, up to a point)
            text_len = data.get("text_length", 0)
            if 1000 <= text_len <= 10000:
                score += 3
            elif 500 <= text_len <= 50000:
                score += 2
            elif text_len > 100:
                score += 1
            
            # Speed score (faster is better)
            proc_time = data.get("processing_time", float('inf'))
            if proc_time < 5:
                score += 2
            elif proc_time < 15:
                score += 1
            
            # Highlighting success
            if data.get("highlighting_success", False):
                score += 2
            
            # Method preference (textract > semantic > heuristic > reader)
            method_scores = {
                "textract": 3,
                "dom_semantic": 2,
                "dom_heuristic": 1,
                "reader_mode": 0
            }
            score += method_scores.get(method, 0)
            
            scored_methods.append((method, score))
        
        # Return method with highest score
        scored_methods.sort(key=lambda x: x[1], reverse=True)
        return scored_methods[0][0] if scored_methods else "unknown"

# Global instances
enhanced_extraction_service = EnhancedExtractionService()
highlighting_debugger = HighlightingDebugger()

# Utility functions
async def extract_and_highlight(
    url: str, 
    user: User, 
    db: Session,
    **kwargs
) -> Dict[str, Any]:
    """Convenience function for extraction with highlighting"""
    return await enhanced_extraction_service.extract_with_highlighting(
        url, user, db, **kwargs
    )

async def extract_with_precise_timing(
    url: str,
    user: User, 
    db: Session,
    voice_id: str = "Joanna",
    engine: str = "neural"
) -> Dict[str, Any]:
    """Convenience function for extraction with speech marks"""
    return await enhanced_extraction_service.extract_with_speech_marks(
        url, user, db, voice_id, engine
    )

def debug_highlighting(text: str) -> Dict[str, Any]:
    """Debug highlighting for a given text"""
    return highlighting_debugger.test_highlight_generation(text)

def benchmark_url(url: str) -> Dict[str, Any]:
    """Benchmark extraction methods for a URL"""
    return highlighting_debugger.benchmark_extraction_methods(url)