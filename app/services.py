"""
Business logic services for TTS Reader API - ENHANCED WITH HIGHLIGHTING INTEGRATION
"""
import asyncio
import io
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import boto3
import stripe
from botocore.exceptions import ClientError, NoCredentialsError
from pydub import AudioSegment
from sqlalchemy.orm import Session

from .config import config
from .models import (
    ExtractionProgress, ExtractionPreview, ExtractResponseEnhanced,
    SynthesizeResponse, AnalyticsResponse
)
from textract_processor import ContentExtractorManager, extract_content
from textract_processor.highlighting import create_basic_highlight_map, create_highlight_with_speech_marks
from models import User

logger = logging.getLogger(__name__)

class AWSService:
    """Service for AWS operations (S3, Polly, etc.) - Enhanced for TTS"""
    
    def __init__(self):
        self.session = None
        self.s3 = None
        self.polly = None
        self.bucket_name = config.S3_BUCKET_NAME
        self._initialize_aws()
    
    def _initialize_aws(self):
        """Initialize AWS clients with error handling"""
        try:
            self.session = boto3.Session(
                aws_access_key_id=config.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
                region_name=config.AWS_REGION
            )
            
            self.s3 = self.session.client("s3")
            self.polly = self.session.client("polly")
            
            # Test AWS credentials
            self.s3.list_buckets()
            self.polly.describe_voices(LanguageCode="en-US")
            
            logger.info("✅ AWS services initialized successfully")
            
        except (NoCredentialsError, ClientError) as e:
            logger.error(f"❌ AWS configuration error: {str(e)}")
            raise ValueError("Invalid AWS credentials or configuration")
    
    async def setup_bucket(self):
        """Setup S3 bucket with proper configuration for TTS files"""
        try:
            # Check if bucket exists
            self.s3.head_bucket(Bucket=self.bucket_name)
            logger.info(f"✅ Bucket {self.bucket_name} already exists")
        except ClientError as e:
            error_code = int(e.response["Error"]["Code"])
            if error_code == 404:
                # Create bucket
                try:
                    if config.AWS_REGION == "us-east-1":
                        self.s3.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.s3.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={
                                "LocationConstraint": config.AWS_REGION
                            }
                        )
                    
                    # Configure bucket security
                    self.s3.put_public_access_block(
                        Bucket=self.bucket_name,
                        PublicAccessBlockConfiguration={
                            "BlockPublicAcls": True,
                            "IgnorePublicAcls": True,
                            "BlockPublicPolicy": True,
                            "RestrictPublicBuckets": True
                        }
                    )
                    
                    # Enable versioning
                    self.s3.put_bucket_versioning(
                        Bucket=self.bucket_name,
                        VersioningConfiguration={"Status": "Enabled"}
                    )
                    
                    # Add lifecycle configuration for TTS files
                    self.s3.put_bucket_lifecycle_configuration(
                        Bucket=self.bucket_name,
                        LifecycleConfiguration={
                            'Rules': [
                                {
                                    'ID': 'DeleteTTSFilesAfter7Days',
                                    'Status': 'Enabled',
                                    'Filter': {'Prefix': 'users/'},
                                    'Expiration': {'Days': 7}
                                }
                            ]
                        }
                    )
                    
                    logger.info(f"✅ Created and configured bucket {self.bucket_name} for TTS")
                except ClientError as create_error:
                    logger.error(f"❌ Failed to create bucket: {str(create_error)}")
                    raise
            else:
                logger.error(f"❌ Error accessing bucket: {str(e)}")
                raise
    
    def split_text_smart(self, text: str, max_length: int = None) -> List[str]:
        """Split text intelligently at sentence boundaries for TTS"""
        max_length = max_length or config.MAX_POLLY_CHARS
        
        if len(text) <= max_length:
            return [text]
        
        # Enhanced splitting for TTS - preserve sentence flow
        sentences = text.replace('\n', ' ').split('. ')
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            # Clean up sentence
            sentence = sentence.strip()
            if not sentence:
                continue
                
            test_chunk = current_chunk + sentence + ". "
            if len(test_chunk) > max_length and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
            else:
                current_chunk = test_chunk
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        logger.info(f"📚 Split text into {len(chunks)} chunks for TTS processing")
        return chunks
    
    async def get_voices(self) -> Dict[str, List[Dict]]:
        """Get available Polly voices grouped by engine for TTS"""
        try:
            response = await asyncio.to_thread(
                self.polly.describe_voices,
                LanguageCode="en-US"
            )
            
            # Group voices by supported engines
            standard_voices = []
            neural_voices = []
            long_form_voices = []
            
            for voice in response["Voices"]:
                voice_data = {
                    "id": voice["Id"],
                    "name": voice["Name"],
                    "gender": voice["Gender"],
                    "language": voice["LanguageName"],
                    "tts_optimized": True,
                    "supports_speech_marks": True
                }
                
                # Check which engines this voice supports
                supported_engines = voice["SupportedEngines"]
                
                if "standard" in supported_engines:
                    standard_voices.append(voice_data)
                
                if "neural" in supported_engines:
                    neural_voices.append({**voice_data, "quality": "high"})
                
                # Check for long-form support (newer Polly feature)
                if "long-form" in supported_engines:
                    long_form_voices.append({**voice_data, "quality": "premium"})
            
            return {
                "standard": standard_voices,
                "neural": neural_voices,
                "long_form": long_form_voices,
                "all": standard_voices + neural_voices + long_form_voices,
                "recommendation": "Neural voices provide more natural TTS output with better speech mark accuracy",
                "total_count": len(standard_voices + neural_voices + long_form_voices)
            }
            
        except Exception as e:
            logger.error(f"❌ Error fetching voices: {str(e)}")
            raise

