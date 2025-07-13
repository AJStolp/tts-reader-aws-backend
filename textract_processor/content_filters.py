"""
Enterprise-grade content filtering for TTS optimization before AWS Textract processing
Removes navigation, ads, and non-content elements to ensure clean PDF generation
"""
import re
import logging
from typing import Dict, List, Set, Optional, Tuple, Any
from urllib.parse import urlparse
from enum import Enum

logger = logging.getLogger(__name__)

class ContentPriority(Enum):
    """Content priority levels for TTS extraction"""
    CRITICAL = 10    # Main article content
    HIGH = 8        # Supporting content, captions
    MEDIUM = 6      # Secondary content, sidebars with relevant info
    LOW = 4         # Less important content
    EXCLUDE = 0     # Navigation, ads, forms - should be removed

class SitePattern(Enum):
    """Common website patterns for specialized filtering"""
    DOCUMENTATION = "docs"
    E_LEARNING = "learning"  # Like HackTheBox Academy
    BLOG = "blog"
    NEWS = "news"
    E_COMMERCE = "ecommerce"
    FORUM = "forum"
    SOCIAL = "social"
    GENERIC = "generic"

class TTSContentFilter:
    """Enterprise content filtering for TTS optimization before AWS Textract processing"""
    
    def __init__(self):
        self.exclusion_patterns = self._load_exclusion_patterns()
        self.content_selectors = self._load_content_selectors()
        self.site_specific_rules = self._load_site_specific_rules()
        self.tts_optimization_rules = self._load_tts_optimization_rules()
    
    def _load_exclusion_patterns(self) -> Dict[str, List[str]]:
        """Comprehensive patterns for elements to exclude from TTS content"""
        return {
            # Navigation and structural elements
            "navigation": [
                "nav", "navbar", "navigation", "menu", "menubar",
                "breadcrumb", "breadcrumbs", "pagination", "pager",
                "header", "footer", "sidebar", "aside", "banner"
            ],
            
            # Interactive elements not suitable for TTS
            "interactive": [
                "button", "btn", "form", "input", "select", "textarea",
                "dropdown", "modal", "popup", "overlay", "tooltip",
                "tab", "tabs", "accordion", "carousel", "slider"
            ],
            
            # Advertisements and promotional content
            "advertisements": [
                "ad", "ads", "advertisement", "advertising", "sponsor",
                "promo", "promotion", "affiliate", "banner-ad",
                "google-ad", "adsense", "adsbygoogle"
            ],
            
            # Social and sharing elements
            "social": [
                "social", "share", "sharing", "follow", "subscribe",
                "newsletter", "email-signup", "social-media",
                "twitter", "facebook", "linkedin", "instagram"
            ],
            
            # Comments and user-generated content
            "comments": [
                "comment", "comments", "discussion", "reply", "replies",
                "user-content", "ugc", "review", "rating", "feedback"
            ],
            
            # Metadata and auxiliary content
            "metadata": [
                "meta", "metadata", "byline", "author-bio", "tags",
                "categories", "published", "updated", "timestamp",
                "reading-time", "word-count", "print", "email"
            ],
            
            # Related content and recommendations
            "related": [
                "related", "recommended", "suggestions", "more-like-this",
                "you-might-like", "trending", "popular", "recent", "enterprise-tts-widget"
            ],
            
            # E-learning specific (like HackTheBox)
            "elearning": [
                "vpn", "instance", "spawn", "target", "lab", "vm",
                "download", "connection", "server", "protocol",
                "cheat-sheet", "resources", "table-of-contents",
                "progress", "completion", "badge", "certificate"
            ],
            
            # Technical/debugging elements
            "technical": [
                "debug", "developer", "console", "log", "error",
                "warning", "alert", "notification", "status",
                "loading", "spinner", "progress-bar"
            ]
        }
    
    def _load_content_selectors(self) -> Dict[str, int]:
        """Content selectors ranked by priority for TTS extraction"""
        return {
            # Highest priority - semantic main content
            "article": 10,
            "main": 10,
            '[role="main"]': 10,
            ".main-content": 9,
            ".article-content": 9,
            ".post-content": 9,
            ".entry-content": 9,
            ".content": 8,
            ".page-content": 8,
            ".story-body": 8,
            ".text-content": 8,
            
            # Medium priority - structural content
            "section": 7,
            ".section": 7,
            ".chapter": 7,
            ".lesson": 7,
            ".module": 7,
            
            # Lower priority - generic containers
            ".container": 5,
            ".wrapper": 5,
            ".inner": 5,
            "div": 3,  # Lowest priority fallback
        }
    
    def _load_site_specific_rules(self) -> Dict[SitePattern, Dict[str, Any]]:
        """Site-specific filtering rules for common platforms"""
        return {
            SitePattern.E_LEARNING: {
                "preserve_selectors": [
                    ".training-module", ".lesson-content", ".chapter",
                    ".exercise", ".lab-description", ".instructions"
                ],
                "remove_selectors": [
                    ".vpn-switch-card", ".instance-start", ".target-system",
                    ".download-vpn", ".spawn-target", ".terminal", ".vm-controls",
                    ".sidebar", ".table-of-contents", ".navigation",
                    ".cheat-sheet", ".resources", ".hints"
                ],
                "content_indicators": [
                    "lab", "exercise", "lesson", "chapter", "module",
                    "tutorial", "guide", "instructions"
                ]
            },
            
            SitePattern.DOCUMENTATION: {
                "preserve_selectors": [
                    ".docs-content", ".documentation", ".guide",
                    ".tutorial", ".manual", ".reference"
                ],
                "remove_selectors": [
                    ".docs-nav", ".api-nav", ".version-selector",
                    ".edit-page", ".github-link", ".search"
                ],
                "content_indicators": [
                    "documentation", "docs", "guide", "tutorial",
                    "manual", "reference", "api"
                ]
            },
            
            SitePattern.BLOG: {
                "preserve_selectors": [
                    ".post", ".blog-post", ".article", ".entry"
                ],
                "remove_selectors": [
                    ".blog-sidebar", ".widget", ".archive",
                    ".tag-cloud", ".recent-posts", ".author-box"
                ]
            },
            
            SitePattern.NEWS: {
                "preserve_selectors": [
                    ".story", ".article", ".news-content"
                ],
                "remove_selectors": [
                    ".breaking-news", ".trending", ".most-read",
                    ".newsletter-signup", ".subscription"
                ]
            }
        }
    
    def _load_tts_optimization_rules(self) -> Dict[str, Any]:
        """Rules specifically for TTS content optimization"""
        return {
            "remove_phrases": [
                "click here", "read more", "continue reading",
                "skip to content", "jump to navigation",
                "print this page", "email this article",
                "share on facebook", "tweet this",
                "subscribe to newsletter", "follow us on",
                "accept cookies", "cookie policy",
                "privacy policy", "terms of service"
            ],
            
            "remove_patterns": [
                r"Click\s+here\s+to\s+\w+",
                r"Follow\s+us\s+on\s+\w+",
                r"Subscribe\s+to\s+our\s+\w+",
                r"Download\s+our\s+\w+\s+app",
                r"Join\s+our\s+\w+\s+community",
                r"Sign\s+up\s+for\s+\w+",
                r"Get\s+\w+\s+updates",
                r"Enable\s+\w+\s+notifications"
            ],
            
            "preserve_elements": [
                "h1", "h2", "h3", "h4", "h5", "h6",  # Headings
                "p", "div", "span",  # Text containers
                "blockquote", "code", "pre",  # Special content
                "ul", "ol", "li",  # Lists
                "strong", "em", "b", "i"  # Emphasis
            ],
            
            "text_processing": {
                "min_paragraph_length": 20,
                "max_paragraph_length": 5000,
                "min_sentence_length": 10,
                "remove_single_words": True,
                "normalize_whitespace": True
            }
        }
    
    def detect_site_pattern(self, url: str, title: str = "", description: str = "") -> SitePattern:
        """Detect the type of website for specialized filtering"""
        try:
            domain = urlparse(url).netloc.lower()
            url_path = urlparse(url).path.lower()
            combined_text = f"{url} {title} {description}".lower()
            
            # E-learning platforms
            if any(pattern in domain for pattern in [
                "academy", "learn", "course", "training", "education",
                "hackthebox", "coursera", "udemy", "pluralsight"
            ]):
                return SitePattern.E_LEARNING
            
            # Documentation sites
            if any(pattern in combined_text for pattern in [
                "docs", "documentation", "api", "reference",
                "guide", "manual", "wiki"
            ]):
                return SitePattern.DOCUMENTATION
            
            # Blog patterns
            if any(pattern in url_path for pattern in [
                "/blog/", "/post/", "/article/"
            ]) or "blog" in domain:
                return SitePattern.BLOG
            
            # News sites
            if any(pattern in domain for pattern in [
                "news", "times", "post", "herald", "guardian",
                "cnn", "bbc", "reuters"
            ]):
                return SitePattern.NEWS
            
            # E-commerce
            if any(pattern in combined_text for pattern in [
                "shop", "store", "buy", "cart", "product",
                "amazon", "ebay", "shopify"
            ]):
                return SitePattern.E_COMMERCE
            
            # Forums
            if any(pattern in combined_text for pattern in [
                "forum", "discussion", "thread", "reddit",
                "stackoverflow", "discourse"
            ]):
                return SitePattern.FORUM
            
            # Social media
            if any(pattern in domain for pattern in [
                "twitter", "facebook", "linkedin", "instagram",
                "tiktok", "youtube", "reddit"
            ]):
                return SitePattern.SOCIAL
            
            return SitePattern.GENERIC
            
        except Exception as e:
            logger.warning(f"Error detecting site pattern: {e}")
            return SitePattern.GENERIC
    
    async def filter_page_for_tts(self, page, url: str, title: str = "") -> bool:
        """
        Apply comprehensive content filtering to page before PDF generation
        Returns True if filtering was successful
        """
        try:
            site_pattern = self.detect_site_pattern(url, title)
            logger.info(f"Applying TTS content filtering for {site_pattern.value} pattern: {url}")
            
            # Step 1: Remove unwanted elements by patterns
            await self._remove_unwanted_elements(page, site_pattern)
            
            # Step 2: Apply site-specific filtering
            await self._apply_site_specific_filtering(page, site_pattern)
            
            # Step 3: Clean up remaining content for TTS
            await self._optimize_content_for_tts(page)
            
            # Step 4: Validate that meaningful content remains
            content_remains = await self._validate_content_remains(page)
            
            if content_remains:
                logger.info(f"TTS content filtering successful for {url}")
                return True
            else:
                logger.warning(f"No meaningful content remains after filtering: {url}")
                return False
                
        except Exception as e:
            logger.error(f"Error during TTS content filtering: {e}")
            return False
    
    async def _remove_unwanted_elements(self, page, site_pattern: SitePattern):
        """Remove elements that should not appear in TTS content"""
        try:
            # Build comprehensive selector list
            selectors_to_remove = []
            
            # Add pattern-based selectors
            for category, patterns in self.exclusion_patterns.items():
                for pattern in patterns:
                    # Element selectors
                    selectors_to_remove.append(pattern)
                    # Class selectors
                    selectors_to_remove.append(f".{pattern}")
                    # ID selectors  
                    selectors_to_remove.append(f"#{pattern}")
                    # Attribute selectors
                    selectors_to_remove.append(f'[class*="{pattern}"]')
                    selectors_to_remove.append(f'[id*="{pattern}"]')
            
            # Add common unwanted elements
            unwanted_elements = [
                "script", "style", "noscript", "iframe", "embed", "object",
                "video", "audio", "canvas", "svg", "map", "area"
            ]
            selectors_to_remove.extend(unwanted_elements)
            
            # Execute removal
            selectors_js = ', '.join([f'"{sel}"' for sel in selectors_to_remove])
            
            await page.evaluate(f'''
                () => {{
                    const selectors = [{selectors_js}];
                    let removedCount = 0;
                    
                    selectors.forEach(selector => {{
                        try {{
                            const elements = document.querySelectorAll(selector);
                            elements.forEach(el => {{
                                if (el && el.parentNode) {{
                                    el.parentNode.removeChild(el);
                                    removedCount++;
                                }}
                            }});
                        }} catch (e) {{
                            // Ignore invalid selectors
                        }}
                    }});
                    
                    console.log(`Removed ${{removedCount}} unwanted elements for TTS`);
                    return removedCount;
                }}
            ''')
            
        except Exception as e:
            logger.error(f"Error removing unwanted elements: {e}")
    
    async def _apply_site_specific_filtering(self, page, site_pattern: SitePattern):
        """Apply site-specific filtering rules"""
        try:
            if site_pattern not in self.site_specific_rules:
                return
            
            rules = self.site_specific_rules[site_pattern]
            
            # Remove site-specific unwanted elements
            if "remove_selectors" in rules:
                remove_selectors = ', '.join([f'"{sel}"' for sel in rules["remove_selectors"]])
                
                await page.evaluate(f'''
                    () => {{
                        const selectors = [{remove_selectors}];
                        selectors.forEach(selector => {{
                            try {{
                                document.querySelectorAll(selector).forEach(el => {{
                                    if (el && el.parentNode) {{
                                        el.parentNode.removeChild(el);
                                    }}
                                }});
                            }} catch (e) {{
                                // Ignore invalid selectors
                            }}
                        }});
                    }}
                ''')
            
            logger.info(f"Applied {site_pattern.value} specific filtering")
            
        except Exception as e:
            logger.error(f"Error applying site-specific filtering: {e}")
    
    async def _optimize_content_for_tts(self, page):
        """Optimize remaining content specifically for TTS reading"""
        try:
            tts_rules = self.tts_optimization_rules
            
            # Remove TTS-unfriendly phrases and patterns
            remove_phrases = tts_rules["remove_phrases"]
            remove_patterns = tts_rules["remove_patterns"]
            
            phrases_js = ', '.join([f'"{phrase}"' for phrase in remove_phrases])
            patterns_js = ', '.join([f'"{pattern}"' for pattern in remove_patterns])
            
            await page.evaluate(f'''
                () => {{
                    const phrasesToRemove = [{phrases_js}];
                    const patternsToRemove = [{patterns_js}];
                    
                    // Remove unwanted phrases
                    phrasesToRemove.forEach(phrase => {{
                        const regex = new RegExp(phrase, 'gi');
                        document.body.innerHTML = document.body.innerHTML.replace(regex, '');
                    }});
                    
                    // Remove pattern matches
                    patternsToRemove.forEach(pattern => {{
                        try {{
                            const regex = new RegExp(pattern, 'gi');
                            document.body.innerHTML = document.body.innerHTML.replace(regex, '');
                        }} catch (e) {{
                            // Ignore invalid regex patterns
                        }}
                    }});
                    
                    // Clean up empty elements and normalize spacing
                    document.querySelectorAll('*').forEach(el => {{
                        if (el.children.length === 0 && el.textContent.trim() === '') {{
                            if (el.parentNode) {{
                                el.parentNode.removeChild(el);
                            }}
                        }}
                    }});
                    
                    // Normalize whitespace in text nodes
                    function normalizeWhitespace(node) {{
                        if (node.nodeType === Node.TEXT_NODE) {{
                            node.textContent = node.textContent.replace(/\\s+/g, ' ').trim();
                        }} else {{
                            for (let child of node.childNodes) {{
                                normalizeWhitespace(child);
                            }}
                        }}
                    }}
                    
                    normalizeWhitespace(document.body);
                }}
            ''')
            
        except Exception as e:
            logger.error(f"Error optimizing content for TTS: {e}")
    
    async def _validate_content_remains(self, page) -> bool:
        """Validate that meaningful content remains after filtering"""
        try:
            content_metrics = await page.evaluate('''
                () => {
                    const bodyText = document.body.innerText || '';
                    const paragraphs = document.querySelectorAll('p, div, article, section').length;
                    const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6').length;
                    
                    return {
                        textLength: bodyText.length,
                        wordCount: bodyText.split(/\\s+/).filter(word => word.length > 0).length,
                        paragraphs: paragraphs,
                        headings: headings,
                        hasMainContent: bodyText.length > 200 && paragraphs > 0
                    };
                }
            ''')
            
            # Check if sufficient content remains
            min_text_length = 200
            min_word_count = 30
            
            is_valid = (
                content_metrics["textLength"] >= min_text_length and
                content_metrics["wordCount"] >= min_word_count and
                content_metrics["paragraphs"] > 0
            )
            
            logger.info(f"Content validation: {content_metrics['textLength']} chars, "
                       f"{content_metrics['wordCount']} words, "
                       f"{content_metrics['paragraphs']} paragraphs - {'Valid' if is_valid else 'Invalid'}")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Error validating remaining content: {e}")
            return False
    
    def score_content_block(self, text: str, element_info: Dict[str, str]) -> float:
        """Score a content block for TTS suitability (0.0 to 1.0)"""
        try:
            if not text or len(text.strip()) < 20:
                return 0.0
            
            score = 0.5  # Base score
            
            # Text length scoring
            text_len = len(text.strip())
            if 100 <= text_len <= 5000:
                score += 0.2
            elif text_len > 5000:
                score += 0.1
            elif text_len < 50:
                score -= 0.3
            
            # Semantic element bonus
            tag_name = element_info.get("tag_name", "").lower()
            if tag_name in ["article", "main", "section"]:
                score += 0.2
            elif tag_name in ["p", "div"]:
                score += 0.1
            
            # Class and ID analysis
            class_id = f"{element_info.get('class_name', '')} {element_info.get('id', '')}".lower()
            
            # Positive indicators
            positive_indicators = ["content", "article", "post", "story", "main", "text"]
            for indicator in positive_indicators:
                if indicator in class_id:
                    score += 0.1
                    break
            
            # Negative indicators
            negative_indicators = ["nav", "menu", "sidebar", "footer", "header", "ad"]
            for indicator in negative_indicators:
                if indicator in class_id:
                    score -= 0.3
                    break
            
            # Link density penalty
            link_chars = sum(len(link) for link in re.findall(r'<a[^>]*>([^<]*)</a>', text, re.IGNORECASE))
            if text_len > 0:
                link_density = link_chars / text_len
                if link_density > 0.5:
                    score -= 0.4
                elif link_density > 0.3:
                    score -= 0.2
            
            # Sentence structure bonus
            sentences = re.split(r'[.!?]+', text)
            avg_sentence_length = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
            if 10 <= avg_sentence_length <= 30:
                score += 0.1
            
            return max(0.0, min(1.0, score))
            
        except Exception as e:
            logger.error(f"Error scoring content block: {e}")
            return 0.0
    
    async def extract_main_content_areas(self, page) -> List[Dict[str, Any]]:
        """Extract and score main content areas for TTS processing"""
        try:
            content_areas = await page.evaluate('''
                () => {
                    const contentSelectors = [
                        'article', 'main', '[role="main"]',
                        '.content', '.post-content', '.entry-content',
                        '.article-content', '.page-content', '.story-body',
                        'section', '.section'
                    ];
                    
                    const areas = [];
                    
                    contentSelectors.forEach(selector => {
                        try {
                            const elements = document.querySelectorAll(selector);
                            elements.forEach((el, index) => {
                                const text = el.innerText || '';
                                if (text.length > 50) {
                                    areas.push({
                                        selector: selector,
                                        index: index,
                                        text: text.substring(0, 5000), // Limit for processing
                                        textLength: text.length,
                                        tagName: el.tagName.toLowerCase(),
                                        className: el.className || '',
                                        id: el.id || '',
                                        hasHeadings: el.querySelectorAll('h1, h2, h3, h4, h5, h6').length,
                                        hasParagraphs: el.querySelectorAll('p').length
                                    });
                                }
                            });
                        } catch (e) {
                            // Skip invalid selectors
                        }
                    });
                    
                    return areas;
                }
            ''')
            
            # Score each content area
            scored_areas = []
            for area in content_areas:
                element_info = {
                    "tag_name": area["tagName"],
                    "class_name": area["className"],
                    "id": area["id"]
                }
                
                score = self.score_content_block(area["text"], element_info)
                
                area_data = {
                    **area,
                    "tts_score": score,
                    "priority": ContentPriority.CRITICAL if score > 0.8 else
                               ContentPriority.HIGH if score > 0.6 else
                               ContentPriority.MEDIUM if score > 0.4 else
                               ContentPriority.LOW
                }
                
                scored_areas.append(area_data)
            
            # Sort by score (best first)
            scored_areas.sort(key=lambda x: x["tts_score"], reverse=True)
            
            return scored_areas
            
        except Exception as e:
            logger.error(f"Error extracting main content areas: {e}")
            return []

# Global instance for use across the application
tts_content_filter = TTSContentFilter()

# Convenience functions for integration with existing extractors
async def apply_tts_content_filtering(page, url: str, title: str = "") -> bool:
    """Apply TTS content filtering to a Playwright page before PDF generation"""
    return await tts_content_filter.filter_page_for_tts(page, url, title)

async def get_filtered_content_areas(page) -> List[Dict[str, Any]]:
    """Get scored and filtered content areas suitable for TTS"""
    return await tts_content_filter.extract_main_content_areas(page)

def detect_website_pattern(url: str, title: str = "", description: str = "") -> SitePattern:
    """Detect website pattern for specialized content filtering"""
    return tts_content_filter.detect_site_pattern(url, title, description)