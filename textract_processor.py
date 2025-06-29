import boto3
from playwright.async_api import async_playwright
from typing import Optional, Tuple
import logging
import os
import asyncio
from urllib.parse import urlparse
import re
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AWS clients
try:
    session = boto3.Session(
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("AWS_REGION", "us-east-1")
    )
    textract = session.client("textract")
except Exception as e:
    logger.error(f"Failed to initialize AWS Textract client: {str(e)}")
    textract = None

# Constants
MAX_PDF_SIZE = 10 * 1024 * 1024  # 10MB limit for Textract
MIN_TEXT_LENGTH = 50  # Minimum text length to consider extraction successful
TEXTRACT_TIMEOUT = 30  # Timeout for Textract processing in seconds

async def is_valid_url(url: str) -> bool:
    """Validate URL format and accessibility"""
    try:
        parsed = urlparse(url)
        return all([parsed.scheme in ('http', 'https'), parsed.netloc])
    except Exception:
        return False

async def extract_with_textract(url: str) -> Tuple[str, bool]:
    """
    Extract main content using Amazon Textract from a rendered webpage PDF.
    
    Args:
        url (str): The webpage URL to process.
        
    Returns:
        Tuple[str, bool]: (extracted_text, success_flag)
    """
    if not textract:
        logger.warning("Textract client not available, skipping Textract extraction")
        return "", False
    
    if not await is_valid_url(url):
        logger.error(f"Invalid URL provided: {url}")
        return "", False
    
    try:
        logger.info(f"Starting Textract extraction for: {url}")
        
        # Render webpage to PDF using Playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu'
                ]
            )
            
            try:
                page = await browser.new_page()
                
                # Set user agent to avoid bot detection
                await page.set_user_agent(
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                )
                
                # Navigate to page with timeout
                await page.goto(url, wait_until="networkidle", timeout=30000)
                
                # Wait for content to load
                await page.wait_for_timeout(2000)
                
                # Generate PDF with optimized settings
                pdf_bytes = await page.pdf(
                    format='A4',
                    print_background=False,
                    margin={'top': '1cm', 'right': '1cm', 'bottom': '1cm', 'left': '1cm'}
                )
                
                if len(pdf_bytes) > MAX_PDF_SIZE:
                    logger.warning(f"PDF too large ({len(pdf_bytes)} bytes) for Textract processing")
                    return "", False
                
            finally:
                await browser.close()
        
        # Process with Textract
        logger.info(f"Processing PDF with Textract ({len(pdf_bytes)} bytes)")
        
        response = await asyncio.wait_for(
            asyncio.to_thread(
                textract.analyze_document,
                Document={'Bytes': pdf_bytes},
                FeatureTypes=['LAYOUT']
            ),
            timeout=TEXTRACT_TIMEOUT
        )
        
        # Extract and filter text blocks
        main_text_blocks = []
        header_footer_ids = set()
        
        # First pass: identify headers and footers
        for block in response['Blocks']:
            if block['BlockType'] == 'LAYOUT_HEADER':
                if 'Relationships' in block:
                    for rel in block['Relationships']:
                        if rel['Type'] == 'CHILD':
                            header_footer_ids.update(rel['Ids'])
            elif block['BlockType'] == 'LAYOUT_FOOTER':
                if 'Relationships' in block:
                    for rel in block['Relationships']:
                        if rel['Type'] == 'CHILD':
                            header_footer_ids.update(rel['Ids'])
        
        # Second pass: extract main content text
        for block in response['Blocks']:
            if (block['BlockType'] in ['LINE', 'WORD'] and 
                block['Id'] not in header_footer_ids and
                'Text' in block):
                
                text = block['Text'].strip()
                if text and len(text) > 3:  # Filter out very short fragments
                    main_text_blocks.append(text)
        
        # Combine and clean text
        if main_text_blocks:
            extracted_text = ' '.join(main_text_blocks)
            extracted_text = clean_extracted_text(extracted_text)
            
            if len(extracted_text) >= MIN_TEXT_LENGTH:
                logger.info(f"Textract extraction successful: {len(extracted_text)} characters")
                return extracted_text, True
            else:
                logger.warning(f"Textract extracted text too short: {len(extracted_text)} characters")
                return "", False
        else:
            logger.warning("No text blocks extracted by Textract")
            return "", False
            
    except asyncio.TimeoutError:
        logger.error(f"Textract processing timeout for {url}")
        return "", False
    except ClientError as e:
        logger.error(f"AWS Textract error for {url}: {str(e)}")
        return "", False
    except Exception as e:
        logger.error(f"Textract extraction failed for {url}: {str(e)}", exc_info=True)
        return "", False

