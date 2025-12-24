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

from .config import config, TierConfig
from .models import (
    ExtractionProgress, ExtractionPreview, ExtractResponseEnhanced,
    SynthesizeResponse, AnalyticsResponse
)
from textract_processor import ContentExtractorManager, extract_content
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
            
            self.s3.list_buckets()
            self.polly.describe_voices(LanguageCode="en-US")
            
            logger.info("✅ AWS services initialized successfully")
            
        except (NoCredentialsError, ClientError) as e:
            logger.error(f"❌ AWS configuration error: {str(e)}")
            raise ValueError("Invalid AWS credentials or configuration")
    
    async def setup_bucket(self):
        """Setup S3 bucket with proper configuration for TTS files"""
        try:
            self.s3.head_bucket(Bucket=self.bucket_name)
            logger.info(f"✅ Bucket {self.bucket_name} already exists")
        except ClientError as e:
            error_code = int(e.response["Error"]["Code"])
            if error_code == 404:
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
                    
                    self.s3.put_public_access_block(
                        Bucket=self.bucket_name,
                        PublicAccessBlockConfiguration={
                            "BlockPublicAcls": True,
                            "IgnorePublicAcls": True,
                            "BlockPublicPolicy": True,
                            "RestrictPublicBuckets": True
                        }
                    )
                    
                    self.s3.put_bucket_versioning(
                        Bucket=self.bucket_name,
                        VersioningConfiguration={"Status": "Enabled"}
                    )
                    
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
        
        sentences = text.replace('\n', ' ').split('. ')
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
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
                
                supported_engines = voice["SupportedEngines"]
                
                if "standard" in supported_engines:
                    standard_voices.append(voice_data)
                
                if "neural" in supported_engines:
                    neural_voices.append({**voice_data, "quality": "high"})
                
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
            
            self.extraction_progress[extraction_id] = [
                ExtractionProgress(
                    status="starting",
                    message="🎯 Initializing TTS content extraction...",
                    progress=0.0
                )
            ]
            
            self._update_progress(extraction_id, ExtractionProgress(
                status="processing",
                message="📄 Analyzing webpage and extracting TTS-optimized content...",
                progress=0.3
            ))
            
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
            
            self._update_progress(extraction_id, ExtractionProgress(
                status="processing",
                message="✅ Validating extracted TTS content...",
                progress=0.7,
                method=method
            ))
            
            if not user.deduct_characters(text_length):
                self._update_progress(extraction_id, ExtractionProgress(
                    status="failed",
                    message=f"❌ Text length ({text_length}) exceeds remaining character limit",
                    progress=1.0
                ))
                raise ValueError(f"Text length ({text_length}) exceeds remaining character limit ({user.remaining_chars})")
            
            db.commit()
            
            self._update_progress(extraction_id, ExtractionProgress(
                status="completed",
                message="✅ Content extraction completed successfully",
                progress=1.0,
                method=method
            ))
            
            logger.info(f"✅ Extraction completed for user {user.username}: "
                       f"{text_length} characters using {method} in {processing_time:.2f}s")
            
            response_data = {
                "text": extracted_text,
                "characters_used": text_length,
                "remaining_chars": user.remaining_chars,
                "extraction_method": method,
                "word_count": len(extracted_text.split()),
                "processing_time": processing_time
            }
            
            if include_metadata:
                response_data["metadata"] = {
                    "url": url,
                    "extraction_id": extraction_id,
                    "user_id": str(user.user_id),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "prefer_textract": prefer_textract,
                    "optimized_for_tts": True
                }
            
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
            
            extracted_text, method = await extract_content(url)
            
            if not extracted_text:
                raise ValueError("Could not extract content from the provided URL")
            
            preview = extracted_text[:500]
            if len(extracted_text) > 500:
                preview += "..."
            
            confidence_map = {
                "textract": 0.9,
                "dom_semantic": 0.8,
                "dom_heuristic": 0.7,
                "reader_mode": 0.6,
                "dom_fallback": 0.4
            }
            
            confidence = confidence_map.get(method, 0.5)
            
            word_count = len(extracted_text.split())
            estimated_minutes = word_count / 150
            
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
            "history": [p.dict() for p in progress_list[-5:]]
        }
    
    def _update_progress(self, extraction_id: str, progress: ExtractionProgress):
        """Update extraction progress"""
        if extraction_id in self.extraction_progress:
            self.extraction_progress[extraction_id].append(progress)
    
    def _cleanup_progress_data(self):
        """Clean up old progress data to prevent memory leaks"""
        if len(self.extraction_progress) > 100:
            sorted_keys = sorted(
                self.extraction_progress.keys(),
                key=lambda k: self.extraction_progress[k][-1].timestamp if self.extraction_progress[k] else datetime.min,
                reverse=True
            )
            
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
        db: Session
    ) -> SynthesizeResponse:
        """Synthesize text to speech using Amazon Polly with clean speech marks"""
        text_length = len(text)

        # Check if user has enough credits (credit system)
        can_use, reason = user.can_use_credits(text_length)
        if not can_use:
            logger.warning(f"🚫 User {user.username} ({user.tier.value.lower()}) insufficient credits: {reason}")
            raise ValueError(reason)

        # Check if user's tier supports the requested engine
        if not TierConfig.can_use_engine(user.tier.value, engine):
            if engine == "neural" and not config.NEURAL_VOICES_ENABLED:
                raise ValueError("Neural voices are not yet available. Coming soon for Pro users!")
            raise ValueError(f"Your {user.tier.value.lower()} tier does not support {engine} engine. Please upgrade.")

        try:
            logger.info(f"🎤 Starting TTS synthesis for user {user.username} ({user.tier.value.lower()}): {text_length} chars with {voice_id}/{engine}")
            
            chunks = self.aws_service.split_text_smart(text)
            audio_segments = []
            speech_marks_list = []
            cumulative_time_ms = 0
            
            for i, chunk in enumerate(chunks):
                logger.info(f"🔊 Processing chunk {i+1}/{len(chunks)}: {len(chunk)} chars")
                
                audio_params = {
                    "Text": chunk,
                    "OutputFormat": "mp3",
                    "VoiceId": voice_id,
                    "Engine": engine
                }
                
                audio_response = await asyncio.to_thread(
                    self.aws_service.polly.synthesize_speech,
                    **audio_params
                )
                
                audio_stream = audio_response['AudioStream'].read()
                audio_segment = AudioSegment.from_file(io.BytesIO(audio_stream), format="mp3")
                audio_segments.append(audio_segment)
                
                marks_params = {
                    "Text": chunk,
                    "OutputFormat": "json",
                    "VoiceId": voice_id,
                    "Engine": engine,
                    "SpeechMarkTypes": ["word", "sentence"]
                }
                
                marks_response = await asyncio.to_thread(
                    self.aws_service.polly.synthesize_speech,
                    **marks_params
                )
                
                marks_text = marks_response['AudioStream'].read().decode('utf-8')
                chunk_marks = [json.loads(line) for line in marks_text.splitlines() if line.strip()]
                
                for mark in chunk_marks:
                    mark['time'] += cumulative_time_ms
                
                speech_marks_list.extend(chunk_marks)
                cumulative_time_ms += int(len(audio_segment))
            
            combined_audio = sum(audio_segments)
            audio_buffer = io.BytesIO()
            combined_audio.export(audio_buffer, format="mp3")
            audio_bytes = audio_buffer.getvalue()
            
            timestamp = int(time.time())
            audio_key = f"users/{user.user_id}/audio/{timestamp}.mp3"
            
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
                    "text_length": str(text_length)
                }
            )
            
            audio_url = self.aws_service.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.aws_service.bucket_name, "Key": audio_key},
                ExpiresIn=3600
            )

            # Deduct credits based on character count (1 credit = 1,000 chars)
            user.deduct_credits_for_characters(text_length)

            # Also deduct from legacy remaining_chars for backward compatibility
            user.deduct_characters(text_length)

            db.commit()

            duration = len(combined_audio) / 1000.0

            logger.info(f"✅ Synthesized {text_length} characters for user {user.username} ({user.tier.value.lower()}) in {duration:.1f}s - Credits remaining: {user.credit_balance}")

            # Calculate credits used for this request
            credits_used = (text_length + 999) // 1000

            return SynthesizeResponse(
                audio_url=audio_url,
                speech_marks=speech_marks_list,
                characters_used=text_length,
                remaining_chars=user.remaining_chars,  # Legacy field
                duration_seconds=duration,
                voice_used=voice_id,
                engine_used=engine,
                # Credit system stats
                credit_balance=user.credit_balance,
                credits_used=credits_used,
                # Legacy tier-based usage stats (for backward compatibility)
                monthly_usage=user.monthly_usage,
                monthly_cap=user.get_monthly_cap(),
                usage_percentage=round(user.get_usage_percentage(), 2) if user.get_monthly_cap() > 0 else 0,
                usage_reset_date=user.usage_reset_date.isoformat() if user.usage_reset_date else None,
                tier=user.tier.value.lower(),
                is_near_limit=user.is_near_limit() if user.get_monthly_cap() > 0 else False
            )
            
        except Exception as e:
            logger.error(f"❌ Synthesis error for user {user.username}: {str(e)}")
            db.rollback()
            raise

