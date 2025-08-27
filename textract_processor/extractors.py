import asyncio
import time
import logging
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from .config import ExtractionMethod, ContentType, DEFAULT_CONFIG
from .models import ExtractionResult, PageAnalysis
from .utils import URLValidator, ContentTypeDetector, TextCleaner, ContentAnalyzer

logger = logging.getLogger(__name__)

class BaseExtractor(ABC):
    """Abstract base class for content extractors"""
    
    def __init__(self, config=None):
        self.config = config or DEFAULT_CONFIG
    
    @abstractmethod
    async def extract(self, url: str, page_analysis: PageAnalysis = None) -> Optional[ExtractionResult]:
        """Extract content from URL"""
        pass
    
    def _create_result(self, text: str, method: ExtractionMethod, content_type: ContentType, 
                      processing_time: float, metadata: Dict[str, Any]) -> ExtractionResult:
        """Create standardized extraction result"""
        cleaned_text = TextCleaner.clean_for_tts(text)
        confidence = ContentAnalyzer.score_content_quality(cleaned_text, method.value)
        
        return ExtractionResult(
            text=cleaned_text,
            method=method,
            content_type=content_type,
            confidence=confidence,
            word_count=len(cleaned_text.split()),
            char_count=len(cleaned_text),
            processing_time=processing_time,
            metadata=metadata
        )

class TextractExtractor(BaseExtractor):
    """AWS Textract-based content extractor for high-accuracy TTS content"""
    
    def __init__(self, textract_client, config=None):
        super().__init__(config)
        self.textract = textract_client
    
    async def extract(self, url: str, page_analysis: PageAnalysis = None, selection_text: Optional[str] = None) -> Optional[ExtractionResult]:  # NEW: Added selection_text parameter
        """Extract content using AWS Textract OCR"""
        if not self.textract:
            logger.info("Textract client not available")
            return None
            
        start_time = time.time()
        content_type = page_analysis.content_type if page_analysis else ContentType.UNKNOWN
        
        try:
            logger.info(f"Starting Textract extraction for TTS: {url}")
            
            # NEW: Handle selection text if provided
            if selection_text:
                logger.info(f"Using provided selection text for extraction: {selection_text[:30]}... ({len(selection_text)} chars)")
                normalized_text = self._normalize_text(selection_text)  # NEW: Normalize selection text
                if len(normalized_text) >= self.config.min_text_length:
                    processing_time = time.time() - start_time
                    metadata = {'method_specific': 'textract_selection', 'original_length': len(selection_text)}
                    return self._create_result(normalized_text, ExtractionMethod.TEXTRACT, content_type, processing_time, metadata)
                else:
                    logger.warning(f"Selection text too short after normalization: {len(normalized_text)} characters")
                    return None
            
            # Generate PDF from webpage with TTS content filtering
            pdf_bytes = await self._render_page_to_pdf(url)
            if not pdf_bytes:
                return None
            
            if len(pdf_bytes) > self.config.max_pdf_size:
                logger.warning(f"PDF too large ({len(pdf_bytes)} bytes) for Textract")
                return None
            
            # Process with Textract
            logger.info(f"Processing PDF with Textract ({len(pdf_bytes)} bytes)")
            
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.textract.analyze_document,
                    Document={'Bytes': pdf_bytes},
                    FeatureTypes=['LAYOUT', 'TABLES']
                ),
                timeout=self.config.textract_timeout
            )
            
            # Extract and process text
            extracted_text = self._process_textract_response(response)
            
            # UPDATED: Apply additional normalization to match frontend expectations
            normalized_text = self._normalize_text(extracted_text)
            
            if len(normalized_text) >= self.config.min_text_length:
                processing_time = time.time() - start_time
                
                metadata = {
                    'pdf_size': len(pdf_bytes),
                    'textract_blocks': len(response.get('Blocks', [])),
                    'url': url,
                    'method_specific': 'textract_layout_analysis_with_tts_filtering'
                }
                
                result = self._create_result(
                    normalized_text, ExtractionMethod.TEXTRACT, content_type,
                    processing_time, metadata
                )
                
                logger.info(f"Textract extraction successful: {result.char_count} chars in {processing_time:.2f}s")
                return result
            else:
                logger.warning(f"Textract extracted text too short: {len(normalized_text)} characters")
                return None
                
        except asyncio.TimeoutError:
            logger.error(f"Textract processing timeout for {url}")
            return None
        except Exception as e:
            logger.error(f"Textract extraction failed for {url}: {str(e)}")
            return None
    
    def _normalize_text(self, text: str) -> str:  # NEW: Added consistent normalization method to match frontend (e.g., remove invisible chars, collapse whitespace)
        """Normalize text to match frontend processing"""
        # Remove invisible Unicode characters
        text = re.sub(r'[\uFEFF\u200B\u200C\u200D\u00AD\uFFFE\uFFFF]', '', text)
        # Convert line breaks/tabs to spaces
        text = re.sub(r'[\r\n\t]', ' ', text)
        # Collapse consecutive whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    async def _render_page_to_pdf(self, url: str) -> Optional[bytes]:
        """Render webpage to PDF for Textract processing with enterprise TTS content filtering"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-extensions',
                        '--disable-plugins'
                    ]
                )
                
                try:
                    user_agent = self.config.user_agents[0] if hasattr(self.config, 'user_agents') and self.config.user_agents else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                    
                    context = await browser.new_context(
                        user_agent=user_agent,
                        viewport={"width": 1200, "height": 800}
                    )
                    
                    page = await context.new_page()
                    
                    await page.set_extra_http_headers({
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'DNT': '1'
                    })
                    
                    await page.goto(url, wait_until="domcontentloaded", timeout=self.config.page_load_timeout)
                    
                    # UPDATED: Apply TTS content filtering before PDF generation (with site-specific exclusions)
                    success, filtered_text = await apply_tts_content_filtering(page, url, await page.title())
                    if not success:
                        logger.warning("TTS content filtering failed during PDF rendering")
                        return None
                    
                    # Generate PDF
                    pdf_bytes = await page.pdf(
                        format='A4',
                        print_background=True,
                        prefer_css_page_size=True,
                        timeout=self.config.pdf_render_timeout
                    )
                    
                    logger.info(f"PDF rendered successfully ({len(pdf_bytes)} bytes)")
                    return pdf_bytes
                    
                except PlaywrightTimeoutError as e:
                    logger.error(f"PDF render timeout: {str(e)}")
                    return None
                except Exception as e:
                    logger.error(f"PDF rendering failed: {str(e)}")
                    return None
                
                finally:
                    await browser.close()
                    
        except Exception as e:
            logger.error(f"Playwright setup failed for PDF rendering: {str(e)}")
            return None
    
    def _process_textract_response(self, response: Dict[str, Any]) -> str:
        """Process Textract response to extract clean text for TTS"""
        text = ""
        blocks = response.get('Blocks', [])
        
        # UPDATED: Prioritize layout-based extraction for better TTS flow
        layout_blocks = [b for b in blocks if b.get('BlockType') == 'LAYOUT_TEXT' or b.get('BlockType') == 'LINE']
        
        for block in layout_blocks:
            if 'Text' in block:
                text += block['Text'] + " "
        
        return self._normalize_text(text)  # UPDATED: Apply normalization

# Other classes remain unchanged, but update ContentAnalyzer and TextCleaner if needed to match frontend normalization logic

# Global instances
# ... (unchanged)