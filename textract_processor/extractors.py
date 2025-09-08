import asyncio
import time
import logging
import re
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
import requests

from .config import ExtractionMethod, ContentType, DEFAULT_CONFIG
from .models import ExtractionResult, PageAnalysis
from .utils import URLValidator, ContentTypeDetector, TextCleaner, ContentAnalyzer

logger = logging.getLogger(__name__)

class BaseExtractor(ABC):
    def __init__(self, config=None):
        self.config = config or DEFAULT_CONFIG
    
    @abstractmethod
    async def extract(self, url: str, page_analysis: PageAnalysis = None, selection_text: Optional[str] = None) -> Optional[ExtractionResult]:
        pass
    
    def _create_result(self, text: str, method: ExtractionMethod, content_type: ContentType, 
                      processing_time: float, metadata: Dict[str, Any]) -> ExtractionResult:
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

    def _normalize_text(self, text: str) -> str:
        text = re.sub(r'[\uFEFF\u200B\u200C\u200D\u00AD\uFFFE\uFFFF]', '', text)
        text = re.sub(r'[\r\n\t]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

class TextractExtractor(BaseExtractor):
    def __init__(self, textract_client, config=None):
        super().__init__(config)
        self.textract = textract_client
    
    async def extract(self, url: str, page_analysis: PageAnalysis = None, selection_text: Optional[str] = None) -> Optional[ExtractionResult]:
        if not self.textract:
            logger.info("Textract client not available")
            return None
            
        start_time = time.time()
        content_type = page_analysis.content_type if page_analysis else ContentType.UNKNOWN
        
        try:
            logger.info(f"Starting Textract extraction for TTS: {url}")
            
            if selection_text:
                logger.info(f"Using provided selection text for extraction: {selection_text[:30]}... ({len(selection_text)} chars)")
                normalized_text = self._normalize_text(selection_text)
                if len(normalized_text) >= self.config.min_text_length:
                    processing_time = time.time() - start_time
                    metadata = {'method_specific': 'textract_selection', 'original_length': len(selection_text)}
                    return self._create_result(normalized_text, ExtractionMethod.TEXTRACT, content_type, processing_time, metadata)
                else:
                    logger.warning(f"Selection text too short after normalization: {len(normalized_text)} characters")
                    return None
            
            pdf_bytes = await self._render_page_to_pdf(url)
            if not pdf_bytes:
                return None
            
            if len(pdf_bytes) > self.config.max_pdf_size:
                logger.warning(f"PDF too large ({len(pdf_bytes)} bytes) for Textract")
                return None
            
            logger.info(f"Processing PDF with Textract ({len(pdf_bytes)} bytes)")
            
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.textract.analyze_document,
                    Document={'Bytes': pdf_bytes},
                    FeatureTypes=['LAYOUT', 'TABLES']
                ),
                timeout=self.config.textract_timeout
            )
            
            extracted_text = self._process_textract_response(response)
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
    
    async def _render_page_to_pdf(self, url: str) -> Optional[bytes]:
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
                    
                    try:
                        from .utils import apply_tts_content_filtering
                        success, _ = await apply_tts_content_filtering(page, url, await page.title())
                        if not success:
                            logger.warning("TTS content filtering failed during PDF rendering")
                            return None
                    except ImportError:
                        logger.warning("TTS content filtering not available")
                    
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
        text = ""
        blocks = response.get('Blocks', [])
        layout_blocks = [b for b in blocks if b.get('BlockType') == 'LAYOUT_TEXT' or b.get('BlockType') == 'LINE']
        
        for block in layout_blocks:
            if 'Text' in block:
                text += block['Text'] + " "
        
        return self._normalize_text(text)