# Global AWS service instance
aws_service = AWSService()

class ExtractionService:
    """Service for content extraction operations - Enhanced with highlighting"""
    
    def __init__(self):
        self.extraction_manager = ContentExtractorManager()
        self.extraction_progress: Dict[str, List[ExtractionProgress]] = {}
    
    async def extract_content_enhanced(
        self, 
        url: str, 
        user: User, 
        db: Session,
        prefer_textract: bool = True,
        include_metadata: bool = False
    ) -> ExtractResponseEnhanced:
        """Enhanced content extraction with progress tracking and TTS optimization"""
        extraction_id = str(uuid.uuid4())
        
        try:
            logger.info(f"🚀 Enhanced extraction request from user {user.username}: {url}")
            
            # Initialize progress tracking
            self.extraction_progress[extraction_id] = [
                ExtractionProgress(
                    status="starting",
                    message="🎯 Initializing TTS content extraction...",
                    progress=0.0
                )
            ]
            
            # Update progress
            self._update_progress(extraction_id, ExtractionProgress(
                status="processing",
                message="📄 Analyzing webpage and extracting TTS-optimized content...",
                progress=0.3
            ))
            
            # Perform extraction
            start_time = time.time()
            extracted_text, method = await self.extraction_manager.extract_content(
                url, prefer_textract=prefer_textract
            )
            processing_time = time.time() - start_time
            
            if not extracted_text:
                self._update_progress(extraction_id, ExtractionProgress(
                    status="failed",
                    message="❌ Could not extract TTS content from the provided URL",
                    progress=1.0
                ))
                raise ValueError("Could not extract content from the provided URL")
            
            text_length = len(extracted_text)
            
            # Update progress
            self._update_progress(extraction_id, ExtractionProgress(
                status="processing",
                message="✅ Validating extracted TTS content...",
                progress=0.7,
                method=method
            ))
            
            # Check character limits
            if not user.deduct_characters(text_length):
                self._update_progress(extraction_id, ExtractionProgress(
                    status="failed",
                    message=f"❌ Text length ({text_length}) exceeds remaining character limit",
                    progress=1.0
                ))
                raise ValueError(f"Text length ({text_length}) exceeds remaining character limit ({user.remaining_chars})")
            
            # Create basic highlighting for TTS
            self._update_progress(extraction_id, ExtractionProgress(
                status="processing",
                message="🎨 Generating TTS highlighting map...",
                progress=0.9
            ))
            
            try:
                from textract_processor.highlighting import optimize_text_for_highlighting
                optimized_text = optimize_text_for_highlighting(extracted_text)
                highlight_map = create_basic_highlight_map(optimized_text, extraction_method=method)
                
                logger.info(f"✅ Generated highlighting with {len(highlight_map.segments)} segments")
            except Exception as highlight_error:
                logger.warning(f"⚠️ Could not generate highlighting: {highlight_error}")
                optimized_text = extracted_text
                highlight_map = None
            
            # Commit the character deduction
            db.commit()
            
            # Update progress
            self._update_progress(extraction_id, ExtractionProgress(
                status="completed",
                message="🎉 TTS content extraction completed successfully",
                progress=1.0,
                method=method
            ))
            
            logger.info(f"✅ Enhanced extraction completed for user {user.username}: "
                       f"{text_length} characters using {method} in {processing_time:.2f}s")
            
            # Prepare response with TTS enhancements
            response_data = {
                "text": optimized_text,
                "characters_used": text_length,
                "remaining_chars": user.remaining_chars,
                "extraction_method": method,
                "word_count": len(optimized_text.split()),
                "processing_time": processing_time,
                "tts_optimized": True,
                "highlighting_available": highlight_map is not None
            }
            
            # Add highlighting data if available
            if highlight_map:
                response_data["highlighting_map"] = highlight_map.to_dict()
                response_data["segment_count"] = len(highlight_map.segments)
                response_data["estimated_reading_time"] = highlight_map.total_duration / 1000 / 60
            
            # Add metadata if requested
            if include_metadata:
                response_data["metadata"] = {
                    "url": url,
                    "extraction_id": extraction_id,
                    "user_id": str(user.user_id),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "prefer_textract": prefer_textract,
                    "optimized_for_tts": True
                }
            
            # Clean up progress data
            self._cleanup_progress_data()
            
            return ExtractResponseEnhanced(**response_data)
            
        except Exception as e:
            logger.error(f"❌ Enhanced extraction error for user {user.username}: {str(e)}", exc_info=True)
            
            self._update_progress(extraction_id, ExtractionProgress(
                status="failed",
                message=f"❌ An error occurred during TTS extraction: {str(e)}",
                progress=1.0
            ))
            
            db.rollback()
            raise
    
    async def extract_preview(self, url: str) -> ExtractionPreview:
        """Get a preview of extracted TTS content without using character credits"""
        try:
            logger.info(f"📋 Preview extraction request: {url}")
            
            # Perform extraction
            extracted_text, method = await extract_content(url)
            
            if not extracted_text:
                raise ValueError("Could not extract content from the provided URL")
            
            # Create preview (first 500 characters)
            preview = extracted_text[:500]
            if len(extracted_text) > 500:
                preview += "..."
            
            # Estimate confidence based on extraction method
            confidence_map = {
                "textract": 0.9,
                "dom_semantic": 0.8,
                "dom_heuristic": 0.7,
                "reader_mode": 0.6,
                "dom_fallback": 0.4
            }
            
            confidence = confidence_map.get(method, 0.5)
            
            # Estimate TTS reading time
            word_count = len(extracted_text.split())
            estimated_minutes = word_count / 150  # Average reading speed
            
            return ExtractionPreview(
                preview=preview,
                estimated_length=len(extracted_text),
                confidence=confidence,
                method=method,
                full_available=True,
                word_count=word_count,
                estimated_reading_time=estimated_minutes
            )
            
        except Exception as e:
            logger.error(f"❌ Preview extraction error: {str(e)}")
            raise
    
    def get_extraction_progress(self, extraction_id: str) -> Dict[str, Any]:
        """Get real-time progress of content extraction"""
        if extraction_id not in self.extraction_progress:
            raise ValueError("Extraction progress not found")
        
        progress_list = self.extraction_progress[extraction_id]
        latest_progress = progress_list[-1] if progress_list else None
        
        return {
            "extraction_id": extraction_id,
            "current_status": latest_progress.status if latest_progress else "unknown",
            "current_message": latest_progress.message if latest_progress else "No progress data",
            "progress": latest_progress.progress if latest_progress else 0.0,
            "method": latest_progress.method if latest_progress else None,
            "history": [p.dict() for p in progress_list[-5:]]  # Last 5 progress updates
        }
    
    def _update_progress(self, extraction_id: str, progress: ExtractionProgress):
        """Update extraction progress"""
        if extraction_id in self.extraction_progress:
            self.extraction_progress[extraction_id].append(progress)
    
    def _cleanup_progress_data(self):
        """Clean up old progress data to prevent memory leaks"""
        if len(self.extraction_progress) > 100:
            # Sort by the latest timestamp and keep the most recent
            sorted_keys = sorted(
                self.extraction_progress.keys(),
                key=lambda k: self.extraction_progress[k][-1].timestamp if self.extraction_progress[k] else datetime.min,
                reverse=True
            )
            
            # Keep only the latest 50
            keys_to_keep = sorted_keys[:50]
            keys_to_remove = [k for k in self.extraction_progress.keys() if k not in keys_to_keep]
            
            for key in keys_to_remove:
                del self.extraction_progress[key]

