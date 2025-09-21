#!/usr/bin/env python3
"""
Quick test of the labeling system with the blog post
"""

import asyncio
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from human_labeling_interface import HumanLabelingInterface

async def test_blog_labeling():
    """Test labeling on the developer blog post"""
    
    interface = HumanLabelingInterface()
    
    # Test URL - the developer blog we know well
    test_url = "https://spin.atomicobject.com/keep-a-developer-log/?ref=dailydev"
    
    print(f"🧪 TESTING LABELING SYSTEM")
    print(f"📋 URL: {test_url}")
    print(f"🎯 Expected good content: Main article title + article body")
    print(f"❌ Expected bad content: Sidebar articles, footer, navigation")
    print()
    
    try:
        # Extract content (will show what we found)
        # Use the existing debug system to get content
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            await page.goto(test_url, wait_until='networkidle', timeout=15000)
            
            # Extract content with visual positioning (matching our debug system)
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
                                    const rect = el.getBoundingClientRect();
                                    const style = window.getComputedStyle(el);
                                    
                                    areas.push({
                                        text: text.substring(0, 2000),
                                        textLength: text.length,
                                        tagName: el.tagName.toLowerCase(),
                                        className: el.className || '',
                                        id: el.id || '',
                                        x_percent: (rect.left / viewportWidth) * 100,
                                        y_percent: (rect.top / viewportHeight) * 100,
                                        width_percent: (rect.width / viewportWidth) * 100,
                                        height_percent: (rect.height / viewportHeight) * 100,
                                        fontSize: parseFloat(style.fontSize) || 16,
                                    });
                                }
                            });
                        } catch (e) {}
                    });
                    return areas;
                }
            ''')
            
            await browser.close()
        
        print(f"📊 Found {len(content_areas)} content blocks")
        print("\n🔍 CONTENT BLOCKS SUMMARY:")
        print("-" * 80)
        
        for i, area in enumerate(content_areas):
            x_pos = area.get('x_percent', 0)
            y_pos = area.get('y_percent', 0)
            width_pct = area.get('width_percent', 0)
            font_size = area.get('fontSize', 16)
            text_len = area.get('textLength', 0)
            
            # Determine layout zone
            if x_pos >= 20 and x_pos <= 80 and width_pct > 30:
                zone = "CENTER"
                recommendation = "✅ LIKELY GOOD" if text_len > 500 or font_size > 24 else "⭐ MAYBE"
            elif x_pos < 25 and width_pct < 30:
                zone = "LEFT_SIDEBAR"
                recommendation = "❌ LIKELY BAD"
            elif x_pos > 75 and width_pct < 30:
                zone = "RIGHT_SIDEBAR" 
                recommendation = "❌ LIKELY BAD"
            elif y_pos < 15:
                zone = "HEADER"
                recommendation = "⭐ MAYBE" if text_len > 1000 else "❌ LIKELY BAD"
            elif y_pos > 85:
                zone = "FOOTER"
                recommendation = "❌ LIKELY BAD"
            else:
                zone = "OTHER"
                recommendation = "⭐ MAYBE"
            
            print(f"#{i+1:2d} | {zone:12s} | {text_len:4d} chars | {font_size:2.0f}px | {recommendation}")
            print(f"    📝 {area.get('text', '')[:80]}...")
            print()
        
        print("🎯 RECOMMENDATIONS FOR GOOD TTS CONTENT:")
        print("-" * 50)
        good_candidates = []
        
        for i, area in enumerate(content_areas):
            x_pos = area.get('x_percent', 0)
            text_len = area.get('textLength', 0)
            font_size = area.get('fontSize', 16)
            
            # Identify likely good content
            is_center = 20 <= x_pos <= 80
            is_substantial = text_len > 500
            is_title = font_size > 30
            
            if (is_center and is_substantial) or is_title:
                good_candidates.append((i+1, area))
                print(f"✅ Block #{i+1}: {area.get('text', '')[:100]}...")
        
        print(f"\n📈 SUMMARY:")
        print(f"   Total blocks: {len(content_areas)}")
        print(f"   Recommended for TTS: {len(good_candidates)}")
        print(f"   Screenshot saved: screenshots/labeling_{test_url.split('/')[-1]}.png")
        
        return content_areas
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

if __name__ == "__main__":
    asyncio.run(test_blog_labeling())