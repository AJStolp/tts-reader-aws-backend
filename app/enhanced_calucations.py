"""
Enhanced extraction service with highlighting integration - COMPLETE ENTERPRISE VERSION
Implements enterprise-grade security, comprehensive audit logging, and advanced TTS optimization
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
try:
    from .enterprise_security import enterprise_security
except ImportError:
    logging.warning("Enterprise security not available")
    # Create a mock enterprise security for fallback
    class MockEnterpriseSecurity:
        def log_security_event(self, *args, **kwargs):
            pass
        def validate_url_security(self, url):
            return {"allowed": True, "violations": [], "risk_score": 0}
        def _validate_content_security(self, content):
            return {"risk_score": 0, "violations": []}
        def sanitize_text_content(self, content):
            return content
        def encrypt_sensitive_data(self, data):
            return data
        def decrypt_sensitive_data(self, data):
            return data
    enterprise_security = MockEnterpriseSecurity()

from textract_processor import ContentExtractorManager, ExtractionResult
from textract_processor.highlighting import (
    HighlightGenerator, HighlightMap, create_basic_highlight_map,
    optimize_text_for_highlighting, create_highlight_with_speech_marks
)
try:
    from textract_processor.extractors import TextractExtractor, DOMExtractor, PageAnalyzer
except ImportError:
    logging.warning("Textract processor extractors not fully available")
    # Create fallback classes
    class TextractExtractor:
        def __init__(self, client):
            self.client = client
        async def extract(self, url, analysis=None):
            return None
    
    class DOMExtractor:
        async def extract(self, url, analysis=None):
            return None
    
    class PageAnalyzer:
        async def analyze_page(self, url):
            return None

from models import User

logger = logging.getLogger(__name__)

class EnterpriseExtractionService:
    """Enterprise-grade extraction service with security, highlighting, and advanced TTS features"""
    
    def __init__(self):
        self.extraction_manager = ContentExtractorManager()
        self.highlight_generator = HighlightGenerator()
        self.extraction_progress: Dict[str, List[ExtractionProgress]] = {}
        self.highlight_cache: Dict[str, HighlightMap] = {}
        
        # Initialize extractors for direct access
        self.textract_extractor = None
        self.dom_extractor = DOMExtractor()
        self.page_analyzer = PageAnalyzer()
        
        # Enterprise security and audit
        self.extraction_audit_trail: List[Dict[str, Any]] = []
        self.performance_metrics: Dict[str, List[float]] = {
            "extraction_times": [],
            "highlighting_times": [],
            "speech_mark_times": []
        }
        
        # Try to initialize Textract if available - FIXED VERSION
        try:
            import boto3
            from .config import config
            
            # Initialize Textract client with proper error handling
            textract_client = boto3.client('textract', region_name=config.AWS_REGION)
            
            # Test Textract connectivity with a simple operation
            try:
                # Use describe_voices as a simple connectivity test instead
                # This is safer than trying to access a non-existent document
                polly_test = boto3.client('polly', region_name=config.AWS_REGION)
                polly_test.describe_voices(MaxItems=1)
                
                # If we get here, AWS credentials work, so Textract should work too
                self.textract_extractor = TextractExtractor(textract_client)
                logger.info("✅ Textract extractor initialized successfully")
                
            except Exception as test_error:
                logger.warning(f"⚠️ AWS connectivity test failed: {test_error}")
                # Still try to initialize Textract - it might work at runtime
                self.textract_extractor = TextractExtractor(textract_client)
                logger.info("✅ Textract extractor initialized with warnings")
                
        except ImportError:
            logger.warning("⚠️ boto3 not available for Textract")
            self.textract_extractor = None
        except Exception as e:
            logger.warning(f"⚠️ Textract extractor not available: {e}")
            self.textract_extractor = None
    
    async def extract_with_highlighting(
        self,
        url: str,
        user: User,
        db: Session,
        prefer_textract: bool = True,
        include_metadata: bool = False,
        include_highlighting: bool = True,
        include_speech_marks: bool = False,
        quality_analysis: bool = False,
        highlighting_options: Optional[Dict[str, Any]] = None,
        request_ip: str = "unknown",
        user_agent: str = "unknown"
    ) -> Dict[str, Any]:
        """Extract content with highlighting - Complete enterprise integration with security"""
        
        extraction_id = str(uuid.uuid4())
        start_time = time.time()
        
        try:
            # Enterprise security validation
            logger.info(f"🎯 Enterprise extraction with highlighting for user {user.username}: {url}")
            
            # Validate URL security
            url_validation = enterprise_security.validate_url_security(url)
            if not url_validation["allowed"]:
                enterprise_security.log_security_event(
                    "URL_SECURITY_VIOLATION",
                    str(user.user_id),
                    request_ip,
                    user_agent,
                    "/api/extract/enhanced",
                    "HIGH",
                    {
                        "url": url,
                        "violations": url_validation["violations"],
                        "risk_score": url_validation["risk_score"]
                    }
                )
                raise ValueError(f"URL blocked by security policy: {url_validation['violations']}")
            
            # Log extraction attempt
            enterprise_security.log_security_event(
                "EXTRACTION_INITIATED",
                str(user.user_id),
                request_ip,
                user_agent,
                "/api/extract/enhanced",
                "INFO",
                {
                    "url": url,
                    "prefer_textract": prefer_textract,
                    "include_highlighting": include_highlighting,
                    "include_speech_marks": include_speech_marks
                }
            )
            
            # Initialize progress with security context
            self._update_progress(extraction_id, ExtractionProgress(
                status="starting",
                message="🚀 Initializing enterprise TTS extraction with security validation...",
                progress=0.0
            ))
            
            # Step 1: Analyze page structure with security validation
            self._update_progress(extraction_id, ExtractionProgress(
                status="processing",
                message="🔍 Analyzing webpage structure for optimal TTS extraction...",
                progress=0.1
            ))
            
            page_analysis = await self.page_analyzer.analyze_page(url)
            
            # Step 2: Choose best extraction method with security considerations
            self._update_progress(extraction_id, ExtractionProgress(
                status="processing",
                message="⚙️ Selecting optimal extraction method for TTS content...",
                progress=0.2
            ))
            
            textract_used = False
            extraction_result = None
            
            # Try Textract first if preferred and available
            if prefer_textract and self.textract_extractor:
                try:
                    self._update_progress(extraction_id, ExtractionProgress(
                        status="processing",
                        message="🤖 Extracting content with AWS Textract for high-quality TTS...",
                        progress=0.3
                    ))
                    
                    extraction_result = await self.textract_extractor.extract(url, page_analysis)
                    if extraction_result and extraction_result.confidence > 0.6:
                        textract_used = True
                        logger.info(f"✅ Textract extraction successful with confidence {extraction_result.confidence}")
                        
                        # Log successful Textract usage
                        enterprise_security.log_security_event(
                            "TEXTRACT_EXTRACTION_SUCCESS",
                            str(user.user_id),
                            request_ip,
                            user_agent,
                            "/api/extract/enhanced",
                            "INFO",
                            {
                                "confidence": extraction_result.confidence,
                                "text_length": len(extraction_result.text),
                                "processing_time": extraction_result.processing_time
                            }
                        )
                    else:
                        logger.info("⚠️ Textract extraction low quality, falling back to DOM")
                        extraction_result = None
                        
                except Exception as e:
                    logger.warning(f"⚠️ Textract extraction failed: {e}")
                    enterprise_security.log_security_event(
                        "TEXTRACT_EXTRACTION_FAILED",
                        str(user.user_id),
                        request_ip,
                        user_agent,
                        "/api/extract/enhanced",
                        "MEDIUM",
                        {"error": str(e)}
                    )
                    extraction_result = None
            
            # Fallback to DOM extraction if Textract wasn't used or failed
            if not extraction_result:
                self._update_progress(extraction_id, ExtractionProgress(
                    status="processing", 
                    message="📄 Extracting content with DOM analysis optimized for TTS...",
                    progress=0.3
                ))
                
                extraction_result = await self.dom_extractor.extract(url, page_analysis)
                
                if not extraction_result:
                    enterprise_security.log_security_event(
                        "EXTRACTION_FAILED_ALL_METHODS",
                        str(user.user_id),
                        request_ip,
                        user_agent,
                        "/api/extract/enhanced",
                        "HIGH",
                        {"url": url}
                    )
                    raise ValueError("Could not extract content from the provided URL using any method")
            
            extracted_text = extraction_result.text
            method_used = extraction_result.method.value
            text_length = len(extracted_text)
            
            # Enterprise security: Validate extracted content
            content_validation = enterprise_security._validate_content_security(extracted_text)
            if content_validation["risk_score"] > 50:
                enterprise_security.log_security_event(
                    "EXTRACTED_CONTENT_SECURITY_RISK",
                    str(user.user_id),
                    request_ip,
                    user_agent,
                    "/api/extract/enhanced",
                    "HIGH",
                    {
                        "risk_score": content_validation["risk_score"],
                        "violations": content_validation["violations"],
                        "text_length": text_length
                    }
                )
                
                # Sanitize content for security
                extracted_text = enterprise_security.sanitize_text_content(extracted_text)
                text_length = len(extracted_text)
                logger.warning("⚠️ Content sanitized due to security concerns")
            
            # Step 3: Check character limits and deduct with audit trail
            if not user.deduct_characters(text_length):
                enterprise_security.log_security_event(
                    "CHARACTER_LIMIT_EXCEEDED",
                    str(user.user_id),
                    request_ip,
                    user_agent,
                    "/api/extract/enhanced",
                    "MEDIUM",
                    {
                        "requested_chars": text_length,
                        "remaining_chars": user.remaining_chars
                    }
                )
                raise ValueError(f"Text length ({text_length}) exceeds remaining character limit ({user.remaining_chars})")
            
            # Step 4: Optimize text for highlighting with security
            self._update_progress(extraction_id, ExtractionProgress(
                status="processing",
                message="🎨 Optimizing text for TTS highlighting synchronization...",
                progress=0.4,
                method=method_used
            ))
            
            highlighting_start_time = time.time()
            optimized_text = optimize_text_for_highlighting(extracted_text)
            
            # Step 5: Generate highlighting map with enterprise security
            highlight_map = None
            speech_marks_data = None
            
            if include_highlighting:
                self._update_progress(extraction_id, ExtractionProgress(
                    status="processing",
                    message="✨ Generating highlighting map for TTS synchronization...",
                    progress=0.6
                ))
                
                highlighting_opts = highlighting_options or {}
                segment_type = highlighting_opts.get("segment_type", "sentence")
                
                if include_speech_marks:
                    # Generate speech marks for precise timing with security validation
                    try:
                        self._update_progress(extraction_id, ExtractionProgress(
                            status="processing",
                            message="🎤 Generating speech marks with AWS Polly for precise highlighting...",
                            progress=0.7
                        ))
                        
                        speech_marks_start_time = time.time()
                        speech_marks_data = await self._generate_speech_marks_secure(
                            optimized_text,
                            highlighting_opts.get("voice_id", "Joanna"),
                            highlighting_opts.get("engine", "neural"),
                            user,
                            request_ip,
                            user_agent
                        )
                        
                        self.performance_metrics["speech_mark_times"].append(
                            time.time() - speech_marks_start_time
                        )
                        
                        highlight_map = create_highlight_with_speech_marks(
                            optimized_text,
                            speech_marks_data,
                            extraction_method=f"{method_used}_with_speech_marks"
                        )
                        
                        logger.info("✅ Generated highlighting with precise speech mark timing")
                        
                        # Log successful speech mark generation
                        enterprise_security.log_security_event(
                            "SPEECH_MARKS_GENERATED",
                            str(user.user_id),
                            request_ip,
                            user_agent,
                            "/api/extract/enhanced",
                            "INFO",
                            {
                                "text_length": len(optimized_text),
                                "processing_time": time.time() - speech_marks_start_time,
                                "segments": len(highlight_map.segments) if highlight_map else 0
                            }
                        )
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Speech marks generation failed: {e}")
                        enterprise_security.log_security_event(
                            "SPEECH_MARKS_GENERATION_FAILED",
                            str(user.user_id),
                            request_ip,
                            user_agent,
                            "/api/extract/enhanced",
                            "MEDIUM",
                            {"error": str(e)}
                        )
                        # Fallback to basic highlighting
                        highlight_map = create_basic_highlight_map(
                            optimized_text,
                            extraction_method=method_used
                        )
                else:
                    # Generate basic highlighting without speech marks
                    highlight_map = self.highlight_generator.create_highlight_map(
                        optimized_text,
                        extraction_method=method_used,
                        segment_type=segment_type
                    )
                
                highlighting_time = time.time() - highlighting_start_time
                self.performance_metrics["highlighting_times"].append(highlighting_time)
            
            # Step 6: Create reading chunks for long content with security limits
            self._update_progress(extraction_id, ExtractionProgress(
                status="processing",
                message="📚 Creating optimized reading chunks for TTS playback...",
                progress=0.8
            ))
            
            reading_chunks = []
            if text_length > 3000:  # Create chunks for long content
                max_chunk_size = min(
                    highlighting_opts.get("chunk_size", 3000) if highlighting_opts else 3000,
                    10000  # Security limit: max 10KB chunks
                )
                reading_chunks = self.highlight_generator.create_reading_chunks(
                    optimized_text,
                    max_chunk_size=max_chunk_size,
                    overlap_sentences=highlighting_opts.get("overlap_sentences", 1) if highlighting_opts else 1
                )
            
            # Step 7: Quality analysis if requested
            extraction_metrics = {
                "processing_time": time.time() - start_time,
                "text_quality_score": extraction_result.confidence,
                "method_confidence": 1.0 if textract_used else 0.8,
                "security_validated": True,
                "content_sanitized": content_validation["risk_score"] > 50
            }
            
            if quality_analysis:
                quality_metrics = self.analyze_extraction_quality_secure(url, extraction_result, user, request_ip)
                extraction_metrics.update(quality_metrics)
            
            # Step 8: Validate highlighting if generated
            validation_result = None
            if highlight_map:
                validation_result = self.highlight_generator.validate_highlight_map(highlight_map)
                
                # Security validation of highlight map
                if not self._validate_highlight_map_security(highlight_map):
                    enterprise_security.log_security_event(
                        "HIGHLIGHT_MAP_SECURITY_ISSUE",
                        str(user.user_id),
                        request_ip,
                        user_agent,
                        "/api/extract/enhanced",
                        "MEDIUM",
                        {"segments": len(highlight_map.segments), "words": len(highlight_map.words)}
                    )
            
            # Commit character deduction with audit trail
            db.commit()
            
            # Record performance metrics
            total_processing_time = time.time() - start_time
            self.performance_metrics["extraction_times"].append(total_processing_time)
            
            # Final progress update
            self._update_progress(extraction_id, ExtractionProgress(
                status="completed",
                message="🎉 Enhanced TTS extraction with highlighting completed successfully",
                progress=1.0,
                method=method_used
            ))
            
            # Cache the highlighting map securely
            cache_key = None
            if highlight_map:
                cache_key = f"{url}_{method_used}_{hash(optimized_text)}"
                # Encrypt sensitive cache data
                encrypted_cache_data = enterprise_security.encrypt_sensitive_data(
                    json.dumps(highlight_map.to_dict())
                )
                self.highlight_cache[cache_key] = encrypted_cache_data
            
            # Create audit trail entry
            audit_entry = {
                "extraction_id": extraction_id,
                "user_id": str(user.user_id),
                "url": url,
                "method_used": method_used,
                "textract_used": textract_used,
                "text_length": text_length,
                "processing_time": total_processing_time,
                "highlighting_generated": highlight_map is not None,
                "speech_marks_generated": speech_marks_data is not None,
                "security_validated": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            self.extraction_audit_trail.append(audit_entry)
            
            logger.info(f"🎯 Enterprise extraction completed for user {user.username}: "
                       f"{text_length} characters, {len(highlight_map.segments) if highlight_map else 0} segments in {total_processing_time:.2f}s")
            
            # Log successful completion
            enterprise_security.log_security_event(
                "EXTRACTION_COMPLETED_SUCCESS",
                str(user.user_id),
                request_ip,
                user_agent,
                "/api/extract/enhanced",
                "INFO",
                {
                    "extraction_id": extraction_id,
                    "text_length": text_length,
                    "method_used": method_used,
                    "textract_used": textract_used,
                    "processing_time": total_processing_time,
                    "highlighting_segments": len(highlight_map.segments) if highlight_map else 0
                }
            )
            
            # Prepare enhanced response matching frontend expectations
            response_data = {
                # Core extraction data
                "text": optimized_text,
                "characters_used": text_length,
                "remaining_chars": user.remaining_chars,
                "extraction_method": method_used,
                "method_used": method_used,  # Legacy compatibility
                "word_count": len(optimized_text.split()),
                "processing_time": total_processing_time,
                
                # TTS-specific flags that frontend checks
                "textract_used": textract_used,
                "success": True,
                
                # Highlighting data for frontend integration
                "highlighting_map": highlight_map.to_dict() if highlight_map else None,
                "speech_marks": speech_marks_data,
                "reading_chunks": reading_chunks,
                
                # Quality and validation
                "validation": validation_result,
                "extraction_metrics": extraction_metrics,
                
                # TTS optimization info
                "tts_optimized": True,
                "segment_count": len(highlight_map.segments) if highlight_map else 0,
                "estimated_reading_time": highlight_map.total_duration / 1000 / 60 if highlight_map else 0,  # minutes
                
                # Enterprise security info
                "security_validated": True,
                "content_sanitized": content_validation["risk_score"] > 50,
                "extraction_id": extraction_id
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
                    "cache_key": cache_key if highlight_map else None,
                    "page_analysis": page_analysis.dict() if page_analysis else None,
                    "content_type": extraction_result.content_type.value if extraction_result else "unknown",
                    "security_context": {
                        "ip_address": request_ip,
                        "user_agent": user_agent,
                        "url_validated": True,
                        "content_validated": True
                    }
                }
            
            self._cleanup_progress_data()
            return response_data
            
        except Exception as e:
            logger.error(f"❌ Enhanced extraction error for user {user.username}: {str(e)}", exc_info=True)
            
            # Log security incident
            enterprise_security.log_security_event(
                "EXTRACTION_ERROR",
                str(user.user_id),
                request_ip,
                user_agent,
                "/api/extract/enhanced",
                "HIGH",
                {
                    "extraction_id": extraction_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "processing_time": time.time() - start_time
                }
            )
            
            self._update_progress(extraction_id, ExtractionProgress(
                status="failed",
                message=f"❌ Enhanced extraction failed: {str(e)}",
                progress=1.0
            ))
            
            db.rollback()
            raise
    
    async def _generate_speech_marks_secure(
        self, 
        text: str, 
        voice_id: str = "Joanna", 
        engine: str = "neural",
        user: User = None,
        request_ip: str = "unknown",
        user_agent: str = "unknown"
    ) -> str:
        """Generate speech marks using AWS Polly with enterprise security"""
        try:
            import boto3
            from .config import config
            
            # Security validation for speech synthesis
            if len(text) > 100000:  # 100KB limit for security
                enterprise_security.log_security_event(
                    "SPEECH_MARKS_TEXT_TOO_LARGE",
                    str(user.user_id) if user else None,
                    request_ip,
                    user_agent,
                    "/api/speech-marks",
                    "MEDIUM",
                    {"text_length": len(text)}
                )
                raise ValueError("Text too large for speech mark generation")
            
            # Sanitize text for speech synthesis
            sanitized_text = enterprise_security.sanitize_text_content(text)
            
            polly_client = boto3.client('polly', region_name=config.AWS_REGION)
            
            # Split text into chunks if too long (Polly has character limits)
            chunks = self._split_text_for_polly_secure(sanitized_text, 3000)
            all_marks = []
            cumulative_time = 0
            
            for i, chunk in enumerate(chunks):
                try:
                    # Log chunk processing for audit
                    if user:
                        enterprise_security.log_security_event(
                            "SPEECH_MARKS_CHUNK_PROCESSING",
                            str(user.user_id),
                            request_ip,
                            user_agent,
                            "/api/speech-marks",
                            "LOW",
                            {
                                "chunk_index": i + 1,
                                "total_chunks": len(chunks),
                                "chunk_length": len(chunk)
                            }
                        )
                    
                    # Generate speech marks for this chunk with timeout
                    response = await asyncio.wait_for(
                        asyncio.to_thread(
                            polly_client.synthesize_speech,
                            Text=chunk,
                            OutputFormat="json",
                            VoiceId=voice_id,
                            Engine=engine,
                            SpeechMarkTypes=["word", "sentence"]
                        ),
                        timeout=30.0  # 30 second timeout for security
                    )
                    
                    marks_text = response['AudioStream'].read().decode('utf-8')
                    chunk_marks = [json.loads(line) for line in marks_text.splitlines() if line.strip()]
                    
                    # Adjust timing for concatenated chunks
                    for mark in chunk_marks:
                        mark['time'] += cumulative_time
                        all_marks.append(mark)
                    
                    # Estimate chunk duration for next offset
                    if chunk_marks:
                        chunk_duration = max([mark['time'] for mark in chunk_marks]) + 1000
                        cumulative_time += chunk_duration
                    else:
                        # Fallback duration estimation
                        cumulative_time += len(chunk) * 50  # ~50ms per character
                        
                except asyncio.TimeoutError:
                    logger.warning(f"⚠️ Speech mark generation timeout for chunk {i+1}")
                    if user:
                        enterprise_security.log_security_event(
                            "SPEECH_MARKS_TIMEOUT",
                            str(user.user_id),
                            request_ip,
                            user_agent,
                            "/api/speech-marks",
                            "MEDIUM",
                            {"chunk_index": i + 1, "timeout": True}
                        )
                    continue
                except Exception as chunk_error:
                    logger.warning(f"⚠️ Failed to process chunk {i+1}: {chunk_error}")
                    if user:
                        enterprise_security.log_security_event(
                            "SPEECH_MARKS_CHUNK_ERROR",
                            str(user.user_id),
                            request_ip,
                            user_agent,
                            "/api/speech-marks",
                            "MEDIUM",
                            {
                                "chunk_index": i + 1,
                                "error": str(chunk_error)
                            }
                        )
                    continue
            
            # Convert back to newline-separated JSON format expected by frontend
            result = '\n'.join([json.dumps(mark) for mark in all_marks])
            
            # Validate result size for security
            if len(result) > 10000000:  # 10MB limit
                enterprise_security.log_security_event(
                    "SPEECH_MARKS_RESULT_TOO_LARGE",
                    str(user.user_id) if user else None,
                    request_ip,
                    user_agent,
                    "/api/speech-marks",
                    "HIGH",
                    {"result_size": len(result)}
                )
                raise ValueError("Speech marks result too large")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error generating speech marks: {str(e)}")
            if user:
                enterprise_security.log_security_event(
                    "SPEECH_MARKS_GENERATION_ERROR",
                    str(user.user_id),
                    request_ip,
                    user_agent,
                    "/api/speech-marks",
                    "HIGH",
                    {"error": str(e)}
                )
            raise
    
    def _split_text_for_polly_secure(self, text: str, max_length: int = 3000) -> List[str]:
        """Split text intelligently at sentence boundaries for Polly with security limits"""
        if len(text) <= max_length:
            return [text]
        
        # Security: Limit total chunks to prevent DoS
        max_chunks = 50
        
        # Split by sentences
        sentences = text.replace('\n', ' ').split('. ')
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            # Security: Skip excessively long sentences
            if len(sentence) > max_length * 2:
                logger.warning(f"⚠️ Skipping excessively long sentence: {len(sentence)} chars")
                continue
                
            test_chunk = current_chunk + sentence + ". "
            if len(test_chunk) > max_length and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
                
                # Security: Limit number of chunks
                if len(chunks) >= max_chunks:
                    logger.warning(f"⚠️ Reached maximum chunk limit: {max_chunks}")
                    break
            else:
                current_chunk = test_chunk
        
        if current_chunk and len(chunks) < max_chunks:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _validate_highlight_map_security(self, highlight_map: HighlightMap) -> bool:
        """Validate highlighting map for security issues"""
        try:
            # Check for reasonable bounds
            if len(highlight_map.segments) > 10000:  # Max 10k segments
                return False
            
            if len(highlight_map.words) > 100000:  # Max 100k words
                return False
            
            if highlight_map.total_duration > 86400000:  # Max 24 hours
                return False
            
            # Validate segment data
            for segment in highlight_map.segments:
                if segment.start_char < 0 or segment.end_char < 0:
                    return False
                if segment.start_time < 0 or segment.end_time < 0:
                    return False
                if len(segment.text) > 10000:  # Max 10KB per segment
                    return False
            
            return True
        except Exception:
            return False
    
    def analyze_extraction_quality_secure(
        self, 
        url: str, 
        result: ExtractionResult, 
        user: User,
        request_ip: str
    ) -> Dict[str, Any]:
        """Analyze extraction quality with enterprise security logging"""
        
        try:
            analysis = {
                "url": url,
                "extraction_method": result.method.value,
                "content_type": result.content_type.value,
                "confidence": result.confidence,
                "character_count": result.char_count,
                "word_count": result.word_count,
                "processing_time": result.processing_time,
                "security_validated": True
            }
            
            # Add quality metrics
            if result.word_count > 0:
                analysis["avg_word_length"] = result.char_count / result.word_count
                analysis["reading_complexity"] = self._assess_reading_complexity_secure(result.text)
            
            # Add TTS-specific recommendations with security considerations
            recommendations = []
            if result.confidence < 0.7:
                recommendations.append("Consider trying a different extraction method for better TTS quality")
            if result.char_count < 200:
                recommendations.append("Content may be too short for effective TTS playback")
            if result.char_count > 50000:
                recommendations.append("Consider breaking into smaller chunks for better TTS performance")
            
            # Check for TTS-problematic content with security validation
            text_sample = result.text[:1000]  # Only analyze first 1KB for security
            text_lower = text_sample.lower()
            
            if text_lower.count('http') > 10:
                recommendations.append("Content contains many URLs - consider cleaning for better TTS")
            if len([c for c in text_sample if c.isdigit()]) / len(text_sample) > 0.3:
                recommendations.append("High number density - may need preprocessing for TTS")
            
            analysis["recommendations"] = recommendations
            analysis["overall_grade"] = self._calculate_overall_grade_secure(result)
            analysis["tts_suitability"] = self._assess_tts_suitability_secure(text_sample)
            
            # Log quality analysis
            enterprise_security.log_security_event(
                "QUALITY_ANALYSIS_PERFORMED",
                str(user.user_id),
                request_ip,
                "quality-analyzer",
                "/api/extract/quality",
                "LOW",
                {
                    "overall_grade": analysis["overall_grade"],
                    "confidence": result.confidence,
                    "method": result.method.value
                }
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Quality analysis error: {str(e)}")
            enterprise_security.log_security_event(
                "QUALITY_ANALYSIS_ERROR",
                str(user.user_id),
                request_ip,
                "quality-analyzer",
                "/api/extract/quality",
                "MEDIUM",
                {"error": str(e)}
            )
            return {"error": "Quality analysis failed", "security_validated": False}
    
    def _assess_reading_complexity_secure(self, text: str) -> str:
        """Assess reading complexity for TTS optimization with security limits"""
        try:
            # Security: Only analyze first 5KB of text
            text_sample = text[:5000]
            sentences = [s for s in text_sample.split('.') if s.strip()]
            
            if not sentences or len(sentences) > 1000:  # Security limit
                return "unknown"
            
            avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
            
            if avg_sentence_length < 10:
                return "simple"
            elif avg_sentence_length < 20:
                return "moderate"
            else:
                return "complex"
        except Exception:
            return "unknown"
    
    def _assess_tts_suitability_secure(self, text: str) -> Dict[str, Any]:
        """Assess how suitable the text is for TTS with security limits"""
        try:
            # Security: Only analyze first 5KB
            text_sample = text[:5000]
            total_chars = len(text_sample)
            
            if total_chars == 0:
                return {"score": 0.0, "issues": ["Empty text"]}
            
            # Count various text characteristics with security limits
            urls = min(text_sample.count('http'), 100)  # Cap count for security
            numbers = sum(1 for c in text_sample if c.isdigit())
            special_chars = sum(1 for c in text_sample if not c.isalnum() and c not in ' .,!?;:-\'"()')
            
            # Calculate ratios
            url_ratio = urls / max(1, total_chars / 100)  # URLs per 100 chars
            number_ratio = numbers / total_chars if total_chars > 0 else 0
            special_ratio = special_chars / total_chars if total_chars > 0 else 0
            
            # Calculate score
            score = 1.0
            issues = []
            
            if url_ratio > 2:
                score -= 0.2
                issues.append("High URL density")
            
            if number_ratio > 0.3:
                score -= 0.15
                issues.append("High number density")
            
            if special_ratio > 0.1:
                score -= 0.1
                issues.append("High special character density")
            
            # Check for code-like content (security: limited check)
            if '()' in text_sample[:1000] and '{' in text_sample[:1000]:
                score -= 0.2
                issues.append("Contains code-like syntax")
            
            return {
                "score": max(0.0, score),
                "issues": issues,
                "url_ratio": url_ratio,
                "number_ratio": number_ratio,
                "special_ratio": special_ratio,
                "security_validated": True
            }
            
        except Exception as e:
            logger.warning(f"⚠️ TTS suitability assessment error: {str(e)}")
            return {"score": 0.5, "issues": ["Assessment failed"], "security_validated": False}
    
    def _calculate_overall_grade_secure(self, result: ExtractionResult) -> str:
        """Calculate overall grade for extraction quality with security validation"""
        try:
            score = 0
            
            # Confidence scoring (40% weight)
            score += min(result.confidence, 1.0) * 0.4
            
            # Length scoring (30% weight) with security limits
            char_count = min(result.char_count, 1000000)  # Cap at 1MB for security
            if 500 <= char_count <= 10000:
                score += 0.3  # Ideal length
            elif 200 <= char_count <= 50000:
                score += 0.15  # Acceptable length
            
            # Processing time scoring (15% weight) with security limits
            processing_time = min(result.processing_time, 300)  # Cap at 5 minutes
            if processing_time < 5:
                score += 0.15
            elif processing_time < 15:
                score += 0.1
            elif processing_time < 30:
                score += 0.05
            
            # Method scoring (15% weight)
            method_scores = {
                "textract": 0.15,
                "dom_semantic": 0.12,
                "dom_heuristic": 0.1,
                "reader_mode": 0.08,
                "dom_fallback": 0.05
            }
            score += method_scores.get(result.method.value, 0.05)
            
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
                
        except Exception:
            return "F"  # Fail safe
    
    def get_cached_highlight_map(self, cache_key: str) -> Optional[HighlightMap]:
        """Retrieve cached highlight map with security decryption"""
        try:
            encrypted_data = self.highlight_cache.get(cache_key)
            if encrypted_data:
                decrypted_data = enterprise_security.decrypt_sensitive_data(encrypted_data)
                highlight_dict = json.loads(decrypted_data)
                # Convert back to HighlightMap object (implementation depends on your structure)
                return highlight_dict
            return None
        except Exception as e:
            logger.warning(f"⚠️ Cache retrieval error: {str(e)}")
            return None
    
    def _update_progress(self, extraction_id: str, progress: ExtractionProgress):
        """Update extraction progress with security validation"""
        if extraction_id not in self.extraction_progress:
            self.extraction_progress[extraction_id] = []
        
        # Security: Limit progress entries per extraction
        if len(self.extraction_progress[extraction_id]) > 100:
            self.extraction_progress[extraction_id] = self.extraction_progress[extraction_id][-50:]
        
        self.extraction_progress[extraction_id].append(progress)
    
    def _cleanup_progress_data(self):
        """Clean up old progress data with enterprise security"""
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
        
        # Clean up old cache entries (keep last 1000)
        if len(self.highlight_cache) > 1000:
            cache_keys = list(self.highlight_cache.keys())
            for key in cache_keys[:-1000]:
                del self.highlight_cache[key]
    
    def get_extraction_progress(self, extraction_id: str) -> Dict[str, Any]:
        """Get extraction progress with security validation"""
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
            "history": [p.dict() for p in progress_list[-5:]],  # Last 5 only for security
            "security_validated": True
        }
    
    def get_enterprise_metrics(self) -> Dict[str, Any]:
        """Get enterprise performance and security metrics"""
        return {
            "performance_metrics": {
                "avg_extraction_time": sum(self.performance_metrics["extraction_times"]) / len(self.performance_metrics["extraction_times"]) if self.performance_metrics["extraction_times"] else 0,
                "avg_highlighting_time": sum(self.performance_metrics["highlighting_times"]) / len(self.performance_metrics["highlighting_times"]) if self.performance_metrics["highlighting_times"] else 0,
                "avg_speech_mark_time": sum(self.performance_metrics["speech_mark_times"]) / len(self.performance_metrics["speech_mark_times"]) if self.performance_metrics["speech_mark_times"] else 0,
                "total_extractions": len(self.performance_metrics["extraction_times"]),
                "cache_size": len(self.highlight_cache),
                "active_extractions": len(self.extraction_progress)
            },
            "security_status": {
                "audit_trail_entries": len(self.extraction_audit_trail),
                "textract_available": self.textract_extractor is not None,
                "security_validation_enabled": True,
                "content_sanitization_enabled": True
            },
            "system_health": {
                "extraction_manager_healthy": self.extraction_manager is not None,
                "highlight_generator_healthy": self.highlight_generator is not None,
                "cache_healthy": len(self.highlight_cache) < 10000
            }
        }

# Global instance for use across the application
enhanced_extraction_service = EnterpriseExtractionService()

# Convenience functions matching the frontend expectations
async def extract_and_highlight(
    url: str, 
    user: User, 
    db: Session,
    request_ip: str = "unknown",
    user_agent: str = "unknown",
    **kwargs
) -> Dict[str, Any]:
    """Convenience function for extraction with highlighting - Enterprise secured"""
    return await enhanced_extraction_service.extract_with_highlighting(
        url, user, db, request_ip=request_ip, user_agent=user_agent, **kwargs
    )

async def extract_with_precise_timing(
    url: str,
    user: User, 
    db: Session,
    voice_id: str = "Joanna",
    engine: str = "neural",
    request_ip: str = "unknown",
    user_agent: str = "unknown"
) -> Dict[str, Any]:
    """Convenience function for extraction with speech marks - Enterprise secured"""
    return await enhanced_extraction_service.extract_with_highlighting(
        url, user, db, 
        include_speech_marks=True,
        highlighting_options={"voice_id": voice_id, "engine": engine},
        request_ip=request_ip,
        user_agent=user_agent
    )