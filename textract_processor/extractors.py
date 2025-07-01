"""
Content extraction implementations for different methods
"""
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
    
    async def extract(self, url: str, page_analysis: PageAnalysis = None) -> Optional[ExtractionResult]:
        """Extract content using AWS Textract OCR"""
        if not self.textract:
            logger.info("Textract client not available")
            return None
            
        start_time = time.time()
        content_type = page_analysis.content_type if page_analysis else ContentType.UNKNOWN
        
        try:
            logger.info(f"Starting Textract extraction for TTS: {url}")
            
            # Generate PDF from webpage
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
            
            if len(extracted_text) >= self.config.min_text_length:
                processing_time = time.time() - start_time
                
                metadata = {
                    'pdf_size': len(pdf_bytes),
                    'textract_blocks': len(response.get('Blocks', [])),
                    'url': url,
                    'method_specific': 'textract_layout_analysis'
                }
                
                result = self._create_result(
                    extracted_text, ExtractionMethod.TEXTRACT, content_type,
                    processing_time, metadata
                )
                
                logger.info(f"Textract extraction successful: {result.char_count} chars in {processing_time:.2f}s")
                return result
            else:
                logger.warning(f"Textract extracted text too short: {len(extracted_text)} characters")
                return None
                
        except asyncio.TimeoutError:
            logger.error(f"Textract processing timeout for {url}")
            return None
        except Exception as e:
            logger.error(f"Textract extraction failed for {url}: {str(e)}")
            return None
    
    async def _render_page_to_pdf(self, url: str) -> Optional[bytes]:
        """Render webpage to PDF for Textract processing"""
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
                    page = await browser.new_page()
                    await page.set_user_agent(self.config.user_agents[0])
                    await page.set_viewport_size({"width": 1200, "height": 800})
                    
                    # Enhanced page setup for better content rendering
                    await page.set_extra_http_headers({
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'DNT': '1'
                    })
                    
                    # Navigate with enhanced error handling
                    try:
                        await page.goto(url, wait_until="networkidle", timeout=self.config.page_load_timeout)
                    except PlaywrightTimeoutError:
                        logger.warning(f"Page load timeout for {url}, trying with domcontentloaded")
                        await page.goto(url, wait_until="domcontentloaded", timeout=self.config.page_load_timeout)
                    
                    # Wait for dynamic content and remove overlays
                    await page.wait_for_timeout(self.config.content_load_wait)
                    await self._remove_overlays(page)
                    
                    # Generate PDF with optimized settings for text extraction
                    pdf_bytes = await page.pdf(
                        format='A4',
                        print_background=False,
                        margin={'top': '1cm', 'right': '1cm', 'bottom': '1cm', 'left': '1cm'},
                        prefer_css_page_size=True
                    )
                    
                    return pdf_bytes
                    
                finally:
                    await browser.close()
                    
        except Exception as e:
            logger.error(f"Failed to render page to PDF: {str(e)}")
            return None
    
    async def _remove_overlays(self, page):
        """Remove overlays and popups that interfere with TTS content"""
        try:
            await page.evaluate('''
                () => {
                    const overlaySelectors = [
                        '[class*="overlay"]', '[class*="modal"]', '[class*="popup"]',
                        '[class*="cookie"]', '[class*="gdpr"]', '[class*="consent"]',
                        '[class*="newsletter"]', '[class*="subscribe"]', '[id*="overlay"]',
                        '[id*="modal"]', '[id*="popup"]', '.fixed', '[style*="position: fixed"]'
                    ];
                    
                    overlaySelectors.forEach(selector => {
                        document.querySelectorAll(selector).forEach(el => {
                            const style = window.getComputedStyle(el);
                            if (style.position === 'fixed' || style.position === 'absolute') {
                                if (style.zIndex > 1000 || style.display === 'block') {
                                    el.remove();
                                }
                            }
                        });
                    });
                    
                    // Remove elements that cover most of the screen
                    document.querySelectorAll('*').forEach(el => {
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        if (rect.width > window.innerWidth * 0.8 && 
                            rect.height > window.innerHeight * 0.8 && 
                            (style.position === 'fixed' || style.position === 'absolute')) {
                            el.remove();
                        }
                    });
                }
            ''')
        except Exception as e:
            logger.warning(f"Error removing overlays: {str(e)}")
    
    def _process_textract_response(self, response: Dict) -> str:
        """Process Textract response with layout awareness for TTS"""
        try:
            # Group blocks by layout type
            layout_blocks = {}
            text_blocks = {}
            
            for block in response.get('Blocks', []):
                block_id = block['Id']
                block_type = block['BlockType']
                
                if block_type.startswith('LAYOUT_'):
                    layout_blocks[block_id] = block
                elif block_type in ['LINE', 'WORD'] and 'Text' in block:
                    text_blocks[block_id] = block
            
            # Identify main content areas and exclude headers/footers for TTS
            main_content_ids = set()
            header_footer_ids = set()
            
            for block_id, block in layout_blocks.items():
                if block['BlockType'] in ['LAYOUT_HEADER', 'LAYOUT_FOOTER']:
                    if 'Relationships' in block:
                        for rel in block['Relationships']:
                            if rel['Type'] == 'CHILD':
                                header_footer_ids.update(rel['Ids'])
                elif block['BlockType'] in ['LAYOUT_TEXT', 'LAYOUT_TITLE']:
                    if 'Relationships' in block:
                        for rel in block['Relationships']:
                            if rel['Type'] == 'CHILD':
                                main_content_ids.update(rel['Ids'])
            
            # Extract main content text optimized for TTS
            main_text_blocks = []
            
            for block_id, block in text_blocks.items():
                if (block_id not in header_footer_ids and 
                    (block_id in main_content_ids or not main_content_ids)):
                    
                    text = block['Text'].strip()
                    if text and len(text) > 2:
                        # Add proper spacing for TTS reading
                        if block['BlockType'] == 'LINE':
                            main_text_blocks.append(text + '\n')
                        else:
                            main_text_blocks.append(text + ' ')
            
            return ''.join(main_text_blocks)
            
        except Exception as e:
            logger.error(f"Error processing Textract response: {str(e)}")
            return ""


