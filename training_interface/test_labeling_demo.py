#!/usr/bin/env python3
"""
Demo of the labeling system - shows content blocks for review
"""

import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from human_labeling_interface import HumanLabelingInterface

async def demo_content_extraction():
    """Demo content extraction without interactive labeling"""
    
    interface = HumanLabelingInterface()
    
    # Test URL - try a few options
    test_urls = [
        "https://medium.com/blog/32-of-our-favorite-medium-stories-of-2023-1fb10ca34cd8",
        "https://spin.atomicobject.com/keep-a-developer-log/?ref=dailydev",
        "https://puppies.com/listings/7bc50525-6020-4a21-a941-de56fbea6dd8"
    ]
    
    for test_url in test_urls:
        print(f"\n🔍 TRYING: {test_url}")
        try:
    
    print(f"🧪 DEMO: Content extraction for labeling")
    print(f"📋 URL: {test_url}")
    print("🎯 This shows what content blocks would be presented for human labeling")
    print("=" * 80)
    
    try:
        # Extract content areas using Playwright directly
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            await page.goto(test_url, wait_until='networkidle', timeout=15000)
            
            # Extract content with visual positioning
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
        
        if not content_areas:
            print("❌ No content found")
            return
            
        print(f"📊 Found {len(content_areas)} content blocks to review")
        print("\n🔍 CONTENT BLOCKS FOR HUMAN REVIEW:")
        print("-" * 80)
        
        for i, area in enumerate(content_areas[:10]):  # Show first 10
            # Show visual context
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
                
            print(f"\n📍 BLOCK #{i+1}")
            print(f"   🎯 VISUAL: x={x_pos:.0f}%, y={y_pos:.0f}%, width={width_pct:.0f}%, zone={zone}")
            print(f"   📏 SIZE: {text_len} chars, {font_size}px font, {area.get('tagName', 'unknown')} tag")
            print(f"   🤖 RECOMMENDATION: {recommendation}")
            print(f"   📝 TEXT: {area.get('text', '')[:150]}...")
            print(f"   👤 USER WOULD CHOOSE: [✅ y/❌ n/⏭️ s/🔍 f]")
        
        print(f"\n📈 SUMMARY:")
        print(f"   • Total blocks found: {len(content_areas)}")
        print(f"   • Shown above: {min(10, len(content_areas))}")
        print(f"   • Each block would be reviewed by human")
        print(f"   • Choices train the ML model to learn preferences")
        
        print(f"\n🚀 TO START REAL LABELING:")
        print(f"   1. Run: python human_labeling_interface.py")
        print(f"   2. Choose option 1 (Label content from URL)")
        print(f"   3. Enter URL: {test_url}")
        print(f"   4. Review each block and label as include/exclude")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(demo_content_extraction())