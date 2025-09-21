import asyncio
import json
import logging
from typing import List, Dict, Any, Tuple
from playwright.async_api import async_playwright
from .content_filters import tts_content_filter
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class TrainingDataCollector:
    def __init__(self):
        self.training_data = []
        
    async def collect_training_data_from_urls(self, urls: List[str], max_pages: int = 50) -> List[Dict[str, Any]]:
        """Collect training data by visiting URLs and extracting features + labels"""
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            for i, url in enumerate(urls[:max_pages]):
                if i % 10 == 0:
                    logger.info(f"Processing URL {i+1}/{min(len(urls), max_pages)}: {url}")
                
                try:
                    page = await browser.new_page()
                    await page.goto(url, wait_until='networkidle', timeout=10000)
                    
                    # Take screenshot for visual analysis
                    screenshot_path = f"screenshots/page_{i}.png"
                    await page.screenshot(path=screenshot_path, full_page=True)
                    logger.info(f"Screenshot saved: {screenshot_path}")
                    
                    # Extract all content blocks and their features (with visual positioning)
                    content_areas = await self.extract_visual_content_areas(page)
                    
                    for area in content_areas:
                        # Extract features for this content block
                        features = self._extract_features_from_area(area, url)
                        
                        # Use existing scoring as label (0-1 score)
                        label = area.get('tts_score', 0.0)
                        
                        training_example = {
                            'features': features,
                            'label': label,
                            'url': url,
                            'text_preview': area.get('text', '')[:200]
                        }
                        
                        self.training_data.append(training_example)
                    
                    await page.close()
                    
                except Exception as e:
                    logger.error(f"Error processing {url}: {e}")
                    continue
            
            await browser.close()
        
        logger.info(f"Collected {len(self.training_data)} training examples")
        return self.training_data
    
    def _extract_features_from_area(self, area: Dict[str, Any], url: str) -> Dict[str, float]:
        """Extract numerical features from a content area for ML training"""
        
        text = area.get('text', '')
        tag_name = area.get('tagName', '').lower()
        class_name = area.get('className', '').lower()
        element_id = area.get('id', '').lower()
        
        # Get visual positioning data
        viewport_width = area.get('viewportWidth', 1200)
        viewport_height = area.get('viewportHeight', 800)
        x_percent = area.get('x_percent', 0)
        y_percent = area.get('y_percent', 0)
        width_percent = area.get('width_percent', 0)
        center_x = area.get('center_x', 0)
        
        features = {
            # Text-based features
            'text_length': len(text),
            'word_count': len(text.split()),
            'avg_word_length': np.mean([len(word) for word in text.split()]) if text.split() else 0,
            'sentence_count': len([s for s in text.split('.') if s.strip()]),
            'paragraph_count': area.get('hasParagraphs', 0),
            'heading_count': area.get('hasHeadings', 0),
            
            # HTML structure features
            'is_article': 1.0 if tag_name == 'article' else 0.0,
            'is_main': 1.0 if tag_name == 'main' else 0.0,
            'is_section': 1.0 if tag_name == 'section' else 0.0,
            'is_div': 1.0 if tag_name == 'div' else 0.0,
            'is_heading': 1.0 if tag_name.startswith('h') and len(tag_name) == 2 else 0.0,
            
            # Class/ID indicators
            'has_content_class': 1.0 if 'content' in class_name else 0.0,
            'has_article_class': 1.0 if 'article' in class_name else 0.0,
            'has_post_class': 1.0 if 'post' in class_name else 0.0,
            'has_main_class': 1.0 if 'main' in class_name else 0.0,
            'has_navigation_class': 1.0 if any(nav in class_name for nav in ['nav', 'menu', 'sidebar']) else 0.0,
            'has_ad_class': 1.0 if any(ad in class_name for ad in ['ad', 'advertisement', 'sponsor']) else 0.0,
            
            # Content quality indicators
            'link_density': self._calculate_link_density(text),
            'uppercase_ratio': sum(1 for c in text if c.isupper()) / max(len(text), 1),
            'digit_ratio': sum(1 for c in text if c.isdigit()) / max(len(text), 1),
            'special_char_ratio': sum(1 for c in text if not c.isalnum() and not c.isspace()) / max(len(text), 1),
            
            # VISUAL LAYOUT FEATURES - This is the key addition!
            'x_position_percent': x_percent,
            'y_position_percent': y_percent,
            'width_percent': width_percent,
            
            # Layout zones (like how you visually categorize)
            'is_center_column': 1.0 if 20 <= x_percent <= 80 and width_percent > 30 else 0.0,
            'is_left_sidebar': 1.0 if x_percent < 25 and width_percent < 30 else 0.0,
            'is_right_sidebar': 1.0 if x_percent > 75 and width_percent < 30 else 0.0,
            'is_header_area': 1.0 if y_percent < 15 else 0.0,
            'is_footer_area': 1.0 if y_percent > 85 else 0.0,
            'is_main_content_area': 1.0 if 15 <= y_percent <= 85 and 20 <= x_percent <= 80 else 0.0,
            
            # Size indicators
            'is_large_element': 1.0 if width_percent > 50 and area.get('height_percent', 0) > 20 else 0.0,
            'is_small_element': 1.0 if width_percent < 20 or area.get('height_percent', 0) < 5 else 0.0,
            
            # Font size (bigger = more important)
            'font_size': area.get('fontSize', 16),
            'is_large_font': 1.0 if area.get('fontSize', 16) > 18 else 0.0,
            'is_small_font': 1.0 if area.get('fontSize', 16) < 14 else 0.0,
            
            # URL-based features  
            'is_blog': 1.0 if 'blog' in url else 0.0,
            'is_docs': 1.0 if any(doc in url for doc in ['docs', 'documentation', 'guide']) else 0.0,
            'is_news': 1.0 if 'news' in url else 0.0,
        }
        
        return features
    
    def _calculate_link_density(self, text: str) -> float:
        """Calculate ratio of link text to total text"""
        import re
        links = re.findall(r'<a[^>]*>([^<]*)</a>', text, re.IGNORECASE)
        link_chars = sum(len(link) for link in links)
        return link_chars / max(len(text), 1)
    
    def save_training_data(self, filepath: str):
        """Save collected training data to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(self.training_data, f, indent=2)
        logger.info(f"Saved {len(self.training_data)} training examples to {filepath}")
    
    def load_training_data(self, filepath: str):
        """Load training data from JSON file"""
        with open(filepath, 'r') as f:
            self.training_data = json.load(f)
        logger.info(f"Loaded {len(self.training_data)} training examples from {filepath}")
    
    def get_features_and_labels(self) -> Tuple[np.ndarray, np.ndarray]:
        """Convert training data to numpy arrays for ML training"""
        if not self.training_data:
            raise ValueError("No training data collected")
        
        # Extract feature names from first example
        feature_names = list(self.training_data[0]['features'].keys())
        
        # Create feature matrix
        features = []
        labels = []
        
        for example in self.training_data:
            feature_vector = [example['features'][name] for name in feature_names]
            features.append(feature_vector)
            labels.append(example['label'])
        
        return np.array(features), np.array(labels), feature_names
    
    async def extract_visual_content_areas(self, page) -> List[Dict[str, Any]]:
        """Extract content areas with visual positioning data"""
        try:
            content_areas = await page.evaluate('''
                () => {
                    const contentSelectors = [
                        'article', 'main', '[role="main"]',
                        '.content', '.post-content', '.entry-content',
                        '.article-content', '.page-content', '.story-body',
                        'section', '.section',
                        'h1', 'h2', 'h3', 'h4', 'h5', 'h6'
                    ];
                    const areas = [];
                    
                    // Get viewport dimensions
                    const viewportWidth = window.innerWidth;
                    const viewportHeight = window.innerHeight;
                    
                    contentSelectors.forEach(selector => {
                        try {
                            const elements = document.querySelectorAll(selector);
                            elements.forEach((el, index) => {
                                const text = el.innerText || '';
                                const isHeading = el.tagName.toLowerCase().match(/^h[1-6]$/);
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
                                        right: rect.right,
                                        bottom: rect.bottom,
                                        
                                        // Relative positioning (as percentages)
                                        x_percent: (rect.left / viewportWidth) * 100,
                                        y_percent: (rect.top / viewportHeight) * 100,
                                        width_percent: (rect.width / viewportWidth) * 100,
                                        height_percent: (rect.height / viewportHeight) * 100,
                                        
                                        // Layout indicators
                                        center_x: rect.left + (rect.width / 2),
                                        center_y: rect.top + (rect.height / 2),
                                        
                                        // CSS properties that matter for layout
                                        fontSize: parseFloat(style.fontSize) || 16,
                                        fontWeight: style.fontWeight,
                                        display: style.display,
                                        position: style.position,
                                        zIndex: parseInt(style.zIndex) || 0,
                                        backgroundColor: style.backgroundColor,
                                        
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
            
            logger.info(f"Extracted {len(content_areas)} content areas with visual positioning")
            return content_areas
            
        except Exception as e:
            logger.error(f"Error extracting visual content areas: {e}")
            return []

# Example usage function
async def collect_sample_data():
    """Collect sample training data from common websites"""
    
    sample_urls = [
        "https://docs.python.org/3/tutorial/",
        "https://pytorch.org/tutorials/beginner/basics/quickstart_tutorial.html",
        "https://fastapi.tiangolo.com/tutorial/",
        "https://medium.com/@example/sample-article",
        "https://stackoverflow.com/questions/tagged/python",
        "https://github.com/pytorch/pytorch/blob/main/README.md",
        "https://news.ycombinator.com/",
        "https://www.reddit.com/r/MachineLearning/",
    ]
    
    collector = TrainingDataCollector()
    await collector.collect_training_data_from_urls(sample_urls, max_pages=20)
    collector.save_training_data('training_data.json')
    
    return collector

if __name__ == "__main__":
    asyncio.run(collect_sample_data())