class TTSService:
    """Service for text-to-speech synthesis operations - Enhanced with highlighting"""
    
    def __init__(self, aws_service: AWSService):
        self.aws_service = aws_service
    
    async def synthesize_text(
        self, 
        text: str, 
        voice_id: str, 
        engine: str, 
        user: User, 
        db: Session,
        include_highlighting: bool = False
    ) -> SynthesizeResponse:
        """🎤 Synthesize text to speech using Amazon Polly with TTS highlighting"""
        text_length = len(text)
        
        if not user.deduct_characters(text_length):
            raise ValueError(f"Text length ({text_length}) exceeds remaining character limit ({user.remaining_chars})")
        
        try:
            logger.info(f"🎤 Starting TTS synthesis for user {user.username}: {text_length} chars with {voice_id}/{engine}")
            
            # Optimize text for TTS
            from textract_processor.highlighting import optimize_text_for_highlighting
            optimized_text = optimize_text_for_highlighting(text)
            
            # Split text into chunks optimized for TTS
            chunks = self.aws_service.split_text_smart(optimized_text)
            audio_segments = []
            speech_marks_list = []
            cumulative_time = 0.0
            
            for i, chunk in enumerate(chunks):
                logger.info(f"🔊 Processing chunk {i+1}/{len(chunks)}: {len(chunk)} chars")
                
                # Detect if chunk contains SSML markup
                is_ssml = chunk.strip().startswith('<speak>') and chunk.strip().endswith('</speak>')
                
                # Synthesize audio with proper SSML handling
                audio_params = {
                    "Text": chunk,
                    "OutputFormat": "mp3",
                    "VoiceId": voice_id,
                    "Engine": engine
                }
                
                # Add TextType for SSML processing
                if is_ssml:
                    audio_params["TextType"] = "ssml"
                
                audio_response = await asyncio.to_thread(
                    self.aws_service.polly.synthesize_speech,
                    **audio_params
                )
                
                audio_stream = audio_response['AudioStream'].read()
                audio_segment = AudioSegment.from_file(io.BytesIO(audio_stream), format="mp3")
                audio_segments.append(audio_segment)
                
                # Generate speech marks for TTS synchronization with SSML support
                try:
                    # Speech mark types should include "ssml" for SSML markup processing
                    speech_mark_types = ["word", "sentence"]
                    if is_ssml:
                        speech_mark_types.append("ssml")
                    
                    marks_params = {
                        "Text": chunk,
                        "OutputFormat": "json",
                        "VoiceId": voice_id,
                        "Engine": engine,
                        "SpeechMarkTypes": speech_mark_types
                    }
                    
                    # Add TextType for SSML processing in speech marks
                    if is_ssml:
                        marks_params["TextType"] = "ssml"
                    
                    marks_response = await asyncio.to_thread(
                        self.aws_service.polly.synthesize_speech,
                        **marks_params
                    )
                    
                    marks_text = marks_response['AudioStream'].read().decode('utf-8')
                    chunk_marks = [json.loads(line) for line in marks_text.splitlines() if line.strip()]
                    
                    # Adjust timing for concatenated audio
                    for mark in chunk_marks:
                        mark['time'] += int(cumulative_time * 1000)
                    
                    speech_marks_list.extend(chunk_marks)
                    
                except Exception as marks_error:
                    logger.warning(f"⚠️ Could not generate speech marks for chunk {i+1}: {marks_error}")
                
                cumulative_time += len(audio_segment) / 1000.0
            
            # Combine audio segments
            combined_audio = sum(audio_segments)
            audio_buffer = io.BytesIO()
            combined_audio.export(audio_buffer, format="mp3")
            audio_bytes = audio_buffer.getvalue()
            
            # Upload to S3
            timestamp = int(time.time())
            audio_key = f"users/{user.user_id}/audio/{timestamp}.mp3"
            marks_key = f"users/{user.user_id}/speech_marks/{timestamp}.json"
            
            # Upload audio file
            await asyncio.to_thread(
                self.aws_service.s3.put_object,
                Bucket=self.aws_service.bucket_name,
                Key=audio_key,
                Body=audio_bytes,
                ContentType="audio/mpeg",
                Metadata={
                    "user_id": str(user.user_id),
                    "voice_id": voice_id,
                    "engine": engine,
                    "text_length": str(text_length),
                    "chunks": str(len(chunks))
                }
            )
            
            # Upload speech marks
            logger.info(f"🔍 Debug: Before creating marks_data, speech_marks_list length: {len(speech_marks_list)}")
            marks_data = "\n".join([json.dumps(mark) for mark in speech_marks_list])
            logger.info(f"🔍 Debug: marks_data created, length: {len(marks_data)} chars")
            await asyncio.to_thread(
                self.aws_service.s3.put_object,
                Bucket=self.aws_service.bucket_name,
                Key=marks_key,
                Body=marks_data,
                ContentType="application/json"
            )
            
            # Generate presigned URLs
            audio_url = self.aws_service.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.aws_service.bucket_name, "Key": audio_key},
                ExpiresIn=3600
            )
            
            speech_marks_url = self.aws_service.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.aws_service.bucket_name, "Key": marks_key},
                ExpiresIn=3600
            )
            
            # Generate highlighting if requested
            highlighting_map = None
            if include_highlighting and speech_marks_list:
                try:
                    highlighting_map = create_highlight_with_speech_marks(
                        optimized_text,
                        marks_data,
                        extraction_method="polly_synthesis"
                    )
                    logger.info(f"✅ Generated highlighting with {len(highlighting_map.segments)} segments")
                except Exception as highlight_error:
                    logger.warning(f"⚠️ Could not generate highlighting: {highlight_error}")
                    highlighting_map = create_basic_highlight_map(optimized_text, "polly_synthesis_fallback")
            
            # Commit the character deduction
            db.commit()
            
            duration = len(combined_audio) / 1000.0
            
            logger.info(f"✅ Synthesized {text_length} characters for user {user.username} in {duration:.1f}s")
            
            # Debug log speech marks
            logger.info(f"🔍 Debug: speech_marks_list length: {len(speech_marks_list)}")
            logger.info(f"🔍 Debug: include_highlighting: {include_highlighting}")
            logger.info(f"🔍 Debug: marks_data length: {len(marks_data)} chars")
            if speech_marks_list:
                logger.info(f"🔍 Debug: First speech mark: {speech_marks_list[0]}")
            
            # ALWAYS parse speech marks from marks_data to ensure we have the data
            final_speech_marks = []
            if marks_data:
                logger.info("🔧 Parsing speech marks from marks_data")
                try:
                    for line in marks_data.strip().split('\n'):
                        if line.strip():
                            final_speech_marks.append(json.loads(line))
                    logger.info(f"🔧 Parsed {len(final_speech_marks)} speech marks from marks_data")
                except Exception as parse_error:
                    logger.error(f"❌ Error parsing marks_data: {parse_error}")
                    final_speech_marks = []
            
            # If we still don't have speech marks but had speech_marks_list, use that
            if not final_speech_marks and speech_marks_list:
                final_speech_marks = speech_marks_list
                logger.info(f"🔧 Using original speech_marks_list with {len(final_speech_marks)} items")
            
            # Final debug before creating response
            logger.info(f"🎯 FINAL DEBUG: final_speech_marks type: {type(final_speech_marks)}")
            logger.info(f"🎯 FINAL DEBUG: final_speech_marks length: {len(final_speech_marks) if final_speech_marks else 'None'}")
            if final_speech_marks:
                logger.info(f"🎯 FINAL DEBUG: First item: {final_speech_marks[0]}")
            
            # FOR DEBUG: Create a simple test array if we have no speech marks
            if not final_speech_marks:
                final_speech_marks = [{"time": 0, "type": "test", "value": "debug_test"}]
                logger.info("🐛 DEBUG: Created test speech marks array")
            
            # Prepare response
            response = SynthesizeResponse(
                audio_url=audio_url,
                speech_marks_url=speech_marks_url,
                speech_marks=final_speech_marks,  # Use the final speech marks
                characters_used=text_length,
                remaining_chars=user.remaining_chars,
                duration_seconds=duration,
                voice_used=voice_id,
                engine_used=engine,
                chunks_processed=len(chunks)
            )
            
            # Debug the response object
            logger.info(f"🎯 RESPONSE DEBUG: response.speech_marks type: {type(response.speech_marks)}")
            logger.info(f"🎯 RESPONSE DEBUG: response.speech_marks value: {response.speech_marks}")
            
            # Always add speech marks raw data if available
            if marks_data:
                response.speech_marks_raw = marks_data
            
            # Add highlighting data if generated
            if highlighting_map:
                response.highlighting_map = highlighting_map.to_dict()
                response.precise_timing = True
            
            # FINAL DEBUG: Check what the response dict looks like
            response_dict = response.model_dump()
            logger.info(f"🎯 RESPONSE DICT DEBUG: speech_marks in dict: {response_dict.get('speech_marks')}")
            logger.info(f"🎯 RESPONSE DICT DEBUG: Full dict keys: {list(response_dict.keys())}")
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Synthesis error for user {user.username}: {str(e)}")
            db.rollback()
            raise

