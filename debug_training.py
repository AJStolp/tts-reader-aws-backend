#!/usr/bin/env python3
"""
Debug training script - test on one site and show what the model learns
"""

import asyncio
import logging
import sys
import os
import json

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from textract_processor.ml_training_data_collector import TrainingDataCollector
from textract_processor.content_classifier_model import ContentClassifierTrainer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def print_content_analysis(training_data):
    """Print detailed analysis of what was found"""
    print("\n" + "="*80)
    print("CONTENT ANALYSIS RESULTS")
    print("="*80)
    
    print(f"\nTotal content blocks found: {len(training_data)}")
    
    # Sort by score to see best and worst content
    sorted_data = sorted(training_data, key=lambda x: x['label'], reverse=True)
    
    print(f"\n📋 ALL CONTENT BLOCKS (sorted by quality score):")
    print("-" * 80)
    for i, example in enumerate(sorted_data):
        features = example['features']
        quality_indicator = "🟢" if example['label'] > 0.7 else "🟡" if example['label'] > 0.4 else "🔴"
        
        print(f"\n{quality_indicator} #{i+1} - Score: {example['label']:.3f}")
        print(f"   Text preview: {example['text_preview'][:120]}...")
        print(f"   Length: {features['text_length']} chars, {features['word_count']} words")
        print(f"   HTML: {'article' if features['is_article'] else 'main' if features['is_main'] else 'section' if features['is_section'] else 'heading' if features.get('is_heading', 0) else 'div'}")
        print(f"   Classes: content={features['has_content_class']:.0f}, nav={features['has_navigation_class']:.0f}, ad={features['has_ad_class']:.0f}")
        print(f"   Quality: links={features['link_density']:.2f}, upper={features['uppercase_ratio']:.2f}")
        
        # Show visual positioning - the key new feature!
        if 'x_position_percent' in features:
            layout_zone = "CENTER" if features.get('is_center_column', 0) else \
                         "LEFT_SIDEBAR" if features.get('is_left_sidebar', 0) else \
                         "RIGHT_SIDEBAR" if features.get('is_right_sidebar', 0) else \
                         "HEADER" if features.get('is_header_area', 0) else \
                         "FOOTER" if features.get('is_footer_area', 0) else "OTHER"
            print(f"   🎯 VISUAL: x={features['x_position_percent']:.0f}%, y={features['y_position_percent']:.0f}%, width={features['width_percent']:.0f}%, zone={layout_zone}")
            print(f"   📏 SIZE: font={features.get('font_size', 16):.0f}px, {'LARGE' if features.get('is_large_element', 0) else 'SMALL' if features.get('is_small_element', 0) else 'NORMAL'}")
    
    print(f"\n🏆 TOP 3 HIGHEST QUALITY CONTENT BLOCKS:")
    print("-" * 50)
    for i, example in enumerate(sorted_data[:3]):
        features = example['features']
        print(f"\n#{i+1} - Score: {example['label']:.3f}")
        print(f"Text preview: {example['text_preview'][:100]}...")
        print(f"Features: text_length={features['text_length']}, word_count={features['word_count']}")
        print(f"HTML: article={features['is_article']}, main={features['is_main']}, section={features['is_section']}")
        print(f"Classes: content={features['has_content_class']}, nav={features['has_navigation_class']}")
        print(f"Quality: link_density={features['link_density']:.3f}, uppercase_ratio={features['uppercase_ratio']:.3f}")
    
    print(f"\n💩 BOTTOM 3 LOWEST QUALITY CONTENT BLOCKS:")
    print("-" * 50)
    for i, example in enumerate(sorted_data[-3:]):
        features = example['features']
        print(f"\n#{len(sorted_data)-2+i} - Score: {example['label']:.3f}")
        print(f"Text preview: {example['text_preview'][:100]}...")
        print(f"Features: text_length={features['text_length']}, word_count={features['word_count']}")
        print(f"HTML: article={features['is_article']}, main={features['is_main']}, section={features['is_section']}")
        print(f"Classes: content={features['has_content_class']}, nav={features['has_navigation_class']}")
        print(f"Quality: link_density={features['link_density']:.3f}, uppercase_ratio={features['uppercase_ratio']:.3f}")

    print(f"\n📊 FEATURE STATISTICS:")
    print("-" * 50)
    
    # Calculate feature averages for high vs low quality content
    high_quality = [x for x in training_data if x['label'] > 0.6]
    low_quality = [x for x in training_data if x['label'] < 0.4]
    
    if high_quality and low_quality:
        print(f"High quality blocks ({len(high_quality)}): avg_length={sum(x['features']['text_length'] for x in high_quality)/len(high_quality):.0f}")
        print(f"Low quality blocks ({len(low_quality)}): avg_length={sum(x['features']['text_length'] for x in low_quality)/len(low_quality):.0f}")
        
        print(f"High quality: avg_link_density={sum(x['features']['link_density'] for x in high_quality)/len(high_quality):.3f}")
        print(f"Low quality: avg_link_density={sum(x['features']['link_density'] for x in low_quality)/len(low_quality):.3f}")

