#!/usr/bin/env python3
"""
Human Labeling Interface for Content Quality Training
Allows manual review and labeling of extracted content blocks
"""

import asyncio
import json
import sys
import os
from typing import List, Dict, Any
import logging

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from textract_processor.ml_training_data_collector import TrainingDataCollector
from textract_processor.content_classifier_model import ContentClassifierTrainer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HumanLabelingInterface:
    def __init__(self):
        self.labeled_data = []
        self.current_url = None
        
    def display_content_for_labeling(self, content_areas: List[Dict[str, Any]], url: str):
        """Display content blocks for human review and labeling"""
        print("\n" + "="*100)
        print(f"🌐 CONTENT LABELING FOR: {url}")
        print("="*100)
        print("📋 Review each content block and decide if it should be included in TTS")
        print("   ✅ = Include (good content for reading aloud)")
        print("   ❌ = Exclude (navigation, ads, sidebar content)")
        print("   ⏭️  = Skip (review later)")
        print("-"*100)
        
        labeled_areas = []
        
        for i, area in enumerate(content_areas):
            # Show visual context
            x_pos = area.get('x_percent', 0)
            y_pos = area.get('y_percent', 0) 
            width_pct = area.get('width_percent', 0)
            font_size = area.get('fontSize', 16)
            
            # Determine layout zone
            if x_pos >= 20 and x_pos <= 80 and width_pct > 30:
                zone = "CENTER"
            elif x_pos < 25 and width_pct < 30:
                zone = "LEFT_SIDEBAR" 
            elif x_pos > 75 and width_pct < 30:
                zone = "RIGHT_SIDEBAR"
            elif y_pos < 15:
                zone = "HEADER"
            elif y_pos > 85:
                zone = "FOOTER"
            else:
                zone = "OTHER"
                
            print(f"\n📍 BLOCK #{i+1}/{{len(content_areas)}}")
            print(f"   🎯 VISUAL: x={x_pos:.0f}%, y={y_pos:.0f}%, width={width_pct:.0f}%, zone={zone}")
            print(f"   📏 SIZE: {area.get('textLength', 0)} chars, {font_size}px font, {area.get('tagName', 'unknown')} tag")
            print(f"   📝 TEXT: {area.get('text', '')[:200]}...")
            
            # Get human label
            while True:
                choice = input(f"\n   👤 Include in TTS? [✅ y/❌ n/⏭️ s/🔍 f=full text]: ").lower().strip()
                
                if choice in ['y', 'yes', '✅']:
                    label = 1.0  # High quality
                    print(f"   ✅ LABELED: Include")
                    break
                elif choice in ['n', 'no', '❌']:
                    label = 0.0  # Low quality  
                    print(f"   ❌ LABELED: Exclude")
                    break
                elif choice in ['s', 'skip', '⏭️']:
                    continue  # Skip this one for now
                elif choice in ['f', 'full']:
                    print(f"\n   📖 FULL TEXT:\n{area.get('text', '')}\n")
                    continue
                else:
                    print("   ⚠️  Please enter: y (include), n (exclude), s (skip), or f (full text)")
                    continue
            
            # Store the labeled example
            labeled_example = {
                'features': self._extract_features_from_area(area, url),
                'label': label,
                'url': url,
                'text_preview': area.get('text', '')[:200],
                'human_labeled': True,
                'visual_zone': zone
            }
            
            labeled_areas.append(labeled_example)
            
        return labeled_areas
    
    def _extract_features_from_area(self, area: Dict[str, Any], url: str) -> Dict[str, float]:
        """Extract numerical features matching the ML model"""
        text = area.get('text', '')
        tag_name = area.get('tagName', '').lower()
        class_name = area.get('className', '').lower()
        element_id = area.get('id', '').lower()
        
        # Get visual positioning data
        x_percent = area.get('x_percent', 0)
        y_percent = area.get('y_percent', 0)
        width_percent = area.get('width_percent', 0)
        font_size = area.get('fontSize', 16)
        
        features = {
            # Text-based features
            'text_length': len(text),
            'word_count': len(text.split()),
            'avg_word_length': sum(len(word) for word in text.split()) / max(len(text.split()), 1),
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
            
            # VISUAL LAYOUT FEATURES
            'x_position_percent': x_percent,
            'y_position_percent': y_percent,
            'width_percent': width_percent,
            
            # Layout zones
            'is_center_column': 1.0 if 20 <= x_percent <= 80 and width_percent > 30 else 0.0,
            'is_left_sidebar': 1.0 if x_percent < 25 and width_percent < 30 else 0.0,
            'is_right_sidebar': 1.0 if x_percent > 75 and width_percent < 30 else 0.0,
            'is_header_area': 1.0 if y_percent < 15 else 0.0,
            'is_footer_area': 1.0 if y_percent > 85 else 0.0,
            'is_main_content_area': 1.0 if 15 <= y_percent <= 85 and 20 <= x_percent <= 80 else 0.0,
            
            # Size indicators
            'is_large_element': 1.0 if width_percent > 50 and area.get('height_percent', 0) > 20 else 0.0,
            'is_small_element': 1.0 if width_percent < 20 or area.get('height_percent', 0) < 5 else 0.0,
            
            # Font size
            'font_size': font_size,
            'is_large_font': 1.0 if font_size > 18 else 0.0,
            'is_small_font': 1.0 if font_size < 14 else 0.0,
            
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
    
    async def label_site(self, url: str):
        """Collect and label content from a single site"""
        print(f"\n🚀 Starting content collection and labeling for: {url}")
        
        collector = TrainingDataCollector()
        
        try:
            # Extract content with visual positioning
            content_areas = await collector.extract_visual_content_areas_from_url(url)
            
            if not content_areas:
                print(f"❌ No content found on {url}")
                return []
            
            print(f"📊 Found {len(content_areas)} content blocks to review")
            
            # Human labeling interface
            labeled_examples = self.display_content_for_labeling(content_areas, url)
            
            # Save labeled data
            self.labeled_data.extend(labeled_examples)
            
            timestamp = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"human_labeled_data_{timestamp}.json"
            
            with open(filename, 'w') as f:
                json.dump(self.labeled_data, f, indent=2)
            
            print(f"\n✅ Saved {len(labeled_examples)} labeled examples to {filename}")
            return labeled_examples
            
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            return []
    
    def train_on_labeled_data(self, data_file: str = None):
        """Train the model on human-labeled data"""
        if data_file is None:
            # Find the most recent labeled data file
            import glob
            files = glob.glob("human_labeled_data_*.json")
            if not files:
                print("❌ No labeled data files found")
                return
            data_file = max(files)  # Most recent
        
        print(f"\n🤖 Training model on labeled data: {data_file}")
        
        trainer = ContentClassifierTrainer()
        
        try:
            train_loader, val_loader = trainer.prepare_data(data_file)
            trainer.train(train_loader, val_loader, epochs=50)
            
            print("✅ Model training completed with human-labeled data!")
            
        except Exception as e:
            logger.error(f"Training failed: {e}")

# Add method to TrainingDataCollector for single URL processing
async def extract_visual_content_areas_from_url(self, url: str):
    """Extract content areas from a single URL with visual positioning"""
    from playwright.async_api import async_playwright
    from .content_filters import tts_content_filter
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            await page.goto(url, wait_until='networkidle', timeout=15000)
            
            # Take screenshot
            screenshot_path = f"screenshots/labeling_{url.split('/')[-1]}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            
            # Extract content areas with visual positioning
            content_areas = await self.extract_visual_content_areas(page)
            
            await browser.close()
            return content_areas
            
        except Exception as e:
            logger.error(f"Error extracting from {url}: {e}")
            await browser.close()
            return []

# Monkey patch the method
TrainingDataCollector.extract_visual_content_areas_from_url = extract_visual_content_areas_from_url

async def main():
    """Interactive labeling session"""
    interface = HumanLabelingInterface()
    
    print("🎯 HUMAN CONTENT LABELING SYSTEM")
    print("="*50)
    print("This tool helps train the model by showing you content blocks")
    print("and letting you decide what should be read aloud by TTS.")
    print()
    
    while True:
        print("\n📋 Options:")
        print("  1. Label content from a URL")
        print("  2. Train model on labeled data")
        print("  3. Exit")
        
        choice = input("\n👤 Choose an option (1-3): ").strip()
        
        if choice == '1':
            url = input("🌐 Enter URL to analyze: ").strip()
            if url:
                await interface.label_site(url)
        elif choice == '2':
            interface.train_on_labeled_data()
        elif choice == '3':
            print("👋 Goodbye!")
            break
        else:
            print("⚠️  Please enter 1, 2, or 3")

if __name__ == "__main__":
    asyncio.run(main())