async def extract_with_dom(url: str) -> Tuple[str, bool]:
    """
    Extract main content using DOM traversal as fallback method.
    
    Args:
        url (str): The webpage URL to process.
        
    Returns:
        Tuple[str, bool]: (extracted_text, success_flag)
    """
    if not await is_valid_url(url):
        logger.error(f"Invalid URL provided: {url}")
        return "", False
    
    try:
        logger.info(f"Starting DOM extraction for: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu'
                ]
            )
            
            try:
                page = await browser.new_page()
                
                # Set user agent
                await page.set_user_agent(
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                )
                
                # Navigate with timeout
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)
                
                # Find main content using multiple strategies
                main_content = await find_main_content_node(page)
                
                if main_content:
                    extracted_text = clean_extracted_text(main_content)
                    if len(extracted_text) >= MIN_TEXT_LENGTH:
                        logger.info(f"DOM extraction successful: {len(extracted_text)} characters")
                        return extracted_text, True
                    else:
                        logger.warning(f"DOM extracted text too short: {len(extracted_text)} characters")
                        return "", False
                else:
                    logger.warning("No main content found using DOM extraction")
                    return "", False
                    
            finally:
                await browser.close()
                
    except Exception as e:
        logger.error(f"DOM extraction failed for {url}: {str(e)}", exc_info=True)
        return "", False

async def find_main_content_node(page) -> Optional[str]:
    """
    Identify and extract main content using multiple heuristics.
    
    Args:
        page: Playwright page object.
        
    Returns:
        Optional[str]: Extracted main content text or None.
    """
    try:
        # Strategy 1: Semantic HTML elements
        semantic_selectors = [
            'main',
            'article',
            '[role="main"]',
            '[role="article"]',
            '[role="document"]'
        ]
        
        for selector in semantic_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    if text and len(text.strip()) > MIN_TEXT_LENGTH:
                        logger.info(f"Found content using semantic selector: {selector}")
                        return text.strip()
            except Exception:
                continue
        
        # Strategy 2: Common content class/id patterns
        content_selectors = [
            '[class*="main-content"]',
            '[class*="article-content"]',
            '[class*="post-content"]',
            '[class*="entry-content"]',
            '[class*="content-body"]',
            '[class*="article-body"]',
            '[id*="main-content"]',
            '[id*="article-content"]',
            '[id*="content"]'
        ]
        
        candidates = []
        
        for selector in content_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    # Skip if element is likely navigation, sidebar, or ads
                    if await is_likely_main_content(element):
                        text = await element.inner_text()
                        if text and len(text.strip()) > MIN_TEXT_LENGTH:
                            candidates.append((text.strip(), len(text.strip())))
            except Exception:
                continue
        
        # Strategy 3: Heuristic-based content detection
        if not candidates:
            try:
                # Look for the largest text block that's not navigation
                all_elements = await page.query_selector_all('div, section, article, p')
                
                for element in all_elements:
                    if await is_likely_main_content(element):
                        text = await element.inner_text()
                        if text and len(text.strip()) > MIN_TEXT_LENGTH:
                            candidates.append((text.strip(), len(text.strip())))
            except Exception:
                pass
        
        # Strategy 4: Fallback to body content with filtering
        if not candidates:
            try:
                body_text = await page.inner_text('body')
                if body_text and len(body_text.strip()) > MIN_TEXT_LENGTH:
                    # Basic filtering to remove navigation and footer content
                    filtered_text = filter_body_content(body_text)
                    if len(filtered_text) > MIN_TEXT_LENGTH:
                        candidates.append((filtered_text, len(filtered_text)))
            except Exception:
                pass
        
        # Return the longest candidate
        if candidates:
            best_candidate = max(candidates, key=lambda x: x[1])
            logger.info(f"Selected content with {best_candidate[1]} characters")
            return best_candidate[0]
        
        return None
        
    except Exception as e:
        logger.error(f"Error in find_main_content_node: {str(e)}")
        return None