class StripeService:
    """Service for Stripe payment operations with tier management"""

    def __init__(self):
        stripe.api_key = config.STRIPE_API_KEY
        self.webhook_secret = config.STRIPE_WEBHOOK_SECRET

    def get_tier_from_price_id(self, price_id: str) -> str:
        """Determine tier from Stripe price ID"""
        premium_ids = [
            config.STRIPE_PRICE_ID_PREMIUM_MONTHLY,
            config.STRIPE_PRICE_ID_PREMIUM_YEARLY
        ]
        pro_ids = [
            config.STRIPE_PRICE_ID_PRO_MONTHLY,
            config.STRIPE_PRICE_ID_PRO_YEARLY
        ]

        if price_id in premium_ids:
            return "premium"
        elif price_id in pro_ids:
            return "pro"
        else:
            return "free"

    async def create_checkout_session(self, price_id: str, username: str, user_email: str = None) -> str:
        """Create a Stripe checkout session for subscription with tier tracking"""
        try:
            tier = self.get_tier_from_price_id(price_id)

            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price": price_id,
                        "quantity": 1,
                    }
                ],
                mode="subscription",
                success_url="http://localhost:3000/success?session_id={CHECKOUT_SESSION_ID}",
                cancel_url="http://localhost:3000/pricing",
                client_reference_id=username,
                customer_email=user_email,
                metadata={
                    "username": username,
                    "tier": tier,
                    "price_id": price_id
                }
            )

            logger.info(f"💳 Created {tier} checkout session for user {username}")
            return checkout_session.url

        except Exception as e:
            logger.error(f"❌ Stripe checkout error for user {username}: {str(e)}")
            raise

    async def create_credit_checkout_session(self, credits: int, username: str, user_email: str = None) -> str:
        """
        Create a Stripe checkout session for one-time credit purchase.

        Args:
            credits: Number of credits to purchase
            username: Username of the purchaser
            user_email: Email of the purchaser (optional)

        Returns:
            Checkout session URL
        """
        try:
            from app.config import CreditConfig

            # Calculate price and determine tier
            price = CreditConfig.calculate_price(credits)
            tier = CreditConfig.get_tier_for_credits(credits)

            # Create a dynamic price for the credit purchase
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": "usd",
                            "product_data": {
                                "name": f"{credits:,} TTS Credits",
                                "description": f"{tier.upper()} tier - {credits * 1000:,} characters"
                            },
                            "unit_amount": int(price * 100)  # Convert to cents
                        },
                        "quantity": 1
                    }
                ],
                mode="payment",  # One-time payment
                success_url="http://localhost:3000/success?session_id={CHECKOUT_SESSION_ID}",
                cancel_url="http://localhost:3000/pricing",
                client_reference_id=username,
                customer_email=user_email,
                metadata={
                    "username": username,
                    "credits": str(credits),
                    "tier": tier,
                    "purchase_type": "credits"
                }
            )

            logger.info(f"💳 Created credit checkout session for {credits} credits ({tier} tier) for user {username}")
            return checkout_session.url

        except Exception as e:
            logger.error(f"❌ Credit checkout error for user {username}: {str(e)}")
            raise

    def handle_webhook_event(self, payload: bytes, signature: str, db: Session) -> Dict[str, str]:
        """Handle Stripe webhook events with tier management"""
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

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            username = session.get("client_reference_id") or session.get("metadata", {}).get("username")
            user = db.query(User).filter(User.username == username).first()

            if user:
                metadata = session.get("metadata", {})
                purchase_type = metadata.get("purchase_type", "subscription")

                # Import UserTier enum
                from models import UserTier

                if purchase_type == "credits":
                    # Handle credit purchase
                    credits = int(metadata.get("credits", 0))
                    tier = metadata.get("tier", "free")

                    # Add credits to user balance and update tier
                    # Light tier users get Premium features (just fewer credits)
                    if tier == "light" or tier == "premium":
                        user.purchase_credits(credits, UserTier.PREMIUM)
                    elif tier == "pro":
                        user.purchase_credits(credits, UserTier.PRO)

                    db.commit()
                    logger.info(f"✅ Added {credits} credits to user {username} ({tier} tier)")

                else:
                    # Handle subscription purchase (legacy)
                    subscription_id = session.get("subscription")
                    tier = metadata.get("tier", "free")
                    price_id = metadata.get("price_id", "")

                    # Update user subscription and tier
                    user.stripe_subscription_id = subscription_id
                    user.stripe_price_id = price_id

                    if tier == "premium":
                        user.tier = UserTier.PREMIUM
                    elif tier == "pro":
                        user.tier = UserTier.PRO

                    # Reset monthly usage on new subscription
                    user.monthly_usage = 0

                    db.commit()
                    logger.info(f"✅ Updated subscription and tier ({tier}) for user {username}")

        elif event["type"] == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            user = db.query(User).filter(User.stripe_subscription_id == subscription["id"]).first()
            if user:
                # Downgrade to free tier
                from models import UserTier
                user.tier = UserTier.FREE
                user.stripe_subscription_id = None
                user.stripe_price_id = None
                db.commit()
                logger.info(f"✅ Downgraded user {user.username} to free tier")

        elif event["type"] == "customer.subscription.updated":
            subscription = event["data"]["object"]
            user = db.query(User).filter(User.stripe_subscription_id == subscription["id"]).first()
            if user:
                # Get the price ID from the subscription
                items = subscription.get("items", {}).get("data", [])
                if items:
                    price_id = items[0].get("price", {}).get("id", "")
                    tier = self.get_tier_from_price_id(price_id)

                    from models import UserTier
                    if tier == "premium":
                        user.tier = UserTier.PREMIUM
                    elif tier == "pro":
                        user.tier = UserTier.PRO

                    user.stripe_price_id = price_id
                    db.commit()
                    logger.info(f"✅ Updated tier ({tier}) for user {user.username}")

        return {"status": "success"}

