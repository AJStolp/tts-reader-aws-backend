#!/usr/bin/env python3
"""
Visual Content Summary - Show exactly what the model detected
"""

import json

def create_content_summary():
    """Create a visual summary of detected content"""
    
    with open('debug_training_data.json', 'r') as f:
        data = json.load(f)
    
    print("🎯 VISUAL CONTENT ANALYSIS SUMMARY")
    print("=" * 80)
    print(f"Site: https://spin.atomicobject.com/keep-a-developer-log/")
    print(f"Total content blocks found: {len(data)}")
    print()
    
    # Group by layout zones
    center_content = []
    sidebar_content = []
    header_content = []
    footer_content = []
    other_content = []
    
    for item in data:
        features = item['features']
        text_preview = item['text_preview'][:80] + "..." if len(item['text_preview']) > 80 else item['text_preview']
        
        content_info = {
            'text': text_preview,
            'length': features['text_length'],
            'x_pos': features['x_position_percent'],
            'y_pos': features['y_position_percent'],
            'font_size': features['font_size'],
            'is_heading': features.get('is_heading', 0),
            'tag': 'heading' if features.get('is_heading', 0) else 'article' if features['is_article'] else 'main' if features['is_main'] else 'div'
        }
        
        if features['is_center_column']:
            center_content.append(content_info)
        elif features['is_right_sidebar'] or features['is_left_sidebar']:
            sidebar_content.append(content_info)
        elif features['is_header_area']:
            header_content.append(content_info)
        elif features['is_footer_area']:
            footer_content.append(content_info)
        else:
            other_content.append(content_info)
    
    print("🏠 HEADER AREA (Top of page)")
    print("-" * 40)
    for item in header_content:
        print(f"📍 Position: x={item['x_pos']:.0f}%, y={item['y_pos']:.0f}% | Font: {item['font_size']}px | {item['tag']}")
        print(f"   Text: {item['text']}")
        print(f"   Length: {item['length']} chars")
        print()
    
    print("📰 CENTER COLUMN (Main content area)")
    print("-" * 40)
    for item in center_content:
        priority = "🔥 HIGH" if item['length'] > 1000 or (item['is_heading'] and item['font_size'] > 30) else "⭐ MEDIUM"
        print(f"📍 Position: x={item['x_pos']:.0f}%, y={item['y_pos']:.0f}% | Font: {item['font_size']}px | {item['tag']} | {priority}")
        print(f"   Text: {item['text']}")
        print(f"   Length: {item['length']} chars")
        print()
    
    print("📋 SIDEBAR (Navigation/Related content)")
    print("-" * 40)
    for item in sidebar_content:
        print(f"📍 Position: x={item['x_pos']:.0f}%, y={item['y_pos']:.0f}% | Font: {item['font_size']}px | {item['tag']}")
        print(f"   Text: {item['text']}")
        print(f"   Length: {item['length']} chars")
        print()
    
    print("🦶 FOOTER AREA (Bottom promotional content)")
    print("-" * 40)
    for item in footer_content:
        print(f"📍 Position: x={item['x_pos']:.0f}%, y={item['y_pos']:.0f}% | Font: {item['font_size']}px | {item['tag']}")
        print(f"   Text: {item['text']}")
        print(f"   Length: {item['length']} chars")
        print()
    
    print("❓ OTHER/MIXED ZONES")
    print("-" * 40)
    for item in other_content:
        print(f"📍 Position: x={item['x_pos']:.0f}%, y={item['y_pos']:.0f}% | Font: {item['font_size']}px | {item['tag']}")
        print(f"   Text: {item['text']}")
        print(f"   Length: {item['length']} chars")
        print()

    # Recommendations
    print("🎯 RECOMMENDED CONTENT FOR TTS:")
    print("-" * 40)
    print("✅ INCLUDE:")
    for item in center_content:
        if item['length'] > 1000 or (item['is_heading'] and item['font_size'] > 30):
            print(f"   • {item['text'][:60]}... ({item['length']} chars)")
    
    print("\n❌ EXCLUDE:")
    for item in sidebar_content + footer_content:
        if item['length'] < 100:
            print(f"   • {item['text'][:60]}... (sidebar/footer)")

if __name__ == "__main__":
    create_content_summary()