async def is_likely_main_content(element) -> bool:
    """
    Determine if an element likely contains main content.
    
    Args:
        element: Playwright element object.
        
    Returns:
        bool: True if element likely contains main content.
    """
    try:
        # Get element attributes
        class_name = await element.get_attribute('class') or ''
        element_id = await element.get_attribute('id') or ''
        tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
        
        # Exclude navigation, sidebar, header, footer elements
        exclude_patterns = [
            'nav', 'navigation', 'menu', 'sidebar', 'aside', 'header', 'footer',
            'banner', 'advertisement', 'ad', 'social', 'share', 'related',
            'comments', 'pagination', 'breadcrumb', 'widget', 'toolbar'
        ]
        
        combined_attrs = f"{class_name} {element_id}".lower()
        
        for pattern in exclude_patterns:
            if pattern in combined_attrs:
                return False
        
        # Exclude common navigation tags
        if tag_name in ['nav', 'aside', 'header', 'footer']:
            return False
        
        # Check text length
        text = await element.inner_text()
        if not text or len(text.strip()) < MIN_TEXT_LENGTH:
            return False
        
        # Check for high link density (likely navigation)
        try:
            links = await element.query_selector_all('a')
            link_text_length = sum([
                len(await link.inner_text()) 
                for link in links[:10]  # Limit to avoid performance issues
            ])
            
            if len(text) > 0 and (link_text_length / len(text)) > 0.8:
                return False
        except Exception:
            pass
        
        return True
        
    except Exception:
        return False

def filter_body_content(body_text: str) -> str:
    """
    Filter body content to remove likely navigation and footer content.
    
    Args:
        body_text (str): Raw body text content.
        
    Returns:
        str: Filtered content.
    """
    lines = body_text.split('\n')
    filtered_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Skip lines that look like navigation
        if (len(line) < 100 and 
            any(keyword in line.lower() for keyword in [
                'home', 'about', 'contact', 'menu', 'login', 'register',
                'privacy', 'terms', 'copyright', '©', 'all rights reserved'
            ])):
            continue
        
        # Skip lines with high punctuation density (likely metadata)
        if len(line) > 0 and (line.count('|') + line.count('•') + line.count('-')) / len(line) > 0.3:
            continue
        
        filtered_lines.append(line)
    
    return '\n'.join(filtered_lines)

def clean_extracted_text(text: str) -> str:
    """
    Clean and normalize extracted text.
    
    Args:
        text (str): Raw extracted text.
        
    Returns:
        str: Cleaned text.
    """
    if not text:
        return ""
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove excessive punctuation
    text = re.sub(r'[.]{3,}', '...', text)
    text = re.sub(r'[-]{3,}', '---', text)
    
    # Remove common web artifacts
    artifacts = [
        'Cookie Policy',
        'Accept Cookies',
        'Privacy Policy',
        'Terms of Service',
        'Subscribe to Newsletter',
        'Follow us on',
        'Share this article',
        'Print this page'
    ]
    
    for artifact in artifacts:
        text = text.replace(artifact, '')
    
    # Remove URLs
    text = re.sub(r'https?://[^\s]+', '', text)
    
    # Clean up extra whitespace again
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

async def extract_content(url: str) -> Tuple[str, str]:
    """
    Extract content using Textract with DOM fallback.
    
    Args:
        url (str): The webpage URL to process.
        
    Returns:
        Tuple[str, str]: (extracted_text, extraction_method)
    """
    if not url or not isinstance(url, str):
        raise ValueError("A valid URL string is required")
    
    if not await is_valid_url(url):
        raise ValueError("Invalid URL format")
    
    logger.info(f"Starting content extraction for: {url}")
    
    # Try Textract first
    extracted_text, textract_success = await extract_with_textract(url)
    
    if textract_success and extracted_text:
        logger.info(f"Successfully extracted content using Textract: {len(extracted_text)} characters")
        return extracted_text, "textract"
    
    # Fallback to DOM extraction
    logger.info("Textract extraction failed or unavailable, falling back to DOM extraction")
    extracted_text, dom_success = await extract_with_dom(url)
    
    if dom_success and extracted_text:
        logger.info(f"Successfully extracted content using DOM: {len(extracted_text)} characters")
        return extracted_text, "dom"
    
    # If both methods fail
    logger.error(f"Both extraction methods failed for URL: {url}")
    raise Exception("Unable to extract content using any available method")

# Health check function for the extraction service
async def health_check() -> dict:
    """
    Perform health check for the extraction service.
    
    Returns:
        dict: Health status information.
    """
    status = {
        "textract_available": textract is not None,
        "playwright_available": True,  # If we got here, playwright is working
        "status": "healthy"
    }
    
    # Test Playwright
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            await browser.close()
    except Exception as e:
        status["playwright_available"] = False
        status["playwright_error"] = str(e)
        status["status"] = "degraded"
    
    # Test Textract (if available)
    if textract:
        try:
            # Simple test to verify Textract connectivity
            await asyncio.to_thread(textract.get_document_analysis, JobId="test")
        except ClientError as e:
            if e.response["Error"]["Code"] != "InvalidJobIdException":
                status["textract_available"] = False
                status["textract_error"] = str(e)
                status["status"] = "degraded"
        except Exception as e:
            status["textract_available"] = False
            status["textract_error"] = str(e)
            status["status"] = "degraded"
    
    return status