class DOMExtractor(BaseExtractor):
    async def extract(self, url: str, page_analysis: PageAnalysis = None, selection_text: Optional[str] = None) -> Optional[ExtractionResult]:
        start_time = time.time()
        content_type = page_analysis.content_type if page_analysis else ContentType.UNKNOWN
        
        try:
            if selection_text:
                logger.info(f"Using provided selection text for DOM extraction: {selection_text[:30]}... ({len(selection_text)} chars)")
                normalized_text = self._normalize_text(selection_text)
                if len(normalized_text) >= self.config.min_text_length:
                    processing_time = time.time() - start_time
                    metadata = {'method_specific': 'dom_selection', 'original_length': len(selection_text)}
                    return self._create_result(normalized_text, ExtractionMethod.DOM_FALLBACK, content_type, processing_time, metadata)
                else:
                    logger.warning(f"Selection text too short after normalization: {len(normalized_text)} characters")
                    return None
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    context = await browser.new_context()
                    page = await context.new_page()
                    await page.goto(url, wait_until="domcontentloaded", timeout=self.config.page_load_timeout)
                    
                    content = await page.content()
                    soup = BeautifulSoup(content, 'html.parser')
                    text = self._extract_dom_content(soup)
                    normalized_text = self._normalize_text(text)
                    
                    if len(normalized_text) >= self.config.min_text_length:
                        processing_time = time.time() - start_time
                        metadata = {'url': url, 'method_specific': 'dom_basic'}
                        result = self._create_result(
                            normalized_text, ExtractionMethod.DOM_FALLBACK, content_type,
                            processing_time, metadata
                        )
                        logger.info(f"DOM extraction successful: {result.char_count} chars in {processing_time:.2f}s")
                        return result
                    else:
                        logger.warning(f"DOM extracted text too short: {len(normalized_text)} characters")
                        return None
                finally:
                    await browser.close()
        except Exception as e:
            logger.error(f"DOM extraction failed for {url}: {str(e)}")
            return None
    
    def _extract_dom_content(self, soup: BeautifulSoup) -> str:
        for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()
        text = soup.get_text(separator=' ', strip=True)
        return text

class DOMSemanticExtractor(DOMExtractor):
    async def extract(self, url: str, page_analysis: PageAnalysis = None, selection_text: Optional[str] = None) -> Optional[ExtractionResult]:
        start_time = time.time()
        content_type = page_analysis.content_type if page_analysis else ContentType.UNKNOWN
        
        try:
            if selection_text:
                logger.info(f"Using provided selection text for semantic extraction: {selection_text[:30]}... ({len(selection_text)} chars)")
                normalized_text = self._normalize_text(selection_text)
                if len(normalized_text) >= self.config.min_text_length:
                    processing_time = time.time() - start_time
                    metadata = {'method_specific': 'dom_semantic_selection', 'original_length': len(selection_text)}
                    return self._create_result(normalized_text, ExtractionMethod.DOM_SEMANTIC, content_type, processing_time, metadata)
                else:
                    logger.warning(f"Selection text too short after normalization: {len(normalized_text)} characters")
                    return None
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    context = await browser.new_context()
                    page = await context.new_page()
                    await page.goto(url, wait_until="domcontentloaded", timeout=self.config.page_load_timeout)
                    
                    content = await page.content()
                    soup = BeautifulSoup(content, 'html.parser')
                    text = self._extract_semantic_content(soup)
                    normalized_text = self._normalize_text(text)
                    
                    if len(normalized_text) >= self.config.min_text_length:
                        processing_time = time.time() - start_time
                        metadata = {'url': url, 'method_specific': 'dom_semantic'}
                        result = self._create_result(
                            normalized_text, ExtractionMethod.DOM_SEMANTIC, content_type,
                            processing_time, metadata
                        )
                        logger.info(f"DOM semantic extraction successful: {result.char_count} chars in {processing_time:.2f}s")
                        return result
                    else:
                        logger.warning(f"DOM semantic extracted text too short: {len(normalized_text)} characters")
                        return None
                finally:
                    await browser.close()
        except Exception as e:
            logger.error(f"DOM semantic extraction failed for {url}: {str(e)}")
            return None
    
    def _extract_semantic_content(self, soup: BeautifulSoup) -> str:
        content_elements = soup.find_all(['article', 'main', 'section', 'p'])
        text = ' '.join(elem.get_text(strip=True) for elem in content_elements if elem.get_text(strip=True))
        return text

