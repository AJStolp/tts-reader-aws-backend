import boto3
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from typing import Optional, Tuple, Dict, List, Any
import logging
import os
import asyncio
import time
from urllib.parse import urlparse, urljoin
import re
from botocore.exceptions import ClientError
from dataclasses import dataclass
from enum import Enum
import json
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AWS clients with enhanced error handling
try:
    session = boto3.Session(
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("AWS_REGION", "us-east-1")
    )
    textract = session.client("textract")
    
    # Test Textract connectivity
    textract.describe_document_analysis(JobId="test-connectivity")
except ClientError as e:
    if "InvalidJobIdException" not in str(e):
        logger.warning(f"Textract client issue: {str(e)}")
        textract = None
    else:
        logger.info("Textract client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize AWS Textract client: {str(e)}")
    textract = None

class ExtractionMethod(Enum):
    """Enumeration of available extraction methods"""
    TEXTRACT = "textract"
    DOM_SEMANTIC = "dom_semantic"
    DOM_HEURISTIC = "dom_heuristic"
    DOM_FALLBACK = "dom_fallback"
    READER_MODE = "reader_mode"

class ContentType(Enum):
    """Enumeration of detected content types"""
    ARTICLE = "article"
    BLOG_POST = "blog_post"
    NEWS = "news"
    DOCUMENTATION = "documentation"
    E_COMMERCE = "e_commerce"
    SOCIAL_MEDIA = "social_media"
    FORUM = "forum"
    UNKNOWN = "unknown"

@dataclass
class ExtractionResult:
    """Result of content extraction with metadata"""
    text: str
    method: ExtractionMethod
    content_type: ContentType
    confidence: float
    word_count: int
    char_count: int
    processing_time: float
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            "text": self.text,
            "method": self.method.value,
            "content_type": self.content_type.value,
            "confidence": self.confidence,
            "word_count": self.word_count,
            "char_count": self.char_count,
            "processing_time": self.processing_time,
            "metadata": self.metadata
        }

# Enhanced constants
MAX_PDF_SIZE = 10 * 1024 * 1024  # 10MB limit for Textract
MIN_TEXT_LENGTH = 100  # Increased minimum for better quality
TEXTRACT_TIMEOUT = 45  # Increased timeout
PAGE_LOAD_TIMEOUT = 30000  # 30 seconds
CONTENT_LOAD_WAIT = 3000  # 3 seconds for dynamic content
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

