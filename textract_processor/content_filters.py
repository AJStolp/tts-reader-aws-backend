import re
import logging
from typing import Dict, List, Set, Optional, Tuple, Any
from urllib.parse import urlparse
from enum import Enum

logger = logging.getLogger(__name__)

class ContentPriority(Enum):
    CRITICAL = 10
    HIGH = 8
    MEDIUM = 6
    LOW = 4
    EXCLUDE = 0

class SitePattern(Enum):
    DOCUMENTATION = "docs"
    E_LEARNING = "learning"
    BLOG = "blog"
    NEWS = "news"
    E_COMMERCE = "ecommerce"
    FORUM = "forum"
    SOCIAL = "social"
    GENERIC = "generic"

class TTSContentFilter:
    def __init__(self):
        self.exclusion_patterns = self._load_exclusion_patterns()
        self.content_selectors = self._load_content_selectors()
        self.site_specific_rules = self._load_site_specific_rules()
        self.tts_optimization_rules = self._load_tts_optimization_rules()

    def _load_exclusion_patterns(self) -> Dict[str, List[str]]:
        """Comprehensive patterns for elements to exclude from TTS content"""
        return {
            "navigation": [
                "nav", "navbar", "navigation", "menu", "menubar",
                "breadcrumb", "breadcrumbs", "pagination", "pager",
                "header", "footer", "sidebar", "aside", "banner"
            ],
            "interactive": [
                "button", "btn", "form", "input", "select", "textarea",
                "dropdown", "modal", "popup", "overlay", "tooltip",
                "tab", "tabs", "accordion", "carousel", "slider",
                "tts-widget", "enterprise-tts-widget"  # Explicitly exclude TTS widget
            ],
            "advertisements": [
                "ad", "ads", "advertisement", "advertising", "sponsor",
                "promo", "promotion", "affiliate", "banner-ad",
                "google-ad", "adsense", "adsbygoogle"
            ],
            "social": [
                "social", "share", "sharing", "follow", "subscribe",
                "newsletter", "email-signup", "social-media",
                "twitter", "facebook", "linkedin", "instagram"
            ],
            "comments": [
                "comment", "comments", "discussion", "reply", "replies",
                "user-content", "ugc", "review", "rating", "feedback"
            ],
            "metadata": [
                "meta", "metadata", "byline", "author-bio", "tags",
                "categories", "published", "updated", "timestamp",
                "reading-time", "word-count", "print", "email"
            ],
            "related": [
                "related", "recommended", "suggestions", "more-like-this",
                "you-might-like", "trending", "popular", "recent"
            ],
            "elearning": [
                "vpn-switch-card", "instance-start", "target-system",
                "download-vpn", "spawn-target", "terminal", "vm-controls",
                "cheat-sheet", "resources", "hints"
                # Removed "lab", "server", "progress" to preserve relevant content
            ],
            "technical": [
                "debug", "developer", "console", "log", "error",
                "warning", "alert", "notification", "status",
                "loading", "spinner", "progress-bar",
                "tts-status", "tts-progress", "tts-controls"  # TTS-specific technical elements
            ]
        }

    def _load_content_selectors(self) -> Dict[str, int]:
        """Content selectors ranked by priority for TTS extraction"""
        return {
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
            "section": 7,
            ".section": 7,
            ".chapter": 7,
            ".lesson": 7,
            ".module": 7,
            ".container": 5,
            ".wrapper": 5,
            ".inner": 5,
            "div": 3,
        }

    def _load_site_specific_rules(self) -> Dict[SitePattern, Dict[str, Any]]:
        """Site-specific filtering rules for common platforms"""
        return {
            SitePattern.E_LEARNING: {
                "preserve_selectors": [
                    ".training-module", ".lesson-content", ".chapter",
                    ".exercise", ".lab-description", ".instructions",
                    ".module-content", ".tutorial-content"  # Preserve lab content
                ],
                "remove_selectors": [
                    ".vpn-switch-card", ".instance-start", ".target-system",
                    ".download-vpn", ".spawn-target", ".terminal", ".vm-controls",
                    ".sidebar", ".table-of-contents", ".navigation",
                    ".cheat-sheet", ".resources", ".hints",
                    ".tts-widget", ".enterprise-tts-widget"  # Explicitly remove TTS widget
                ],
                "content_indicators": [
                    "lab", "exercise", "lesson", "chapter", "module",
                    "tutorial", "guide", "instructions", "description"
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
                "privacy policy", "terms of service",
                "play", "pause", "stop", "read page",  # TTS widget controls
                "volume", "speed", "backend connection", "reading progress"  # TTS widget UI
            ],
            "remove_patterns": [
                r"Click\s+here\s+to\s+\w+",
                r"Follow\s+us\s+on\s+\w+",
                r"Subscribe\s+to\s+our\s+\w+",
                r"Download\s+our\s+\w+\s+app",
                r"Join\s+our\s+\w+\s+community",
                r"Sign\s+up\s+for\s+\w+",
                r"Get\s+\w+\s+updates",
                r"Enable\s+\w+\s+notifications",
                r"00:\d\d",  # Timer patterns (e.g., "00:00")
                r"▶️|⏸️|⏹️|📄|🔊|⏱️|📶"  # TTS widget emojis
            ],
            "preserve_elements": [
                "h1", "h2", "h3", "h4", "h5", "h6",
                "p", "div", "span",
                "blockquote", "code", "pre",
                "ul", "ol", "li",
                "strong", "em", "b", "i"
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
        try:
            domain = urlparse(url).netloc.lower()
            url_path = urlparse(url).path.lower()
            combined_text = f"{url} {title} {description}".lower()

            if any(pattern in domain for pattern in [
                "academy", "learn", "course", "training", "education",
                "hackthebox", "coursera", "udemy", "pluralsight"
            ]):
                return SitePattern.E_LEARNING
            if any(pattern in combined_text for pattern in [
                "docs", "documentation", "api", "reference",
                "guide", "manual", "wiki"
            ]):
                return SitePattern.DOCUMENTATION
            if any(pattern in url_path for pattern in [
                "/blog/", "/post/", "/article/"
            ]) or "blog" in domain:
                return SitePattern.BLOG
            if any(pattern in domain for pattern in [
                "news", "times", "post", "herald", "guardian",
                "cnn", "bbc", "reuters"
            ]):
                return SitePattern.NEWS
            if any(pattern in combined_text for pattern in [
                "shop", "store", "buy", "cart", "product",
                "amazon", "ebay", "shopify"
            ]):
                return SitePattern.E_COMMERCE
            if any(pattern in combined_text for pattern in [
                "forum", "discussion", "thread", "reddit",
                "stackoverflow", "discourse"
            ]):
                return SitePattern.FORUM
            if any(pattern in domain for pattern in [
                "twitter", "facebook", "linkedin", "instagram",
                "tiktok", "youtube", "reddit"
            ]):
                return SitePattern.SOCIAL
            return SitePattern.GENERIC
        except Exception as e:
            logger.warning(f"Error detecting site pattern: {e}")
            return SitePattern.GENERIC

    async def filter_page_for_tts(self, page, url: str, title: str = "", selection_text: Optional[str] = None) -> Tuple[bool, str]:
        """
        Apply comprehensive content filtering to page or selection text before PDF generation
        Returns (success: bool, filtered_text: str)
        """
        try:
            if selection_text:
                logger.info(f"Processing provided selection text: {selection_text[:30]}... ({len(selection_text)} chars)")
                filtered_text = self._normalize_text(selection_text)
                if self._validate_text(filtered_text):
                    logger.info("Selection text filtering successful")
                    return True, filtered_text
                logger.warning("Selection text validation failed")
                return False, ""

            site_pattern = self.detect_site_pattern(url, title)
            logger.info(f"Applying TTS content filtering for {site_pattern.value} pattern: {url}")

            await self._remove_unwanted_elements(page, site_pattern)
            await self._apply_site_specific_filtering(page, site_pattern)
            await self._optimize_content_for_tts(page)
            filtered_text = await self._extract_filtered_text(page)
            content_remains = await self._validate_content_remains(page)

            if content_remains:
                logger.info(f"TTS content filtering successful for {url}")
                return True, filtered_text
            logger.warning(f"No meaningful content remains after filtering: {url}")
            return False, ""

        except Exception as e:
            logger.error(f"Error during TTS content filtering: {e}")
            return False, ""

    async def _remove_unwanted_elements(self, page, site_pattern: SitePattern):
        try:
            selectors_to_remove = []
            for category, patterns in self.exclusion_patterns.items():
                for pattern in patterns:
                    selectors_to_remove.extend([pattern, f".{pattern}", f"#{pattern}", f'[class*="{pattern}"]', f'[id*="{pattern}"]'])
            selectors_to_remove.extend(["script", "style", "noscript", "iframe", "embed", "object", "video", "audio", "canvas", "svg", "map", "area"])
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
                        }} catch (e) {{}}
                    }});
                    console.log(`Removed ${{removedCount}} unwanted elements for TTS`);
                    return removedCount;
                }}
            ''')
        except Exception as e:
            logger.error(f"Error removing unwanted elements: {e}")

    async def _apply_site_specific_filtering(self, page, site_pattern: SitePattern):
        try:
            if site_pattern not in self.site_specific_rules:
                return
            rules = self.site_specific_rules[site_pattern]
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
                            }} catch (e) {{}}
                        }});
                    }}
                ''')
            logger.info(f"Applied {site_pattern.value} specific filtering")
        except Exception as e:
            logger.error(f"Error applying site-specific filtering: {e}")

    async def _optimize_content_for_tts(self, page):
        try:
            tts_rules = self.tts_optimization_rules
            remove_phrases = tts_rules["remove_phrases"]
            remove_patterns = tts_rules["remove_patterns"]
            phrases_js = ', '.join([f'"{phrase}"' for phrase in remove_phrases])
            patterns_js = ', '.join([f'"{pattern}"' for pattern in remove_patterns])

            await page.evaluate(f'''
                () => {{
                    const phrasesToRemove = [{phrases_js}];
                    const patternsToRemove = [{patterns_js}];
                    phrasesToRemove.forEach(phrase => {{
                        const regex = new RegExp(phrase, 'gi');
                        document.body.innerHTML = document.body.innerHTML.replace(regex, '');
                    }});
                    patternsToRemove.forEach(pattern => {{
                        try {{
                            const regex = new RegExp(pattern, 'gi');
                            document.body.innerHTML = document.body.innerHTML.replace(regex, '');
                        }} catch (e) {{}}
                    }});
                    document.querySelectorAll('*').forEach(el => {{
                        if (el.children.length === 0 && el.textContent.trim() === '') {{
                            if (el.parentNode) {{
                                el.parentNode.removeChild(el);
                            }}
                        }}
                    }});
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

    def _normalize_text(self, text: str) -> str:
        """Normalize text for TTS processing"""
        normalized = text
        for phrase in self.tts_optimization_rules["remove_phrases"]:
            normalized = normalized.replace(phrase, '')
        for pattern in self.tts_optimization_rules["remove_patterns"]:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        if self.tts_optimization_rules["text_processing"]["normalize_whitespace"]:
            normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized

    async def _extract_filtered_text(self, page) -> str:
        """Extract filtered text from page"""
        try:
            text = await page.evaluate('''
                () => {
                    const selectors = ['article', 'main', '[role="main"]', '.content', '.post-content', '.entry-content', '.article-content', 'section', 'p'];
                    let text = '';
                    selectors.forEach(selector => {
                        document.querySelectorAll(selector).forEach(el => {
                            if (el.innerText && !el.closest('.tts-widget, .enterprise-tts-widget')) {
                                text += el.innerText + ' ';
                            }
                        });
                    });
                    return text;
                }
            ''')
            return self._normalize_text(text)
        except Exception as e:
            logger.error(f"Error extracting filtered text: {e}")
            return ""

    def _validate_text(self, text: str) -> bool:
        """Validate that text is suitable for TTS"""
        try:
            word_count = len(text.split())
            return (
                len(text) >= self.tts_optimization_rules["text_processing"]["min_paragraph_length"] and
                len(text) <= self.tts_optimization_rules["text_processing"]["max_paragraph_length"] and
                word_count >= 3
            )
        except Exception as e:
            logger.error(f"Error validating text: {e}")
            return False

    def score_content_block(self, text: str, element_info: Dict[str, str]) -> float:
        try:
            if not text or len(text.strip()) < 20:
                return 0.0
            score = 0.5
            text_len = len(text.strip())
            if 100 <= text_len <= 5000:
                score += 0.2
            elif text_len > 5000:
                score += 0.1
            elif text_len < 50:
                score -= 0.3
            tag_name = element_info.get("tag_name", "").lower()
            if tag_name in ["article", "main", "section"]:
                score += 0.2
            elif tag_name in ["p", "div"]:
                score += 0.1
            class_id = f"{element_info.get('class_name', '')} {element_info.get('id', '')}".lower()
            positive_indicators = ["content", "article", "post", "story", "main", "text"]
            for indicator in positive_indicators:
                if indicator in class_id:
                    score += 0.1
                    break
            negative_indicators = ["nav", "menu", "sidebar", "footer", "header", "ad"]
            for indicator in negative_indicators:
                if indicator in class_id:
                    score -= 0.3
                    break
            link_chars = sum(len(link) for link in re.findall(r'<a[^>]*>([^<]*)</a>', text, re.IGNORECASE))
            if text_len > 0:
                link_density = link_chars / text_len
                if link_density > 0.5:
                    score -= 0.4
                elif link_density > 0.3:
                    score -= 0.2
            sentences = re.split(r'[.!?]+', text)
            avg_sentence_length = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
            if 10 <= avg_sentence_length <= 30:
                score += 0.1
            return max(0.0, min(1.0, score))
        except Exception as e:
            logger.error(f"Error scoring content block: {e}")
            return 0.0

    async def extract_main_content_areas(self, page) -> List[Dict[str, Any]]:
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
                                        text: text.substring(0, 5000),
                                        textLength: text.length,
                                        tagName: el.tagName.toLowerCase(),
                                        className: el.className || '',
                                        id: el.id || '',
                                        hasHeadings: el.querySelectorAll('h1, h2, h3, h4, h5, h6').length,
                                        hasParagraphs: el.querySelectorAll('p').length
                                    });
                                }
                            });
                        } catch (e) {}
                    });
                    return areas;
                }
            ''')
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
            scored_areas.sort(key=lambda x: x["tts_score"], reverse=True)
            return scored_areas
        except Exception as e:
            logger.error(f"Error extracting main content areas: {e}")
            return []

tts_content_filter = TTSContentFilter()

async def apply_tts_content_filtering(page, url: str, title: str = "", selection_text: Optional[str] = None) -> Tuple[bool, str]:
    return await tts_content_filter.filter_page_for_tts(page, url, title, selection_text)

async def get_filtered_content_areas(page) -> List[Dict[str, Any]]:
    return await tts_content_filter.extract_main_content_areas(page)

def detect_website_pattern(url: str, title: str = "", description: str = "") -> SitePattern:
    return tts_content_filter.detect_site_pattern(url, title, description)