class AnalyticsService:
    """Service for analytics and reporting"""
    
    def get_extraction_analytics(self, days: int = 7) -> AnalyticsResponse:
        """Get extraction analytics"""
        return AnalyticsResponse(
            period_days=days,
            total_extractions=142,
            total_characters=425000,
            average_extraction_time=2.8,
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
            }
        )
    
    def get_extraction_methods(self) -> Dict[str, Any]:
        """Get available extraction methods"""
        methods = [
            {
                "id": "textract",
                "name": "AWS Textract OCR",
                "description": "High-accuracy OCR with layout analysis",
                "speed": "medium",
                "accuracy": "very-high",
                "available": True,
                "recommended_for": ["PDFs", "complex layouts"]
            },
            {
                "id": "dom_semantic",
                "name": "DOM Semantic",
                "description": "Extract using semantic HTML elements",
                "speed": "fast",
                "accuracy": "high",
                "available": True,
                "recommended_for": ["well-structured websites", "articles", "blogs"]
            },
            {
                "id": "dom_heuristic", 
                "name": "DOM Heuristic",
                "description": "Content analysis algorithms",
                "speed": "fast",
                "accuracy": "medium-high",
                "available": True,
                "recommended_for": ["dynamic content", "mixed layouts"]
            },
            {
                "id": "reader_mode",
                "name": "Reader Mode",
                "description": "Clean content extraction",
                "speed": "fast",
                "accuracy": "medium",
                "available": True,
                "recommended_for": ["cluttered pages", "news sites"]
            }
        ]
        
        return {
            "methods": methods,
            "default_strategy": "intelligent_fallback",
            "health_status": {"status": "healthy"},
            "service_type": "Content Extraction with TTS",
            "features": {
                "content_extraction": True,
                "speech_synthesis": True,
                "real_time_progress": True
            }
        }

extraction_service = ExtractionService()
tts_service = TTSService(aws_service)
stripe_service = StripeService()
analytics_service = AnalyticsService()