class WebpageExtractor:
    """Advanced webpage content extractor with multiple strategies for TTS reading"""
    
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
        # Enhanced content selectors with priority scoring for TTS-optimized extraction
        self.content_selectors = {
            # Semantic selectors (highest priority)
            'main': 10,
            'article': 10,
            '[role="main"]': 10,
            '[role="article"]': 10,
            
            # Content-specific selectors
            '.article-content': 9,
            '.post-content': 9,
            '.entry-content': 9,
            '.content-body': 9,
            '.article-body': 9,
            '.main-content': 8,
            '.page-content': 8,
            '.content': 7,
            
            # ID-based selectors
            '#main-content': 8,
            '#article-content': 8,
            '#content': 7,
            '#main': 8,
            
            # News/blog specific
            '.story-body': 9,
            '.article-text': 9,
            '.post-body': 8,
            '.entry-text': 8,
            
            # Documentation specific
            '.documentation': 8,
            '.docs-content': 8,
            '.wiki-content': 8,
        }
        
        # Elements to exclude for better TTS reading experience
        self.exclude_selectors = [
            'nav', 'header', 'footer', 'aside', '.sidebar', '.navigation',
            '.menu', '.nav', '.header', '.footer', '.advertisement', '.ad',
            '.social', '.share', '.related', '.comments', '.pagination',
            '.breadcrumb', '.widget', '.toolbar', '.banner', '.popup',
            '.modal', '.overlay', '[class*="cookie"]', '[class*="gdpr"]',
            '.skip-link', '.screen-reader-text', '.visually-hidden'
        ]

    async def is_valid_url(self, url: str) -> bool:
        """Enhanced URL validation"""
        try:
            parsed = urlparse(url)
            return all([
                parsed.scheme in ('http', 'https'),
                parsed.netloc,
                len(parsed.netloc) > 3,
                '.' in parsed.netloc
            ])
        except Exception:
            return False

    async def detect_content_type(self, page) -> ContentType:
        """Detect the type of content on the page for optimized TTS extraction"""
        try:
            # Check meta tags and structured data
            title = await page.title()
            meta_description = await page.get_attribute('meta[name="description"]', 'content') or ""
            
            # Check for schema.org structured data
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
            
            # Check URL patterns
            url = page.url
            
            # Article indicators
            if (any(word in title.lower() for word in ['article', 'story', 'news']) or
                any(word in url.lower() for word in ['/article/', '/story/', '/news/']) or
                'Article' in schema_types):
                return ContentType.ARTICLE
            
            # Blog indicators
            if (any(word in url.lower() for word in ['/blog/', '/post/', '/posts/']) or
                'BlogPosting' in schema_types):
                return ContentType.BLOG_POST
            
            # Documentation indicators
            if any(word in url.lower() for word in ['/docs/', '/documentation/', '/wiki/', '/help/']):
                return ContentType.DOCUMENTATION
            
            # E-commerce indicators
            if ('Product' in schema_types or
                any(word in url.lower() for word in ['/product/', '/shop/', '/store/'])):
                return ContentType.E_COMMERCE
            
            # Social media indicators
            if any(domain in url.lower() for domain in ['twitter.com', 'facebook.com', 'linkedin.com', 'instagram.com']):
                return ContentType.SOCIAL_MEDIA
            
            # Forum indicators
            if any(word in url.lower() for word in ['/forum/', '/thread/', '/topic/']):
                return ContentType.FORUM
            
            return ContentType.UNKNOWN
            
        except Exception as e:
            logger.warning(f"Error detecting content type: {str(e)}")
            return ContentType.UNKNOWN

    async def extract_with_textract(self, url: str) -> Optional[ExtractionResult]:
        """Enhanced Textract extraction with better error handling for TTS content"""
        if not textract:
            logger.info("Textract client not available")
            return None
            
        start_time = time.time()
        
        try:
            logger.info(f"Starting Textract extraction for TTS: {url}")
            
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
                    await page.set_user_agent(self.user_agents[0])
                    
                    # Enhanced page setup for better content rendering
                    await page.set_viewport_size({"width": 1200, "height": 800})
                    await page.set_extra_http_headers({
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'DNT': '1'
                    })
                    
                    # Navigate with enhanced error handling
                    try:
                        await page.goto(url, wait_until="networkidle", timeout=PAGE_LOAD_TIMEOUT)
                    except PlaywrightTimeoutError:
                        logger.warning(f"Page load timeout for {url}, trying with domcontentloaded")
                        await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
                    
                    # Wait for dynamic content to load
                    await page.wait_for_timeout(CONTENT_LOAD_WAIT)
                    
                    # Detect content type for better processing
                    content_type = await self.detect_content_type(page)
                    
                    # Remove overlays and popups that interfere with TTS content
                    await self._remove_overlays(page)
                    
                    # Generate PDF with optimized settings for text extraction
                    pdf_bytes = await page.pdf(
                        format='A4',
                        print_background=False,
                        margin={'top': '1cm', 'right': '1cm', 'bottom': '1cm', 'left': '1cm'},
                        prefer_css_page_size=True
                    )
                    
                    if len(pdf_bytes) > MAX_PDF_SIZE:
                        logger.warning(f"PDF too large ({len(pdf_bytes)} bytes) for Textract")
                        return None
                    
                finally:
                    await browser.close()
            
            # Process with Textract
            logger.info(f"Processing PDF with Textract ({len(pdf_bytes)} bytes)")
            
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    textract.analyze_document,
                    Document={'Bytes': pdf_bytes},
                    FeatureTypes=['LAYOUT', 'TABLES']
                ),
                timeout=TEXTRACT_TIMEOUT
            )
            
            # Enhanced text extraction with layout awareness for TTS
            extracted_text = await self._process_textract_response(response)
            
            if len(extracted_text) >= MIN_TEXT_LENGTH:
                processing_time = time.time() - start_time
                
                result = ExtractionResult(
                    text=extracted_text,
                    method=ExtractionMethod.TEXTRACT,
                    content_type=content_type,
                    confidence=0.9,  # High confidence for Textract
                    word_count=len(extracted_text.split()),
                    char_count=len(extracted_text),
                    processing_time=processing_time,
                    metadata={
                        'pdf_size': len(pdf_bytes),
                        'textract_blocks': len(response.get('Blocks', [])),
                        'url': url
                    }
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

    async def _remove_overlays(self, page):
        """Remove common overlays and popups that interfere with TTS content"""
        try:
            await page.evaluate('''
                () => {
                    // Remove common overlay selectors
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

    async def _process_textract_response(self, response: Dict) -> str:
        """Process Textract response with enhanced layout awareness for TTS"""
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
            
            extracted_text = ''.join(main_text_blocks)
            return self._clean_extracted_text(extracted_text)
            
        except Exception as e:
            logger.error(f"Error processing Textract response: {str(e)}")
            return ""

    async def extract_with_dom(self, url: str) -> Optional[ExtractionResult]:
        """Enhanced DOM extraction with multiple strategies optimized for TTS"""
        start_time = time.time()
        
        for attempt in range(MAX_RETRIES):
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
                        user_agent = self.user_agents[attempt % len(self.user_agents)]
                        await page.set_user_agent(user_agent)
                        
                        await page.set_viewport_size({"width": 1200, "height": 800})
                        
                        # Navigate with error handling
                        try:
                            await page.goto(url, wait_until="networkidle", timeout=PAGE_LOAD_TIMEOUT)
                        except PlaywrightTimeoutError:
                            await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
                        
                        await page.wait_for_timeout(CONTENT_LOAD_WAIT)
                        
                        # Detect content type
                        content_type = await self.detect_content_type(page)
                        
                        # Remove overlays
                        await self._remove_overlays(page)
                        
                        # Try multiple extraction strategies
                        result = await self._try_extraction_strategies(page, url, content_type, start_time)
                        
                        if result:
                            return result
                        
                    finally:
                        await browser.close()
                
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                    
            except Exception as e:
                logger.warning(f"DOM extraction attempt {attempt + 1} failed: {str(e)}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    logger.error(f"All DOM extraction attempts failed for {url}")
        
        return None

    async def _try_extraction_strategies(self, page, url: str, content_type: ContentType, start_time: float) -> Optional[ExtractionResult]:
        """Try multiple extraction strategies in order of preference for TTS content"""
        
        # Strategy 1: Semantic extraction (best for TTS)
        result = await self._extract_semantic_content(page, url, content_type, start_time)
        if result and result.confidence > 0.7:
            return result
        
        # Strategy 2: Heuristic-based extraction
        result = await self._extract_heuristic_content(page, url, content_type, start_time)
        if result and result.confidence > 0.6:
            return result
        
        # Strategy 3: Reader mode extraction (optimized for TTS)
        result = await self._extract_reader_mode_content(page, url, content_type, start_time)
        if result and result.confidence > 0.5:
            return result
        
        # Strategy 4: Fallback extraction
        result = await self._extract_fallback_content(page, url, content_type, start_time)
        return result

    async def _extract_semantic_content(self, page, url: str, content_type: ContentType, start_time: float) -> Optional[ExtractionResult]:
        """Extract content using semantic HTML elements optimized for TTS reading"""
        try:
            for selector, priority in sorted(self.content_selectors.items(), key=lambda x: x[1], reverse=True):
                try:
                    elements = await page.query_selector_all(selector)
                    
                    for element in elements:
                        if await self._is_likely_main_content(element):
                            text = await element.inner_text()
                            if text and len(text.strip()) >= MIN_TEXT_LENGTH:
                                
                                cleaned_text = self._clean_extracted_text(text)
                                if len(cleaned_text) >= MIN_TEXT_LENGTH:
                                    
                                    confidence = min(0.9, priority / 10.0)
                                    processing_time = time.time() - start_time
                                    
                                    return ExtractionResult(
                                        text=cleaned_text,
                                        method=ExtractionMethod.DOM_SEMANTIC,
                                        content_type=content_type,
                                        confidence=confidence,
                                        word_count=len(cleaned_text.split()),
                                        char_count=len(cleaned_text),
                                        processing_time=processing_time,
                                        metadata={
                                            'selector': selector,
                                            'priority': priority,
                                            'url': url
                                        }
                                    )
                except Exception:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error in semantic extraction: {str(e)}")
            return None

    async def _extract_heuristic_content(self, page, url: str, content_type: ContentType, start_time: float) -> Optional[ExtractionResult]:
        """Extract content using heuristic analysis optimized for TTS"""
        try:
            # Get all potential content elements
            candidates = await page.evaluate('''
                () => {
                    const elements = document.querySelectorAll('div, section, article, main, p');
                    const candidates = [];
                    
                    elements.forEach(el => {
                        const text = el.innerText || '';
                        const textLength = text.trim().length;
                        
                        if (textLength < 100) return;
                        
                        // Calculate content score for TTS suitability
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
                            className: el.className,
                            text: text.substring(0, 5000)  // Limit text for performance
                        });
                    });
                    
                    return candidates.sort((a, b) => b.score - a.score).slice(0, 5);
                }
            ''')
            
            if candidates and len(candidates) > 0:
                best_candidate = candidates[0]
                
                if best_candidate['textLength'] >= MIN_TEXT_LENGTH:
                    cleaned_text = self._clean_extracted_text(best_candidate['text'])
                    
                    if len(cleaned_text) >= MIN_TEXT_LENGTH:
                        confidence = min(0.8, best_candidate['score'] / (best_candidate['textLength'] * 2))
                        processing_time = time.time() - start_time
                        
                        return ExtractionResult(
                            text=cleaned_text,
                            method=ExtractionMethod.DOM_HEURISTIC,
                            content_type=content_type,
                            confidence=confidence,
                            word_count=len(cleaned_text.split()),
                            char_count=len(cleaned_text),
                            processing_time=processing_time,
                            metadata={
                                'score': best_candidate['score'],
                                'link_density': best_candidate['linkDensity'],
                                'tag_name': best_candidate['tagName'],
                                'url': url
                            }
                        )
            
            return None
            
        except Exception as e:
            logger.error(f"Error in heuristic extraction: {str(e)}")
            return None

    async def _extract_reader_mode_content(self, page, url: str, content_type: ContentType, start_time: float) -> Optional[ExtractionResult]:
        """Extract content using reader mode algorithm optimized for TTS"""
        try:
            # Implement a simplified reader mode algorithm for TTS
            extracted_text = await page.evaluate('''
                () => {
                    // Remove unwanted elements that interfere with TTS
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
                        
                        // Score based on text length and paragraph count (better for TTS)
                        const score = textLength + (paragraphs * 100);
                        
                        if (score > maxScore && textLength > 200) {
                            maxScore = score;
                            bestContainer = container;
                        }
                    });
                    
                    if (bestContainer) {
                        // Extract and clean text for TTS
                        const paragraphs = Array.from(bestContainer.querySelectorAll('p, h1, h2, h3, h4, h5, h6'));
                        return paragraphs.map(p => p.innerText.trim()).filter(text => text.length > 10).join('\\n\\n');
                    }
                    
                    return '';
                }
            ''')
            
            if extracted_text and len(extracted_text) >= MIN_TEXT_LENGTH:
                cleaned_text = self._clean_extracted_text(extracted_text)
                
                if len(cleaned_text) >= MIN_TEXT_LENGTH:
                    processing_time = time.time() - start_time
                    
                    return ExtractionResult(
                        text=cleaned_text,
                        method=ExtractionMethod.READER_MODE,
                        content_type=content_type,
                        confidence=0.7,
                        word_count=len(cleaned_text.split()),
                        char_count=len(cleaned_text),
                        processing_time=processing_time,
                        metadata={'url': url}
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error in reader mode extraction: {str(e)}")
            return None

    async def _extract_fallback_content(self, page, url: str, content_type: ContentType, start_time: float) -> Optional[ExtractionResult]:
        """Last resort extraction from body content for TTS"""
        try:
            body_text = await page.inner_text('body')
            
            if body_text and len(body_text) >= MIN_TEXT_LENGTH:
                # Apply aggressive filtering for fallback content
                filtered_text = self._filter_body_content(body_text)
                cleaned_text = self._clean_extracted_text(filtered_text)
                
                if len(cleaned_text) >= MIN_TEXT_LENGTH:
                    processing_time = time.time() - start_time
                    
                    return ExtractionResult(
                        text=cleaned_text,
                        method=ExtractionMethod.DOM_FALLBACK,
                        content_type=content_type,
                        confidence=0.4,  # Low confidence for fallback
                        word_count=len(cleaned_text.split()),
                        char_count=len(cleaned_text),
                        processing_time=processing_time,
                        metadata={'url': url, 'note': 'fallback_extraction'}
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Error in fallback extraction: {str(e)}")
            return None

    async def _is_likely_main_content(self, element) -> bool:
        """Enhanced content detection with better heuristics for TTS content"""
        try:
            # Get element attributes
            class_name = await element.get_attribute('class') or ''
            element_id = await element.get_attribute('id') or ''
            tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
            
            # Check exclusion patterns
            combined_attrs = f"{class_name} {element_id}".lower()
            
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
            if not text or len(text.strip()) < MIN_TEXT_LENGTH:
                return False
            
            # Check for high link density (likely navigation, bad for TTS)
            try:
                links = await element.query_selector_all('a')
                if len(links) > 10:  # Limit to avoid performance issues
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

    def _filter_body_content(self, body_text: str) -> str:
        """Enhanced body content filtering for TTS optimization"""
        if not body_text:
            return ""
        
        lines = body_text.split('\n')
        filtered_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip very short lines (likely navigation)
            if len(line) < 20:
                continue
            
            # Skip lines that look like navigation or metadata (bad for TTS)
            if (any(keyword in line.lower() for keyword in [
                'home', 'about', 'contact', 'menu', 'login', 'register',
                'privacy', 'terms', 'copyright', '©', 'all rights reserved',
                'follow us', 'subscribe', 'newsletter', 'cookies', 'gdpr',
                'skip to', 'jump to', 'accessibility'
            ])):
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

    def _clean_extracted_text(self, text: str) -> str:
        """Enhanced text cleaning and normalization for TTS reading"""
        if not text:
            return ""
        
        # Normalize whitespace for better TTS flow
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)  # Clean up multiple newlines
        
        # Remove excessive punctuation that disrupts TTS
        text = re.sub(r'[.]{3,}', '...', text)
        text = re.sub(r'[-]{3,}', '---', text)
        text = re.sub(r'[_]{3,}', '___', text)
        
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
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text


class ContentExtractorManager:
    """Manager class for orchestrating content extraction for TTS reading"""
    
    def __init__(self):
        self.extractor = WebpageExtractor()
    
    async def extract_content(self, url: str, prefer_textract: bool = True) -> Tuple[str, str]:
        """
        Main extraction method with intelligent fallback strategy optimized for TTS
        
        Args:
            url (str): The webpage URL to process
            prefer_textract (bool): Whether to try Textract first
            
        Returns:
            Tuple[str, str]: (extracted_text, extraction_method)
        """
        if not url or not isinstance(url, str):
            raise ValueError("A valid URL string is required")
        
        if not await self.extractor.is_valid_url(url):
            raise ValueError("Invalid URL format")
        
        logger.info(f"Starting intelligent content extraction for TTS: {url}")
        start_time = time.time()
        
        extraction_results = []
        
        # Try Textract first if available and preferred
        if prefer_textract and textract:
            logger.info("Attempting Textract extraction for TTS...")
            textract_result = await self.extractor.extract_with_textract(url)
            if textract_result:
                extraction_results.append(textract_result)
        
        # Try DOM extraction
        logger.info("Attempting DOM extraction for TTS...")
        dom_result = await self.extractor.extract_with_dom(url)
        if dom_result:
            extraction_results.append(dom_result)
        
        # Select the best result for TTS
        if extraction_results:
            best_result = self._select_best_result(extraction_results)
            
            total_time = time.time() - start_time
            logger.info(
                f"TTS content extraction completed in {total_time:.2f}s. "
                f"Method: {best_result.method.value}, "
                f"Confidence: {best_result.confidence:.2f}, "
                f"Length: {best_result.char_count} chars"
            )
            
            return best_result.text, best_result.method.value
        
        # If all methods fail
        logger.error(f"All extraction methods failed for URL: {url}")
        raise Exception("Unable to extract content using any available method")
    
    def _select_best_result(self, results: List[ExtractionResult]) -> ExtractionResult:
        """Select the best extraction result based on TTS suitability"""
        if len(results) == 1:
            return results[0]
        
        # Score each result for TTS suitability
        scored_results = []
        
        for result in results:
            score = 0
            
            # Base confidence score
            score += result.confidence * 100
            
            # Bonus for better extraction methods for TTS
            method_bonuses = {
                ExtractionMethod.TEXTRACT: 30,
                ExtractionMethod.DOM_SEMANTIC: 25,
                ExtractionMethod.DOM_HEURISTIC: 20,
                ExtractionMethod.READER_MODE: 15,
                ExtractionMethod.DOM_FALLBACK: 5
            }
            score += method_bonuses.get(result.method, 0)
            
            # Bonus for reasonable text length for TTS (not too short, not too long)
            if 500 <= result.char_count <= 50000:
                score += 20
            elif 200 <= result.char_count <= 100000:
                score += 10
            
            # Bonus for better word-to-character ratio (indicates proper formatting for TTS)
            if result.word_count > 0:
                word_char_ratio = result.char_count / result.word_count
                if 4 <= word_char_ratio <= 8:  # Good ratio for TTS
                    score += 15
            
            # Penalty for very fast processing (might indicate shallow extraction)
            if result.processing_time < 1.0:
                score -= 10
            
            scored_results.append((result, score))
        
        # Sort by score and return the best for TTS
        scored_results.sort(key=lambda x: x[1], reverse=True)
        best_result = scored_results[0][0]
        
        logger.info(f"Selected extraction method for TTS: {best_result.method.value} "
                   f"(confidence: {best_result.confidence:.2f})")
        
        return best_result


# Health check function
async def health_check() -> Dict[str, Any]:
    """Enhanced health check for the TTS extraction service"""
    status = {
        "textract_available": textract is not None,
        "playwright_available": False,
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "capabilities": [],
        "service": "TTS Content Extractor"
    }
    
    # Test Playwright
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            await browser.close()
        status["playwright_available"] = True
        status["capabilities"].append("dom_extraction")
        logger.info("✓ Playwright health check passed")
    except Exception as e:
        status["playwright_available"] = False
        status["playwright_error"] = str(e)
        status["status"] = "degraded"
        logger.error(f"✗ Playwright health check failed: {e}")
    
    # Test Textract (if available)
    if textract:
        try:
            await asyncio.to_thread(textract.describe_document_analysis, JobId="health-check")
        except ClientError as e:
            if "InvalidJobIdException" in str(e):
                status["capabilities"].append("textract_extraction")
                logger.info("✓ Textract health check passed")
            else:
                status["textract_available"] = False
                status["textract_error"] = str(e)
                status["status"] = "degraded"
                logger.error(f"✗ Textract health check failed: {e}")
        except Exception as e:
            status["textract_available"] = False
            status["textract_error"] = str(e)
            status["status"] = "degraded"
            logger.error(f"✗ Textract health check failed: {e}")
    else:
        logger.info("Textract not available")
    
    return status


# Backwards compatibility functions
async def is_valid_url(url: str) -> bool:
    """Backwards compatibility wrapper"""
    extractor = WebpageExtractor()
    return await extractor.is_valid_url(url)

async def extract_content(url: str) -> Tuple[str, str]:
    """
    Backwards compatibility wrapper for the main extraction function
    
    Args:
        url (str): The webpage URL to process
        
    Returns:
        Tuple[str, str]: (extracted_text, extraction_method)
    """
    manager = ContentExtractorManager()
    return await manager.extract_content(url)