class DOMExtractor(BaseExtractor):
    """DOM-based content extractor with multiple strategies for TTS optimization"""
    
    async def extract(self, url: str, page_analysis: PageAnalysis = None) -> Optional[ExtractionResult]:
        """Extract content using DOM traversal with multiple strategies"""
        start_time = time.time()
        content_type = page_analysis.content_type if page_analysis else ContentType.UNKNOWN
        
        for attempt in range(self.config.max_retries):
            try:
                logger.info(f"Starting DOM extraction for TTS: {url} (attempt {attempt + 1})")
                
                async with async_playwright() as p:
                    browser = await p.chromium.launch(
                        headless=True,
                        args=[
                            '--no-sandbox',
                            '--disable-setuid-sandbox',
                            '--disable-dev-shm-usage',
                            '--disable-gpu',
                            '--disable-images',  # Faster loading
                            '--disable-javascript' if attempt > 0 else '',  # Try without JS on retry
                        ]
                    )
                    
                    try:
                        page = await browser.new_page()
                        
                        # Rotate user agents on retries
                        user_agent = self.config.user_agents[attempt % len(self.config.user_agents)]
                        await page.set_user_agent(user_agent)
                        await page.set_viewport_size({"width": 1200, "height": 800})
                        
                        # Navigate with error handling
                        try:
                            await page.goto(url, wait_until="networkidle", timeout=self.config.page_load_timeout)
                        except PlaywrightTimeoutError:
                            await page.goto(url, wait_until="domcontentloaded", timeout=self.config.page_load_timeout)
                        
                        await page.wait_for_timeout(self.config.content_load_wait)
                        
                        # Try extraction strategies in order of preference
                        result = await self._try_extraction_strategies(page, url, content_type, start_time)
                        
                        if result:
                            return result
                        
                    finally:
                        await browser.close()
                
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
                    
            except Exception as e:
                logger.warning(f"DOM extraction attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    logger.error(f"All DOM extraction attempts failed for {url}")
        
        return None
    
    async def _try_extraction_strategies(self, page, url: str, content_type: ContentType, start_time: float) -> Optional[ExtractionResult]:
        """Try multiple extraction strategies for TTS content"""
        
        # Strategy 1: Semantic extraction (best for TTS)
        result = await self._extract_semantic_content(page, url, content_type, start_time)
        if result and result.confidence > 0.7:
            return result
        
        # Strategy 2: Heuristic-based extraction
        result = await self._extract_heuristic_content(page, url, content_type, start_time)
        if result and result.confidence > 0.6:
            return result
        
        # Strategy 3: Reader mode extraction
        result = await self._extract_reader_mode_content(page, url, content_type, start_time)
        if result and result.confidence > 0.5:
            return result
        
        # Strategy 4: Fallback extraction
        result = await self._extract_fallback_content(page, url, content_type, start_time)
        return result
    
    async def _extract_semantic_content(self, page, url: str, content_type: ContentType, start_time: float) -> Optional[ExtractionResult]:
        """Extract content using semantic HTML elements"""
        try:
            for selector, priority in sorted(self.config.content_selectors.items(), key=lambda x: x[1], reverse=True):
                try:
                    elements = await page.query_selector_all(selector)
                    
                    for element in elements:
                        if await self._is_likely_main_content(element):
                            text = await element.inner_text()
                            if text and len(text.strip()) >= self.config.min_text_length:
                                
                                processing_time = time.time() - start_time
                                confidence = min(0.9, priority / 10.0)
                                
                                metadata = {
                                    'selector': selector,
                                    'priority': priority,
                                    'url': url,
                                    'method_specific': 'semantic_html'
                                }
                                
                                return self._create_result(
                                    text, ExtractionMethod.DOM_SEMANTIC, content_type,
                                    processing_time, metadata
                                )
                except Exception:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error in semantic extraction: {str(e)}")
            return None
    
    async def _extract_heuristic_content(self, page, url: str, content_type: ContentType, start_time: float) -> Optional[ExtractionResult]:
        """Extract content using heuristic analysis for TTS optimization"""
        try:
            candidates = await page.evaluate('''
                () => {
                    const elements = document.querySelectorAll('div, section, article, main, p');
                    const candidates = [];
                    
                    elements.forEach(el => {
                        const text = el.innerText || '';
                        const textLength = text.trim().length;
                        
                        if (textLength < 100) return;
                        
                        let score = textLength;
                        
                        // Boost for semantic elements
                        if (['ARTICLE', 'MAIN', 'SECTION'].includes(el.tagName)) {
                            score *= 1.5;
                        }
                        
                        // Boost for content-related classes/ids
                        const classId = (el.className + ' ' + el.id).toLowerCase();
                        if (classId.includes('content') || classId.includes('article') || classId.includes('post')) {
                            score *= 1.3;
                        }
                        
                        // Penalize navigation-like elements
                        if (classId.includes('nav') || classId.includes('menu') || classId.includes('sidebar')) {
                            score *= 0.3;
                        }
                        
                        // Check link density (high link density = poor TTS content)
                        const links = el.querySelectorAll('a');
                        const linkText = Array.from(links).reduce((acc, link) => acc + (link.innerText || '').length, 0);
                        const linkDensity = textLength > 0 ? linkText / textLength : 1;
                        
                        if (linkDensity > 0.5) score *= 0.5;
                        
                        candidates.push({
                            score: score,
                            textLength: textLength,
                            linkDensity: linkDensity,
                            tagName: el.tagName,
                            text: text.substring(0, 5000)
                        });
                    });
                    
                    return candidates.sort((a, b) => b.score - a.score).slice(0, 5);
                }
            ''')
            
            if candidates and len(candidates) > 0:
                best_candidate = candidates[0]
                
                if best_candidate['textLength'] >= self.config.min_text_length:
                    processing_time = time.time() - start_time
                    confidence = min(0.8, best_candidate['score'] / (best_candidate['textLength'] * 2))
                    
                    metadata = {
                        'score': best_candidate['score'],
                        'link_density': best_candidate['linkDensity'],
                        'tag_name': best_candidate['tagName'],
                        'url': url,
                        'method_specific': 'heuristic_analysis'
                    }
                    
                    return self._create_result(
                        best_candidate['text'], ExtractionMethod.DOM_HEURISTIC, content_type,
                        processing_time, metadata
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error in heuristic extraction: {str(e)}")
            return None
    
    async def _extract_reader_mode_content(self, page, url: str, content_type: ContentType, start_time: float) -> Optional[ExtractionResult]:
        """Extract content using reader mode algorithm for TTS"""
        try:
            extracted_text = await page.evaluate('''
                () => {
                    // Remove unwanted elements
                    const unwantedSelectors = [
                        'script', 'style', 'nav', 'header', 'footer', 'aside',
                        '.advertisement', '.ad', '.sidebar', '.menu', '.navigation',
                        '.social', '.share', '.related', '.comments', '.skip-link'
                    ];
                    
                    unwantedSelectors.forEach(selector => {
                        document.querySelectorAll(selector).forEach(el => el.remove());
                    });
                    
                    // Find the best content container for TTS
                    const containers = document.querySelectorAll('div, article, section, main');
                    let bestContainer = null;
                    let maxScore = 0;
                    
                    containers.forEach(container => {
                        const text = container.innerText || '';
                        const paragraphs = container.querySelectorAll('p').length;
                        const textLength = text.length;
                        
                        const score = textLength + (paragraphs * 100);
                        
                        if (score > maxScore && textLength > 200) {
                            maxScore = score;
                            bestContainer = container;
                        }
                    });
                    
                    if (bestContainer) {
                        const paragraphs = Array.from(bestContainer.querySelectorAll('p, h1, h2, h3, h4, h5, h6'));
                        return paragraphs.map(p => p.innerText.trim()).filter(text => text.length > 10).join('\\n\\n');
                    }
                    
                    return '';
                }
            ''')
            
            if extracted_text and len(extracted_text) >= self.config.min_text_length:
                processing_time = time.time() - start_time
                
                metadata = {
                    'url': url,
                    'method_specific': 'reader_mode_algorithm'
                }
                
                return self._create_result(
                    extracted_text, ExtractionMethod.READER_MODE, content_type,
                    processing_time, metadata
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error in reader mode extraction: {str(e)}")
            return None
    
    async def _extract_fallback_content(self, page, url: str, content_type: ContentType, start_time: float) -> Optional[ExtractionResult]:
        """Last resort extraction from body content for TTS"""
        try:
            body_text = await page.inner_text('body')
            
            if body_text and len(body_text) >= self.config.min_text_length:
                # Apply aggressive filtering for fallback content
                filtered_text = TextCleaner.filter_navigation_content(body_text)
                
                if len(filtered_text) >= self.config.min_text_length:
                    processing_time = time.time() - start_time
                    
                    metadata = {
                        'url': url,
                        'note': 'fallback_extraction',
                        'method_specific': 'body_content_filtered'
                    }
                    
                    return self._create_result(
                        filtered_text, ExtractionMethod.DOM_FALLBACK, content_type,
                        processing_time, metadata
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error in fallback extraction: {str(e)}")
            return None
    
    async def _is_likely_main_content(self, element) -> bool:
        """Determine if element contains main content suitable for TTS"""
        try:
            class_name = await element.get_attribute('class') or ''
            element_id = await element.get_attribute('id') or ''
            tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
            
            combined_attrs = f"{class_name} {element_id}".lower()
            
            # Exclude navigation and non-content elements
            exclude_patterns = [
                'nav', 'navigation', 'menu', 'sidebar', 'aside', 'header', 'footer',
                'banner', 'advertisement', 'ad', 'social', 'share', 'related',
                'comments', 'pagination', 'breadcrumb', 'widget', 'toolbar',
                'cookie', 'gdpr', 'consent', 'popup', 'modal', 'overlay'
            ]
            
            for pattern in exclude_patterns:
                if pattern in combined_attrs:
                    return False
            
            # Exclude navigation tags
            if tag_name in ['nav', 'aside', 'header', 'footer']:
                return False
            
            # Check text content
            text = await element.inner_text()
            if not text or len(text.strip()) < self.config.min_text_length:
                return False
            
            # Check for high link density (bad for TTS)
            try:
                links = await element.query_selector_all('a')
                if len(links) > 10:
                    links = links[:10]
                
                link_text_length = 0
                for link in links:
                    link_text = await link.inner_text()
                    link_text_length += len(link_text)
                
                if len(text) > 0 and (link_text_length / len(text)) > 0.7:
                    return False
            except Exception:
                pass
            
            # Positive indicators for TTS content
            positive_patterns = [
                'content', 'article', 'post', 'story', 'main', 'body', 'text'
            ]
            
            for pattern in positive_patterns:
                if pattern in combined_attrs:
                    return True
            
            # Semantic elements are likely content
            if tag_name in ['article', 'main', 'section']:
                return True
            
            return True
            
        except Exception:
            return False


class PageAnalyzer:
    """Utility class for analyzing webpage structure before extraction"""
    
    def __init__(self, config=None):
        self.config = config or DEFAULT_CONFIG
    
    async def analyze_page(self, url: str) -> Optional[PageAnalysis]:
        """Analyze webpage structure and content for optimization"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=self.config.page_load_timeout)
                    
                    # Get basic page info
                    title = await page.title()
                    
                    # Check for semantic markup
                    has_semantic = await page.evaluate('''
                        () => {
                            const semanticTags = ['article', 'main', 'section'];
                            return semanticTags.some(tag => document.querySelector(tag) !== null);
                        }
                    ''')
                    
                    # Calculate link density
                    link_density = await page.evaluate('''
                        () => {
                            const allText = document.body.innerText || '';
                            const allLinks = document.querySelectorAll('a');
                            const linkText = Array.from(allLinks).reduce((acc, link) => acc + (link.innerText || '').length, 0);
                            return allText.length > 0 ? linkText / allText.length : 1;
                        }
                    ''')
                    
                    # Detect content type
                    content_type = ContentTypeDetector.detect_from_url(url)
                    if content_type == ContentType.UNKNOWN:
                        meta_description = await page.get_attribute('meta[name="description"]', 'content') or ""
                        schema_types = await page.evaluate('''
                            () => {
                                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                                const types = [];
                                scripts.forEach(script => {
                                    try {
                                        const data = JSON.parse(script.textContent);
                                        if (data['@type']) types.push(data['@type']);
                                    } catch (e) {}
                                });
                                return types;
                            }
                        ''')
                        content_type = ContentTypeDetector.detect_from_metadata(title, meta_description, schema_types)
                    
                    # Estimate text to markup ratio
                    text_markup_ratio = await page.evaluate('''
                        () => {
                            const textLength = document.body.innerText.length;
                            const htmlLength = document.body.innerHTML.length;
                            return htmlLength > 0 ? textLength / htmlLength : 0;
                        }
                    ''')
                    
                    # Estimate reading time
                    estimated_reading_time = ContentAnalyzer.estimate_reading_time(await page.inner_text('body'))
                    
                    return PageAnalysis(
                        url=url,
                        title=title,
                        content_type=content_type,
                        has_semantic_markup=has_semantic,
                        link_density=link_density,
                        text_to_markup_ratio=text_markup_ratio,
                        estimated_reading_time=estimated_reading_time
                    )
                    
                finally:
                    await browser.close()
                    
        except Exception as e:
            logger.error(f"Failed to analyze page {url}: {str(e)}")
            return None
            
        except Exception as e:
            logger.error(f"Error processing Textract response: {str(e)}")
            return ""


class DOMExtractor(BaseExtractor):
    """DOM-based content extractor with multiple strategies for TTS optimization"""
    
    async def extract(self, url: str, page_analysis: PageAnalysis = None) -> Optional[ExtractionResult]:
        """Extract content using DOM traversal with multiple strategies"""
        start_time = time.time()
        content_type = page_analysis.content_type if page_analysis else ContentType.UNKNOWN
        
        for attempt in range(self.config.max_retries):
            try:
                logger.info(f"Starting DOM extraction for TTS: {url} (attempt {attempt + 1})")
                
                async with async_playwright() as p:
                    browser = await p.chromium.launch(
                        headless=True,
                        args=[
                            '--no-sandbox',
                            '--disable-setuid-sandbox',
                            '--disable-dev-shm-usage',
                            '--disable-gpu',
                            '--disable-images',  # Faster loading
                            '--disable-javascript' if attempt > 0 else '',  # Try without JS on retry
                        ]
                    )
                    
                    try:
                        page = await browser.new_page()
                        
                        # Rotate user agents on retries
                        user_agent = self.config.user_agents[attempt % len(self.config.user_agents)]
                        await page.set_user_agent(user_agent)
                        await page.set_viewport_size({"width": 1200, "height": 800})
                        
                        # Navigate with error handling
                        try:
                            await page.goto(url, wait_until="networkidle", timeout=self.config.page_load_timeout)
                        except PlaywrightTimeoutError:
                            await page.goto(url, wait_until="domcontentloaded", timeout=self.config.page_load_timeout)
                        
                        await page.wait_for_timeout(self.config.content_load_wait)
                        
                        # Try extraction strategies in order of preference
                        result = await self._try_extraction_strategies(page, url, content_type, start_time)
                        
                        if result:
                            return result
                        
                    finally:
                        await browser.close()
                
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
                    
            except Exception as e:
                logger.warning(f"DOM extraction attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    logger.error(f"All DOM extraction attempts failed for {url}")
        
        return None
    
    async def _try_extraction_strategies(self, page, url: str, content_type: ContentType, start_time: float) -> Optional[ExtractionResult]:
        """Try multiple extraction strategies for TTS content"""
        
        # Strategy 1: Semantic extraction (best for TTS)
        result = await self._extract_semantic_content(page, url, content_type, start_time)
        if result and result.confidence > 0.7:
            return result
        
        # Strategy 2: Heuristic-based extraction
        result = await self._extract_heuristic_content(page, url, content_type, start_time)
        if result and result.confidence > 0.6:
            return result
        
        # Strategy 3: Reader mode extraction
        result = await self._extract_reader_mode_content(page, url, content_type, start_time)
        if result and result.confidence > 0.5:
            return result
        
        # Strategy 4: Fallback extraction
        result = await self._extract_fallback_content(page, url, content_type, start_time)
        return result
    
    async def _extract_semantic_content(self, page, url: str, content_type: ContentType, start_time: float) -> Optional[ExtractionResult]:
        """Extract content using semantic HTML elements"""
        try:
            for selector, priority in sorted(self.config.content_selectors.items(), key=lambda x: x[1], reverse=True):
                try:
                    elements = await page.query_selector_all(selector)
                    
                    for element in elements:
                        if await self._is_likely_main_content(element):
                            text = await element.inner_text()
                            if text and len(text.strip()) >= self.config.min_text_length:
                                
                                processing_time = time.time() - start_time
                                confidence = min(0.9, priority / 10.0)
                                
                                metadata = {
                                    'selector': selector,
                                    'priority': priority,
                                    'url': url,
                                    'method_specific': 'semantic_html'
                                }
                                
                                return self._create_result(
                                    text, ExtractionMethod.DOM_SEMANTIC, content_type,
                                    processing_time, metadata
                                )
                except Exception:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error in semantic extraction: {str(e)}")
            return None
    
    async def _extract_heuristic_content(self, page, url: str, content_type: ContentType, start_time: float) -> Optional[ExtractionResult]:
        """Extract content using heuristic analysis for TTS optimization"""
        try:
            candidates = await page.evaluate('''
                () => {
                    const elements = document.querySelectorAll('div, section, article, main, p');
                    const candidates = [];
                    
                    elements.forEach(el => {
                        const text = el.innerText || '';
                        const textLength = text.trim().length;
                        
                        if (textLength < 100) return;
                        
                        let score = textLength;
                        
                        // Boost for semantic elements
                        if (['ARTICLE', 'MAIN', 'SECTION'].includes(el.tagName)) {
                            score *= 1.5;
                        }
                        
                        // Boost for content-related classes/ids
                        const classId = (el.className + ' ' + el.id).toLowerCase();
                        if (classId.includes('content') || classId.includes('article') || classId.includes('post')) {
                            score *= 1.3;
                        }
                        
                        // Penalize navigation-like elements
                        if (classId.includes('nav') || classId.includes('menu') || classId.includes('sidebar')) {
                            score *= 0.3;
                        }
                        
                        // Check link density (high link density = poor TTS content)
                        const links = el.querySelectorAll('a');
                        const linkText = Array.from(links).reduce((acc, link) => acc + (link.innerText || '').length, 0);
                        const linkDensity = textLength > 0 ? linkText / textLength : 1;
                        
                        if (linkDensity > 0.5) score *= 0.5;
                        
                        candidates.push({
                            score: score,
                            textLength: textLength,
                            linkDensity: linkDensity,
                            tagName: el.tagName,
                            text: text.substring(0, 5000)
                        });
                    });
                    
                    return candidates.sort((a, b) => b.score - a.score).slice(0, 5);
                }
            ''')
            
            if candidates and len(candidates) > 0:
                best_candidate = candidates[0]
                
                if best_candidate['textLength'] >= self.config.min_text_length:
                    processing_time = time.time() - start_time
                    confidence = min(0.8, best_candidate['score'] / (best_candidate['textLength'] * 2))
                    
                    metadata = {
                        'score': best_candidate['score'],
                        'link_density': best_candidate['linkDensity'],
                        'tag_name': best_candidate['tagName'],
                        'url': url,
                        'method_specific': 'heuristic_analysis'
                    }
                    
                    return self._create_result(
                        best_candidate['text'], ExtractionMethod.DOM_HEURISTIC, content_type,
                        processing_time, metadata
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error in heuristic extraction: {str(e)}")
            return None
    
    async def _extract_reader_mode_content(self, page, url: str, content_type: ContentType, start_time: float) -> Optional[ExtractionResult]:
        """Extract content using reader mode algorithm for TTS"""
        try:
            extracted_text = await page.evaluate('''
                () => {
                    // Remove unwanted elements
                    const unwantedSelectors = [
                        'script', 'style', 'nav', 'header', 'footer', 'aside',
                        '.advertisement', '.ad', '.sidebar', '.menu', '.navigation',
                        '.social', '.share', '.related', '.comments', '.skip-link'
                    ];
                    
                    unwantedSelectors.forEach(selector => {
                        document.querySelectorAll(selector).forEach(el => el.remove());
                    });
                    
                    // Find the best content container for TTS
                    const containers = document.querySelectorAll('div, article, section, main');
                    let bestContainer = null;
                    let maxScore = 0;
                    
                    containers.forEach(container => {
                        const text = container.innerText || '';
                        const paragraphs = container.querySelectorAll('p').length;
                        const textLength = text.length;
                        
                        const score = textLength + (paragraphs * 100);
                        
                        if (score > maxScore && textLength > 200) {
                            maxScore = score;
                            bestContainer = container;
                        }
                    });
                    
                    if (bestContainer) {
                        const paragraphs = Array.from(bestContainer.querySelectorAll('p, h1, h2, h3, h4, h5, h6'));
                        return paragraphs.map(p => p.innerText.trim()).filter(text => text.length > 10).join('\\n\\n');
                    }
                    
                    return '';
                }
            ''')
            
            if extracted_text and len(extracted_text) >= self.config.min_text_length:
                processing_time = time.time() - start_time
                
                metadata = {
                    'url': url,
                    'method_specific': 'reader_mode_algorithm'
                }
                
                return self._create_result(
                    extracted_text, ExtractionMethod.READER_MODE, content_type,
                    processing_time, metadata
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error in reader mode extraction: {str(e)}")
            return None
    
    async def _extract_fallback_content(self, page, url: str, content_type: ContentType, start_time: float) -> Optional[ExtractionResult]:
        """Last resort extraction from body content for TTS"""
        try:
            body_text = await page.inner_text('body')
            
            if body_text and len(body_text) >= self.config.min_text_length:
                # Apply aggressive filtering for fallback content
                filtered_text = TextCleaner.filter_navigation_content(body_text)
                
                if len(filtered_text) >= self.config.min_text_length:
                    processing_time = time.time() - start_time
                    
                    metadata = {
                        'url': url,
                        'note': 'fallback_extraction',
                        'method_specific': 'body_content_filtered'
                    }
                    
                    return self._create_result(
                        filtered_text, ExtractionMethod.DOM_FALLBACK, content_type,
                        processing_time, metadata
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error in fallback extraction: {str(e)}")
            return None
    
    async def _is_likely_main_content(self, element) -> bool:
        """Determine if element contains main content suitable for TTS"""
        try:
            class_name = await element.get_attribute('class') or ''
            element_id = await element.get_attribute('id') or ''
            tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
            
            combined_attrs = f"{class_name} {element_id}".lower()
            
            # Exclude navigation and non-content elements
            exclude_patterns = [
                'nav', 'navigation', 'menu', 'sidebar', 'aside', 'header', 'footer',
                'banner', 'advertisement', 'ad', 'social', 'share', 'related',
                'comments', 'pagination', 'breadcrumb', 'widget', 'toolbar',
                'cookie', 'gdpr', 'consent', 'popup', 'modal', 'overlay'
            ]
            
            for pattern in exclude_patterns:
                if pattern in combined_attrs:
                    return False
            
            # Exclude navigation tags
            if tag_name in ['nav', 'aside', 'header', 'footer']:
                return False
            
            # Check text content
            text = await element.inner_text()
            if not text or len(text.strip()) < self.config.min_text_length:
                return False
            
            # Check for high link density (bad for TTS)
            try:
                links = await element.query_selector_all('a')
                if len(links) > 10:
                    links = links[:10]
                
                link_text_length = 0
                for link in links:
                    link_text = await link.inner_text()
                    link_text_length += len(link_text)
                
                if len(text) > 0 and (link_text_length / len(text)) > 0.7:
                    return False
            except Exception:
                pass
            
            # Positive indicators for TTS content
            positive_patterns = [
                'content', 'article', 'post', 'story', 'main', 'body', 'text'
            ]
            
            for pattern in positive_patterns:
                if pattern in combined_attrs:
                    return True
            
            # Semantic elements are likely content
            if tag_name in ['article', 'main', 'section']:
                return True
            
            return True
            
        except Exception:
            return False