class DOMHeuristicExtractor(DOMExtractor):
    async def extract(self, url: str, page_analysis: PageAnalysis = None, selection_text: Optional[str] = None) -> Optional[ExtractionResult]:
        start_time = time.time()
        content_type = page_analysis.content_type if page_analysis else ContentType.UNKNOWN
        
        try:
            if selection_text:
                logger.info(f"Using provided selection text for heuristic extraction: {selection_text[:30]}... ({len(selection_text)} chars)")
                normalized_text = self._normalize_text(selection_text)
                if len(normalized_text) >= self.config.min_text_length:
                    processing_time = time.time() - start_time
                    metadata = {'method_specific': 'dom_heuristic_selection', 'original_length': len(selection_text)}
                    return self._create_result(normalized_text, ExtractionMethod.DOM_HEURISTIC, content_type, processing_time, metadata)
                else:
                    logger.warning(f"Selection text too short after normalization: {len(normalized_text)} characters")
                    return None
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    context = await browser.new_context()
                    page = await context.new_page()
                    await page.goto(url, wait_until="domcontentloaded", timeout=self.config.page_load_timeout)
                    
                    content = await page.content()
                    soup = BeautifulSoup(content, 'html.parser')
                    text = self._extract_heuristic_content(soup)
                    normalized_text = self._normalize_text(text)
                    
                    if len(normalized_text) >= self.config.min_text_length:
                        processing_time = time.time() - start_time
                        metadata = {'url': url, 'method_specific': 'dom_heuristic'}
                        result = self._create_result(
                            normalized_text, ExtractionMethod.DOM_HEURISTIC, content_type,
                            processing_time, metadata
                        )
                        logger.info(f"DOM heuristic extraction successful: {result.char_count} chars in {processing_time:.2f}s")
                        return result
                    else:
                        logger.warning(f"DOM heuristic extracted text too short: {len(normalized_text)} characters")
                        return None
                finally:
                    await browser.close()
        except Exception as e:
            logger.error(f"DOM heuristic extraction failed for {url}: {str(e)}")
            return None
    
    def _extract_heuristic_content(self, soup: BeautifulSoup) -> str:
        content_elements = soup.find_all(['div', 'p', 'article'], class_=['content', 'main-content', 'post', 'article'])
        text = ' '.join(elem.get_text(strip=True) for elem in content_elements if elem.get_text(strip=True))
        return text

class ReaderModeExtractor(DOMExtractor):
    async def extract(self, url: str, page_analysis: PageAnalysis = None, selection_text: Optional[str] = None) -> Optional[ExtractionResult]:
        start_time = time.time()
        content_type = page_analysis.content_type if page_analysis else ContentType.UNKNOWN
        
        try:
            if selection_text:
                logger.info(f"Using provided selection text for reader mode extraction: {selection_text[:30]}... ({len(selection_text)} chars)")
                normalized_text = self._normalize_text(selection_text)
                if len(normalized_text) >= self.config.min_text_length:
                    processing_time = time.time() - start_time
                    metadata = {'method_specific': 'reader_mode_selection', 'original_length': len(selection_text)}
                    return self._create_result(normalized_text, ExtractionMethod.READER_MODE, content_type, processing_time, metadata)
                else:
                    logger.warning(f"Selection text too short after normalization: {len(normalized_text)} characters")
                    return None
            
            response = requests.get(url, timeout=self.config.page_load_timeout / 1000)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            text = self._extract_reader_mode_content(soup)
            normalized_text = self._normalize_text(text)
            
            if len(normalized_text) >= self.config.min_text_length:
                processing_time = time.time() - start_time
                metadata = {'url': url, 'method_specific': 'reader_mode'}
                result = self._create_result(
                    normalized_text, ExtractionMethod.READER_MODE, content_type,
                    processing_time, metadata
                )
                logger.info(f"Reader mode extraction successful: {result.char_count} chars in {processing_time:.2f}s")
                return result
            else:
                logger.warning(f"Reader mode extracted text too short: {len(normalized_text)} characters")
                return None
        except Exception as e:
            logger.error(f"Reader mode extraction failed for {url}: {str(e)}")
            return None
    
    def _extract_reader_mode_content(self, soup: BeautifulSoup) -> str:
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        main_content = soup.find(['article', 'main']) or soup.body
        if main_content:
            text = main_content.get_text(separator=' ', strip=True)
        else:
            text = soup.get_text(separator=' ', strip=True)
        return text

__all__ = [
    'BaseExtractor',
    'TextractExtractor',
    'DOMExtractor',
    'DOMSemanticExtractor',
    'DOMHeuristicExtractor',
    'ReaderModeExtractor'
]