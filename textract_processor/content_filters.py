import re
import logging
from typing import Dict, List, Set, Optional, Tuple, Any
from urllib.parse import urlparse
from enum import Enum
import json

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
        return {
            "navigation": [
                "nav", "navbar", "navigation", "menu", "menubar",
                "breadcrumb", "breadcrumbs", "pagination", "pager",
                "header", "footer", "sidebar", "aside", "banner",
                "mobile-menu", "mobile-nav", "menu-toggle", "menu-button",
                "nav-menu", "main-menu", "primary-nav", "secondary-nav"
            ],
            "interactive": [
                "button", "btn", "form", "input", "select", "textarea",
                "dropdown", "modal", "popup", "overlay", "tooltip",
                "tab", "tabs", "accordion", "carousel", "slider",
                "tts-widget", "enterprise-tts-widget",
                "sign-up", "sign-in", "login", "register", "auth",
                "search", "search-box", "search-form", "filters",
                "toggle", "switch", "checkbox", "radio"
            ],
            "author_metadata": [
                "author", "byline", "bio", "profile", "user-info", "writer",
                "contributor", "published", "publish", "date", "timestamp",
                "read-time", "reading-time", "word-count", "meta", "metadata",
                "author-info", "post-meta", "article-meta", "entry-meta",
                "tags", "categories", "updated", "print", "email", "author-bio"
            ],
            "engagement_widgets": [
                "vote", "clap", "like", "heart", "reaction", "engagement",
                "interaction", "social", "share", "follow", "subscribe",
                "bookmark", "save", "flag", "report", "responses"
            ],
            "ui_elements": [
                "tooltip", "dropdown", "popup", "modal", "menu", "overlay",
                "badge", "tag", "chip", "pill", "popover", "menuitem"
            ],
            "advertisements": [
                "ad", "ads", "advertisement", "advertising", "sponsor",
                "promo", "promotion", "affiliate", "banner-ad",
                "google-ad", "adsense", "adsbygoogle",
                "ad-banner", "ad-container", "ad-slot", "ad-unit", "sponsored",
                "pub-network", "doubleclick", "amazon-adsystem",
                "quantserve", "outbrain", "taboola", "criteo"
            ],
            "social": [
                "social", "share", "sharing", "follow", "subscribe",
                "newsletter", "email-signup", "social-media",
                "twitter", "facebook", "linkedin", "instagram",
                "youtube", "tiktok", "pinterest", "reddit",
                "social-icons", "social-links", "share-buttons"
            ],
            "comments": [
                "comment", "comments", "discussion", "reply", "replies",
                "user-content", "ugc", "review", "rating", "feedback",
                "disqus", "livefyre", "facebook-comments", "intensedebate"
            ],
            "related": [
                "related", "recommended", "suggestions", "more-like-this",
                "you-might-like", "trending", "popular", "recent",
                "similar", "also-read", "recommended-posts", "related-articles"
            ],
            "tracking": [
                "gtm", "google-tag-manager", "analytics", "ga", "gtag",
                "pixel", "tracking", "tracker", "dataLayer", "tag-manager",
                "fb-pixel", "twitter-pixel", "linkedin-insight", "hotjar",
                "mixpanel", "segment", "amplitude", "intercom", "zendesk",
                "optimizely", "ab-test", "experiment", "conversion"
            ],
            "cookies": [
                "cookie", "cookies", "consent", "privacy", "gdpr",
                "cookie-banner", "cookie-notice", "privacy-policy",
                "terms", "legal", "compliance", "data-policy"
            ],
            "elearning": [
                "vpn-switch-card", "instance-start", "target-system",
                "download-vpn", "spawn-target", "terminal", "vm-controls",
                "cheat-sheet", "resources", "hints",
                "lab-controls", "exercise-controls", "quiz", "assessment", "progress"
            ],
            "technical": [
                "debug", "developer", "console", "log", "error",
                "warning", "alert", "notification", "status",
                "loading", "spinner", "progress-bar",
                "tts-status", "tts-progress", "tts-controls",
                "dev-tools", "inspector", "debugger", "profiler"
            ]
        }

    def _get_script_source_filters(self) -> List[str]:
        return [
            "googletagmanager.com", "google-analytics.com", "gtag", "gtm.js",
            "analytics.js", "ga.js", "doubleclick.net", "googlesyndication.com",
            "amazon-adsystem.com", "quantserve.com", "facebook.net",
            "connect.facebook.net", "fbevents.js", "twitter.com/i/adsct",
            "linkedin.com/li.lms-analytics", "hotjar.com", "mixpanel.com",
            "segment.com", "amplitude.com", "intercom.io", "zendesk.com",
            "optimizely.com", "ab-testing", "fraudblocker.com", "pub.network",
            "outbrain.com", "taboola.com", "criteo.com", "adsystem.com"
        ]

    def _get_enhanced_css_selectors(self) -> List[str]:
        return [
            '[role="tooltip"]',
            '[role="button"]',
            '[role="menuitem"]',
            '[aria-hidden="true"]',
            '[aria-label*="follow"]',
            '[aria-label*="subscribe"]',
            '[aria-label*="share"]',
            '[aria-label*="bookmark"]',
            '[aria-label*="like"]',
            '[aria-label*="clap"]',
            '[aria-label*="vote"]',
            '[aria-label*="responses"]',
            '[aria-label*="comment"]',
            '[data-testid*="clap"]',
            '[data-testid*="bookmark"]',
            '[data-testid*="share"]',
            '[data-testid*="author"]',
            '[data-testid*="follow"]',
            '[data-testid*="vote"]',
            '[data-testid*="like"]',
            '[data-testid*="reaction"]',
            '[data-testid*="engagement"]',
            '[class*="pw-multi-vote"]',
            '[data-dd-action-name]',
            '[class*="pw-responses"]',
            '[class*="postActions"]',
            '[class*="buttonSet"]',
            '[class*="vote-arrows"]',
            '[class*="upvote"]',
            '[class*="downvote"]',
            '[class*="score"]',
            '[data-testid*="tweet"]',
            '[data-testid*="retweet"]',
            '[data-testid*="favorite"]',
            '.speechify-ignore',
            '.immersive-translate-target',
            '[data-immersive-translate-walked]',
            '[id*="gtm"]', '[id*="ga-"]', '[id*="google"]', '[id="tag-manager"]',
            '[data-gtm-id]', '[data-ga-id]', '[data-analytics]', '[data-tracking]',
            'noscript[class*="gtm"]', 'iframe[src*="googletagmanager"]'
        ]

    def generate_enhanced_removal_selectors(self, site_pattern: SitePattern) -> List[str]:
        selectors = []
        patterns = self.exclusion_patterns

        for pattern_list in patterns.values():
            for pattern in pattern_list:
                selectors.extend([
                    pattern,
                    f'.{pattern}',
                    f'#{pattern}',
                    f'[class*="{pattern}"]',
                    f'[id*="{pattern}"]'
                ])

        selectors.extend(self._get_enhanced_css_selectors())
        
        if site_pattern in self.site_specific_rules:
            site_rules = self.site_specific_rules[site_pattern]
            if "remove_selectors" in site_rules:
                selectors.extend(site_rules["remove_selectors"])

        selectors.extend([
            "script", "style", "noscript", "iframe", "embed",
            "object", "video", "audio", "canvas", "svg", "map", "area",
            "iframe[id*='tag-manager']", "iframe[id*='gtm']", "iframe[id*='google']",
            "iframe[src*='googletagmanager']", "iframe[src*='gtm']",
            "noscript", "noscript[id*='gtm']", "noscript[class*='gtm']"
        ])
        
        script_sources = self._get_script_source_filters()
        for source in script_sources:
            selectors.extend([
                f'script[src*="{source}"]',
                f'iframe[src*="{source}"]'
            ])

        return selectors

    def _load_content_selectors(self) -> Dict[str, int]:
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
        return {
            SitePattern.E_LEARNING: {
                "preserve_selectors": [
                    ".training-module", ".lesson-content", ".chapter",
                    ".exercise", ".lab-description", ".instructions",
                    ".module-content", ".tutorial-content"
                ],
                "remove_selectors": [
                    ".vpn-switch-card", ".instance-start", ".target-system",
                    ".download-vpn", ".spawn-target", ".terminal", ".vm-controls",
                    ".sidebar", ".table-of-contents", ".navigation",
                    ".cheat-sheet", ".resources", ".hints",
                    ".tts-widget", ".enterprise-tts-widget",
                ],
                "content_indicators": [
                    "lab", "exercise", "lesson", "chapter", "module",
                    "tutorial", "guide", "instructions", "description",
                ],
            },
            SitePattern.DOCUMENTATION: {
                "preserve_selectors": [
                    ".docs-content", ".documentation", ".guide",
                    ".tutorial", ".manual", ".reference",
                ],
                "remove_selectors": [
                    ".docs-nav", ".api-nav", ".version-selector",
                    ".edit-page", ".github-link", ".search",
                ],
                "content_indicators": [
                    "documentation", "docs", "guide", "tutorial",
                    "manual", "reference", "api",
                ],
            },
            SitePattern.BLOG: {
                "preserve_selectors": [".post", ".blog-post", ".article", ".entry"],
                "remove_selectors": [
                    ".blog-sidebar", ".widget", ".archive",
                    ".tag-cloud", ".recent-posts", ".author-box",
                ],
            },
            SitePattern.NEWS: {
                "preserve_selectors": [".story", ".article", ".news-content"],
                "remove_selectors": [
                    ".breaking-news", ".trending", ".most-read",
                    ".newsletter-signup", ".subscription",
                ],
            },
            SitePattern.GENERIC: {},
            SitePattern.E_COMMERCE: {},
            SitePattern.FORUM: {},
            SitePattern.SOCIAL: {},
        }

    def _load_tts_optimization_rules(self) -> Dict[str, Any]:
        return {
            "remove_phrases": [
                "click here",
                "read more",
                "continue reading",
                "skip to content",
                "jump to navigation",
                "print this page",
                "email this article",
                "share on facebook",
                "tweet this",
                "subscribe to newsletter",
                "follow us on",
                "accept cookies",
                "cookie policy",
                "privacy policy",
                "terms of service",
                "play",
                "pause",
                "stop",
                "read page",
                "volume",
                "speed",
                "backend connection",
                "reading progress",
                "gtm.start",
                "dataLayer",
                "gtm.js",
                "gtm_auth",
                "gtm_preview",
                "google-analytics",
                "ga.js",
                "analytics.js",
                "ad by google",
                "advertisement",
                "sponsored content",
                "tracking pixel",
                "conversion tracking",
                "retargeting",
                "facebook pixel",
                "linkedin insight tag",
                "twitter conversion",
                "this site requires javascript",
                "requires javascript",
                "This site requires JavaScript",
            ],
            "remove_patterns": [
                r'Click\s+here\s+to\s+\w+',
                r'Follow\s+us\s+on\s+\w+',
                r'Subscribe\s+to\s+our\s+\w+',
                r'Download\s+our\s+\w+\s+app',
                r'Join\s+our\s+\w+\s+community',
                r'Sign\s+up\s+for\s+\w+',
                r'Get\s+\w+\s+updates',
                r'Enable\s+\w+\s+notifications',
                r'00:\d\d',
                r'▶️|⏸️|⏹️|📄|🔊|⏱️|📶',
                r'gtm\.start.*?new\s+Date.*?getTime',
                r'window\[.*?\].*?dataLayer',
                r'GTM-[A-Z0-9]+',
                r'ga\(["\'].*?["\'],.*?\)',
                r'gtag\(["\'].*?["\'],.*?\)',
                r'This\s+site\s+uses\s+cookies',
                r'Accept\s+(all\s+)?cookies',
                r'We\s+use\s+cookies\s+to',
                r'<iframe[^>]*>.*?</iframe>',
                r'<noscript[^>]*>.*?</noscript>',
                r'<script[^>]*>.*?</script>',
                r'<style[^>]*>.*?</style>',
                r'iframe\s+src=["\']?[^"\'>\s]+["\']?[^>]*>',
                r'iframe\s+src=.*?(?=\s|$)',
                r'This\s+site\s+requires\s+JavaScript',
                r'iframe\s+src="https?://www\.googletagmanager\.com/ns\.html\?id=GTM-\w+(&\w+=[^&]+)*"[^>]*></iframe>',
                r'</iframe><div[^>]*>This site requires JavaScript.</div>',
                r'</iframe>',
                r'<div style="text-align:center;margin:\d+px;background-color:#fff">This site requires JavaScript.</div>',
            ],
            "preserve_elements": [
                ""
                "", "h2", "h3", "h4", "h5", "h6",
                "p", "div", "span", "blockquote", "code", "pre",
                "ul", "ol", "li", "strong", "em", "b", "i",
            ],
            "text_processing": {
                "min_paragraph_length": 20,
                "max_paragraph_length": 5000,
                "min_sentence_length": 10,
                "remove_single_words": True,
                "normalize_whitespace": True,
            },
        }

    async def _remove_unwanted_elements(self, page, removal_selectors: List[str]) -> None:
        try:
            await page.evaluate('''
                () => {
                    const selectors = %s;
                    selectors.forEach(sel => {
                        document.querySelectorAll(sel).forEach(el => {
                            if (el.parentNode) el.parentNode.removeChild(el);
                        });
                    });
                }
            ''' % json.dumps(removal_selectors))
        except Exception as e:
            logger.error(f"Error removing unwanted elements: {e}")

    async def _optimize_content_for_tts(self, page) -> None:
        try:
            await page.evaluate('''
                () => {
                    document.querySelectorAll('iframe, noscript, script, style').forEach(el => {
                        if (el.parentNode) el.parentNode.removeChild(el);
                    });
                    function normalizeWhitespace(node) {
                        if (node.nodeType === Node.TEXT_NODE) {
                            node.textContent = node.textContent.replace(/\\s+/g, ' ').trim();
                        } else {
                            for (let child of node.childNodes) {
                                normalizeWhitespace(child);
                            }
                        }
                    }
                    normalizeWhitespace(document.body);
                }
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
        normalized = text
        
        normalized = re.sub(r'<iframe[^>]*>.*?</iframe>', '', normalized, flags=re.IGNORECASE | re.DOTALL)
        normalized = re.sub(r'iframe\s+src=["\']?[^"\'>\s]+["\']?[^>]*>', '', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'iframe\s+src=.*?(?=\s|$)', '', normalized, flags=re.IGNORECASE)
        
        normalized = re.sub(r'<noscript[^>]*>.*?</noscript>', '', normalized, flags=re.IGNORECASE | re.DOTALL)
        normalized = re.sub(r'<script[^>]*>.*?</script>', '', normalized, flags=re.IGNORECASE | re.DOTALL)
        normalized = re.sub(r'<style[^>]*>.*?</style>', '', normalized, flags=re.IGNORECASE | re.DOTALL)
        
        normalized = re.sub(r'iframe\s+src="https://www\.googletagmanager\.com[^"]*"[^>]*>', '', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'GTM-[A-Z0-9]+[^>]*>', '', normalized, flags=re.IGNORECASE)
        
        for phrase in self.tts_optimization_rules["remove_phrases"]:
            normalized = normalized.replace(phrase, '')
        
        for pattern in self.tts_optimization_rules["remove_patterns"]:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE | re.DOTALL)
        
        if self.tts_optimization_rules["text_processing"]["normalize_whitespace"]:
            normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized

    async def _extract_filtered_text(self, page) -> str:
        try:
            text = await page.evaluate('''
                () => {
                    const selectors = ['article', 'main', '[role="main"]', '.content', '.post-content', '.entry-content', '.article-content', 'section', 'p'];
                    let text = '';
                    selectors.forEach(selector => {
                        document.querySelectorAll(selector).forEach(el => {
                            if (el.innerText && 
                                !el.closest('.tts-widget, .enterprise-tts-widget') &&
                                !el.closest('.tts-ignore') &&
                                !el.classList.contains('tts-ignore')) {
                                const textContent = el.innerText;
                                if (!textContent.includes('iframe src=') && 
                                    !textContent.includes('googletagmanager') &&
                                    !textContent.includes('GTM-') &&
                                    !textContent.includes('This site requires JavaScript') &&
                                    !textContent.includes('gtm_auth') &&
                                    !textContent.includes('gtm_preview') &&
                                    !textContent.includes('tag-manager')) {
                                    text += textContent + ' ';
                                }
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
            if not text or len(text.strip()) < 10:
                return 0.0
            
            # Base score starts higher
            score = 0.3
            text_len = len(text.strip())
            
            # Text length scoring (more generous)
            if text_len > 1000:  # Long content (articles)
                score += 0.4
            elif text_len > 200:  # Medium content
                score += 0.3
            elif text_len > 50:   # Short content
                score += 0.1
            elif text_len < 20:  # Very short content
                score -= 0.2
                
            # HTML tag scoring
            tag_name = element_info.get("tag_name", "").lower()
            if tag_name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                score += 0.3  # Strong bonus for headings
            elif tag_name in ["article", "main", "section"]:
                score += 0.2
            elif tag_name in ["p", "div"]:
                score += 0.1
                
            # VISUAL LAYOUT SCORING - This is the key enhancement!
            # Use visual positioning to determine content importance
            x_pos = element_info.get("x_position_percent", 50)
            y_pos = element_info.get("y_position_percent", 50)
            width_pct = element_info.get("width_percent", 50)
            font_size = element_info.get("font_size", 16)
            
            # Center column content gets major bonus
            if element_info.get("is_center_column") == 1.0:
                score += 0.4
                
            # Main content area gets bonus
            if element_info.get("is_main_content_area") == 1.0:
                score += 0.3
                
            # Large font gets bonus (titles, headings)
            if font_size > 24:
                score += 0.2
            elif font_size > 18:
                score += 0.1
                
            # Sidebar content gets penalty
            if element_info.get("is_right_sidebar") == 1.0 or element_info.get("is_left_sidebar") == 1.0:
                score -= 0.4
                
            # Footer content gets major penalty
            if element_info.get("is_footer_area") == 1.0:
                score -= 0.5
                
            # Header area - depends on content
            if element_info.get("is_header_area") == 1.0:
                if text_len > 500:  # Main article in header
                    score += 0.2
                else:  # Navigation in header
                    score -= 0.3
            
            # Class/ID indicators
            class_id = f"{element_info.get('class_name', '')} {element_info.get('id', '')}".lower()
            positive_indicators = ["content", "article", "post", "story", "main", "text"]
            for indicator in positive_indicators:
                if indicator in class_id:
                    score += 0.1
                    break
                    
            negative_indicators = ["nav", "menu", "sidebar", "footer", "header", "ad", "related", "promo"]
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
            
            # Sentence quality
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
                        'section', '.section',
                        'h1', 'h2', 'h3', 'h4', 'h5', 'h6'  // Include headings for names/titles
                    ];
                    const areas = [];
                    
                    // Get viewport dimensions for visual positioning
                    const viewportWidth = window.innerWidth;
                    const viewportHeight = window.innerHeight;
                    
                    contentSelectors.forEach(selector => {
                        try {
                            const elements = document.querySelectorAll(selector);
                            elements.forEach((el, index) => {
                                const text = el.innerText || '';
                                const isHeading = el.tagName.toLowerCase().match(/^h[1-6]$/);
                                // Lower threshold for headings since they're often short
                                const minLength = isHeading ? 10 : 50;
                                if (text.length > minLength) {
                                    // Get visual positioning
                                    const rect = el.getBoundingClientRect();
                                    const style = window.getComputedStyle(el);
                                    
                                    areas.push({
                                        selector: selector,
                                        index: index,
                                        text: text.substring(0, 5000),
                                        textLength: text.length,
                                        tagName: el.tagName.toLowerCase(),
                                        className: el.className || '',
                                        id: el.id || '',
                                        hasHeadings: el.querySelectorAll('h1, h2, h3, h4, h5, h6').length,
                                        hasParagraphs: el.querySelectorAll('p').length,
                                        
                                        // Visual positioning features
                                        x: rect.left,
                                        y: rect.top,
                                        width: rect.width,
                                        height: rect.height,
                                        
                                        // Relative positioning (as percentages)
                                        x_percent: (rect.left / viewportWidth) * 100,
                                        y_percent: (rect.top / viewportHeight) * 100,
                                        width_percent: (rect.width / viewportWidth) * 100,
                                        height_percent: (rect.height / viewportHeight) * 100,
                                        
                                        // CSS properties
                                        fontSize: parseFloat(style.fontSize) || 16,
                                        fontWeight: style.fontWeight,
                                        
                                        // Viewport dimensions for context
                                        viewportWidth: viewportWidth,
                                        viewportHeight: viewportHeight
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
                    "id": area["id"],
                    # Add visual positioning features for scoring
                    "x_position_percent": area.get("x_percent", 0),
                    "y_position_percent": area.get("y_percent", 0),
                    "width_percent": area.get("width_percent", 0),
                    "font_size": area.get("fontSize", 16),
                    "is_center_column": 1.0 if area.get("x_percent", 0) >= 20 and area.get("x_percent", 0) <= 80 and area.get("width_percent", 0) > 30 else 0.0,
                    "is_left_sidebar": 1.0 if area.get("x_percent", 0) < 25 and area.get("width_percent", 0) < 30 else 0.0,
                    "is_right_sidebar": 1.0 if area.get("x_percent", 0) > 75 and area.get("width_percent", 0) < 30 else 0.0,
                    "is_header_area": 1.0 if area.get("y_percent", 0) < 15 else 0.0,
                    "is_footer_area": 1.0 if area.get("y_percent", 0) > 85 else 0.0,
                    "is_main_content_area": 1.0 if area.get("y_percent", 0) >= 15 and area.get("y_percent", 0) <= 85 and area.get("x_percent", 0) >= 20 and area.get("x_percent", 0) <= 80 else 0.0,
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