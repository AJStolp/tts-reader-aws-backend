#!/usr/bin/env python3
"""
Demo labeling for Medium article
"""

import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def extract_medium_content():
    """Extract content from Medium article for labeling demo"""
    
    test_url = "https://medium.com/blog/32-of-our-favorite-medium-stories-of-2023-1fb10ca34cd8"
    
    print(f"🧪 EXTRACTING CONTENT FOR LABELING")
    print(f"📋 URL: {test_url}")
    print("=" * 80)
    
    try:
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)  # Show browser
            page = await browser.new_page()
            
            # Set user agent to avoid bot detection
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            
            print("🌐 Loading page...")
            await page.goto(test_url, wait_until='networkidle', timeout=30000)
            
            # Wait a bit for any dynamic content
            await page.wait_for_timeout(3000)
            
            # Check if we hit a paywall or security check
            page_text = await page.evaluate('() => document.body.innerText')
            if 'verify' in page_text.lower() or 'security' in page_text.lower():
                print("❌ Hit security check - trying without headers")
                await page.goto(test_url, wait_until='domcontentloaded')
                await page.wait_for_timeout(5000)
            
            # Extract content with visual positioning
            content_areas = await page.evaluate('''
                () => {
                    const contentSelectors = [
                        'article', 'main', '[role="main"]',
                        '.content', '.post-content', '.entry-content',
                        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                        'p', 'div[class*="paragraph"]',
                        '[data-testid="storyTitle"]',
                        '[data-testid="storyContent"]'
                    ];
                    const areas = [];
                    
                    const viewportWidth = window.innerWidth;
                    const viewportHeight = window.innerHeight;
                    
                    contentSelectors.forEach(selector => {
                        try {
                            const elements = document.querySelectorAll(selector);
                            elements.forEach((el, index) => {
                                const text = el.innerText || '';
                                if (text.length > 20) {  // Lower threshold for Medium
                                    const rect = el.getBoundingClientRect();
                                    const style = window.getComputedStyle(el);
                                    
                                    areas.push({
                                        text: text.substring(0, 1000),
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
                print("❌ No content found - might be blocked")
                return
                
            print(f"📊 Found {len(content_areas)} content blocks")
            print("\n🔍 CONTENT FOR LABELING:")
            print("-" * 80)
            
            for i, area in enumerate(content_areas[:15]):  # Show first 15
                x_pos = area.get('x_percent', 0)
                y_pos = area.get('y_percent', 0) 
                width_pct = area.get('width_percent', 0)
                font_size = area.get('fontSize', 16)
                text_len = area.get('textLength', 0)
                
                # Determine layout zone
                if x_pos >= 20 and x_pos <= 80 and width_pct > 30:
                    zone = "CENTER"
                    recommendation = "✅ LIKELY GOOD" if text_len > 300 or font_size > 20 else "⭐ MAYBE"
                elif x_pos < 25:
                    zone = "LEFT_SIDEBAR"
                    recommendation = "❌ LIKELY BAD"
                elif x_pos > 75:
                    zone = "RIGHT_SIDEBAR" 
                    recommendation = "❌ LIKELY BAD"
                elif y_pos < 15:
                    zone = "HEADER"
                    recommendation = "⭐ MAYBE"
                elif y_pos > 85:
                    zone = "FOOTER"
                    recommendation = "❌ LIKELY BAD"
                else:
                    zone = "MIDDLE"
                    recommendation = "⭐ MAYBE"
                    
                print(f"\n📍 BLOCK #{i+1}")
                print(f"   🎯 ZONE: {zone} | x={x_pos:.0f}%, y={y_pos:.0f}%, w={width_pct:.0f}%")
                print(f"   📏 {text_len} chars | {font_size}px | {area.get('tagName', 'unknown')}")
                print(f"   🤖 {recommendation}")
                print(f"   📝 \"{area.get('text', '')[:120]}...\"")
                print(f"   👤 Would you label this as: [✅ include / ❌ exclude]?")
            
            print(f"\n📋 LABELING WORKFLOW:")
            print(f"   1. Review each block above")
            print(f"   2. Decide: ✅ good for TTS / ❌ skip for TTS")
            print(f"   3. Model learns your preferences")
            print(f"   4. Future articles auto-filtered better")
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(extract_medium_content())