class StripeService:
    """Service for Stripe payment operations"""
    
    def __init__(self):
        stripe.api_key = config.STRIPE_API_KEY
        self.webhook_secret = config.STRIPE_WEBHOOK_SECRET
    
    async def create_checkout_session(self, price_id: str, username: str) -> str:
        """Create a Stripe checkout session for subscription"""
        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price": price_id,
                        "quantity": 1,
                    }
                ],
                mode="subscription",
                success_url="http://localhost:3000/success",
                cancel_url="http://localhost:3000/failed",
                client_reference_id=username,
            )
            
            logger.info(f"💳 Created checkout session for user {username}")
            return checkout_session.url
            
        except Exception as e:
            logger.error(f"❌ Stripe checkout error for user {username}: {str(e)}")
            raise
    
    def handle_webhook_event(self, payload: bytes, signature: str, db: Session) -> Dict[str, str]:
        """Handle Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
        except ValueError:
            logger.error("❌ Invalid payload in Stripe webhook")
            raise ValueError("Invalid payload")
        except stripe.error.SignatureVerificationError:
            logger.error("❌ Invalid signature in Stripe webhook")
            raise ValueError("Invalid signature")

        # Handle the event
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            username = session["client_reference_id"]
            user = db.query(User).filter(User.username == username).first()
            
            if user:
                subscription_id = session["customer"]
                user.stripe_subscription_id = subscription_id
                db.commit()
                logger.info(f"✅ Updated subscription ID for user {username}")

        elif event["type"] == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            # Find user by subscription ID and remove it
            user = db.query(User).filter(User.stripe_subscription_id == subscription["id"]).first()
            if user:
                user.stripe_subscription_id = None
                db.commit()
                logger.info(f"✅ Removed subscription ID for user {user.username}")

        return {"status": "success"}

class AnalyticsService:
    """Service for analytics and reporting - Enhanced for TTS"""
    
    def get_extraction_analytics(self, days: int = 7) -> AnalyticsResponse:
        """Get TTS extraction analytics"""
        # In a real implementation, you'd query your database for extraction history
        # For now, return enhanced mock data with TTS metrics
        
        return AnalyticsResponse(
            period_days=days,
            total_extractions=142,
            total_characters=425000,
            average_extraction_time=2.8,
            tts_optimized_extractions=138,
            methods_used={
                "textract": 85,
                "dom_semantic": 32,
                "dom_heuristic": 18,
                "reader_mode": 7
            },
            success_rate=0.97,
            average_confidence=0.86,
            most_common_sites=[
                {"domain": "wikipedia.org", "count": 28},
                {"domain": "medium.com", "count": 19},
                {"domain": "github.com", "count": 15},
                {"domain": "stackoverflow.com", "count": 12},
                {"domain": "docs.microsoft.com", "count": 8}
            ],
            content_types={
                "articles": 62,
                "blog_posts": 34,
                "documentation": 28,
                "news": 12,
                "academic": 6
            },
            # TTS-specific metrics
            highlighting_success_rate=0.94,
            average_segments_per_extraction=24,
            speech_marks_generated=89,
            total_audio_duration_minutes=1847
        )
    
    def get_extraction_methods(self) -> Dict[str, Any]:
        """Get available extraction methods and their TTS capabilities"""
        from textract_processor import health_check
        
        methods = [
            {
                "id": "textract",
                "name": "AWS Textract OCR",
                "description": "High-accuracy OCR with layout analysis - best for TTS quality",
                "speed": "medium",
                "accuracy": "very-high",
                "tts_optimized": True,
                "highlighting_support": True,
                "speech_marks_compatible": True,
                "available": True,
                "recommended_for": ["PDFs", "complex layouts", "high-quality TTS"]
            },
            {
                "id": "dom_semantic",
                "name": "DOM Semantic",
                "description": "Extract using semantic HTML elements - excellent for TTS",
                "speed": "fast",
                "accuracy": "high",
                "tts_optimized": True,
                "highlighting_support": True,
                "speech_marks_compatible": True,
                "available": True,
                "recommended_for": ["well-structured websites", "articles", "blogs"]
            },
            {
                "id": "dom_heuristic", 
                "name": "DOM Heuristic",
                "description": "Content analysis algorithms - good TTS results",
                "speed": "fast",
                "accuracy": "medium-high",
                "tts_optimized": True,
                "highlighting_support": True,
                "speech_marks_compatible": True,
                "available": True,
                "recommended_for": ["dynamic content", "mixed layouts"]
            },
            {
                "id": "reader_mode",
                "name": "Reader Mode",
                "description": "Clean content extraction - optimized for TTS reading",
                "speed": "fast",
                "accuracy": "medium",
                "tts_optimized": True,
                "highlighting_support": True,
                "speech_marks_compatible": True,
                "available": True,
                "recommended_for": ["cluttered pages", "news sites"]
            }
        ]
        
        return {
            "methods": methods,
            "default_strategy": "intelligent_fallback_tts_optimized",
            "health_status": {"status": "healthy"},
            "service_type": "TTS Content Extraction with Advanced Highlighting",
            "features": {
                "content_extraction": True,
                "highlighting": True,
                "speech_marks": True,
                "real_time_progress": True,
                "chunk_processing": True,
                "quality_analysis": True
            }
        }

# Global service instances
extraction_service = ExtractionService()
tts_service = TTSService(aws_service)
stripe_service = StripeService()
analytics_service = AnalyticsService()