async def debug_single_site():
    """Test training on a single well-known site"""
    
    # Use a real blog post to see content vs navigation filtering
    test_url = "https://spin.atomicobject.com/keep-a-developer-log/?ref=dailydev"
    
    logger.info(f"🔍 Testing content extraction on: {test_url}")
    
    # Step 1: Collect training data from one site
    collector = TrainingDataCollector()
    
    try:
        await collector.collect_training_data_from_urls([test_url], max_pages=1)
        
        if not collector.training_data:
            logger.error("❌ No training data collected!")
            return False
            
        # Save the data so we can inspect it
        collector.save_training_data('debug_training_data.json')
        
        # Print detailed analysis
        print_content_analysis(collector.training_data)
        
        # Step 2: Try training a minimal model
        logger.info(f"\n🤖 Training model on {len(collector.training_data)} examples...")
        
        if len(collector.training_data) < 5:
            logger.warning("⚠️  Very few examples - adding some demo data for training")
            # Add some demo examples to make training work
            demo_examples = [
                {
                    'features': {
                        'text_length': 800, 'word_count': 150, 'avg_word_length': 5.3,
                        'sentence_count': 15, 'paragraph_count': 4, 'heading_count': 2,
                        'is_article': 1.0, 'is_main': 0.0, 'is_section': 0.0, 'is_div': 0.0,
                        'has_content_class': 1.0, 'has_article_class': 1.0, 'has_post_class': 0.0,
                        'has_main_class': 0.0, 'has_navigation_class': 0.0, 'has_ad_class': 0.0,
                        'link_density': 0.05, 'uppercase_ratio': 0.03, 'digit_ratio': 0.01,
                        'special_char_ratio': 0.08, 'is_blog': 0.0, 'is_docs': 1.0, 'is_news': 0.0
                    },
                    'label': 0.9, 'url': 'demo_high', 'text_preview': 'High quality content example'
                },
                {
                    'features': {
                        'text_length': 30, 'word_count': 5, 'avg_word_length': 3.0,
                        'sentence_count': 1, 'paragraph_count': 0, 'heading_count': 0,
                        'is_article': 0.0, 'is_main': 0.0, 'is_section': 0.0, 'is_div': 1.0,
                        'has_content_class': 0.0, 'has_article_class': 0.0, 'has_post_class': 0.0,
                        'has_main_class': 0.0, 'has_navigation_class': 1.0, 'has_ad_class': 0.0,
                        'link_density': 0.8, 'uppercase_ratio': 0.2, 'digit_ratio': 0.1,
                        'special_char_ratio': 0.3, 'is_blog': 0.0, 'is_docs': 0.0, 'is_news': 0.0
                    },
                    'label': 0.1, 'url': 'demo_low', 'text_preview': 'Navigation menu text'
                }
            ] * 20  # Repeat to get enough examples
            
            collector.training_data.extend(demo_examples)
            collector.save_training_data('debug_training_data.json')
        
        # Train the model
        trainer = ContentClassifierTrainer()
        train_loader, val_loader = trainer.prepare_data('debug_training_data.json')
        
        # Train for just a few epochs to test
        trainer.train(train_loader, val_loader, epochs=10)
        
        logger.info("✅ Training completed successfully!")
        
        # Test the model on the original content
        print(f"\n🧪 TESTING MODEL PREDICTIONS:")
        print("-" * 50)
        
        for i, example in enumerate(collector.training_data[:5]):
            original_score = example['label']
            predicted_score = trainer.predict(example['features'])
            
            print(f"Example {i+1}:")
            print(f"  Original score: {original_score:.3f}")
            print(f"  Predicted score: {predicted_score:.3f}")
            print(f"  Text: {example['text_preview'][:80]}...")
            print()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error during debug training: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting debug training on single site...")
    success = asyncio.run(debug_single_site())
    
    if success:
        print("\n✅ Debug training completed! Check the output above to see:")
        print("   - What content blocks were found")
        print("   - How they were scored")
        print("   - What features the model learned")
        print("   - Model predictions vs original scores")
    else:
        print("\n❌ Debug training failed")
        sys.exit(1)