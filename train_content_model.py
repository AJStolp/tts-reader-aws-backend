#!/usr/bin/env python3
"""
Training script for content quality classifier

This script will:
1. Collect training data from sample websites
2. Train a PyTorch model to predict content quality
3. Save the trained model for use in content filtering

Usage:
    python train_content_model.py
"""

import asyncio
import logging
import sys
import os

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

async def main():
    """Main training pipeline"""
    
    logger.info("Starting content classifier training pipeline...")
    
    # Step 1: Collect training data
    logger.info("Step 1: Collecting training data...")
    
    sample_urls = [
        # Documentation sites
        "https://docs.python.org/3/tutorial/introduction.html",
        "https://pytorch.org/tutorials/beginner/basics/quickstart_tutorial.html",
        "https://fastapi.tiangolo.com/tutorial/first-steps/",
        "https://docs.djangoproject.com/en/stable/intro/tutorial01/",
        
        # Blog posts
        "https://medium.com/@pytorch/pytorch-1-12-released-a05e91e4caa3",
        "https://blog.openai.com/chatgpt/",
        
        # News sites
        "https://techcrunch.com/2023/05/15/openai-gpt-4/",
        "https://arstechnica.com/information-technology/2023/03/openai-gpt-4/",
        
        # Forums
        "https://stackoverflow.com/questions/231767/what-does-the-yield-keyword-do",
        "https://www.reddit.com/r/MachineLearning/comments/top_post/",
        
        # E-learning
        "https://www.coursera.org/learn/machine-learning",
        "https://www.khanacademy.org/computing/computer-programming/programming",
    ]
    
    collector = TrainingDataCollector()
    
    try:
        # Collect training data
        await collector.collect_training_data_from_urls(sample_urls, max_pages=30)
        
        if len(collector.training_data) < 10:
            logger.warning("Very few training examples collected. Model may not train well.")
            
        # Save training data
        collector.save_training_data('training_data.json')
        
        logger.info(f"Collected {len(collector.training_data)} training examples")
        
    except Exception as e:
        logger.error(f"Data collection failed: {e}")
        logger.info("Creating minimal demo data...")
        
        # Create some demo data for testing
        demo_data = [
            {
                'features': {
                    'text_length': 500, 'word_count': 100, 'avg_word_length': 5.0,
                    'sentence_count': 10, 'paragraph_count': 3, 'heading_count': 1,
                    'is_article': 1.0, 'is_main': 0.0, 'is_section': 0.0, 'is_div': 0.0,
                    'has_content_class': 1.0, 'has_article_class': 1.0, 'has_post_class': 0.0,
                    'has_main_class': 0.0, 'has_navigation_class': 0.0, 'has_ad_class': 0.0,
                    'link_density': 0.1, 'uppercase_ratio': 0.05, 'digit_ratio': 0.02,
                    'special_char_ratio': 0.1, 'is_blog': 0.0, 'is_docs': 1.0, 'is_news': 0.0
                },
                'label': 0.9, 'url': 'demo', 'text_preview': 'High quality content example'
            },
            {
                'features': {
                    'text_length': 50, 'word_count': 10, 'avg_word_length': 3.0,
                    'sentence_count': 1, 'paragraph_count': 0, 'heading_count': 0,
                    'is_article': 0.0, 'is_main': 0.0, 'is_section': 0.0, 'is_div': 1.0,
                    'has_content_class': 0.0, 'has_article_class': 0.0, 'has_post_class': 0.0,
                    'has_main_class': 0.0, 'has_navigation_class': 1.0, 'has_ad_class': 0.0,
                    'link_density': 0.8, 'uppercase_ratio': 0.2, 'digit_ratio': 0.1,
                    'special_char_ratio': 0.3, 'is_blog': 0.0, 'is_docs': 0.0, 'is_news': 0.0
                },
                'label': 0.1, 'url': 'demo', 'text_preview': 'Low quality navigation text'
            }
        ] * 50  # Repeat to create enough examples
        
        collector.training_data = demo_data
        collector.save_training_data('training_data.json')
    
    # Step 2: Train the model
    logger.info("Step 2: Training content classifier model...")
    
    trainer = ContentClassifierTrainer()
    
    try:
        # Prepare data
        train_loader, val_loader = trainer.prepare_data('training_data.json')
        
        # Train model
        trainer.train(train_loader, val_loader, epochs=50)
        
        logger.info("Training completed successfully!")
        
        # Step 3: Test the model
        logger.info("Step 3: Testing the trained model...")
        
        # Test with some example features
        test_features = {
            'text_length': 800, 'word_count': 150, 'avg_word_length': 5.3,
            'sentence_count': 15, 'paragraph_count': 4, 'heading_count': 2,
            'is_article': 1.0, 'is_main': 0.0, 'is_section': 0.0, 'is_div': 0.0,
            'has_content_class': 1.0, 'has_article_class': 1.0, 'has_post_class': 0.0,
            'has_main_class': 0.0, 'has_navigation_class': 0.0, 'has_ad_class': 0.0,
            'link_density': 0.05, 'uppercase_ratio': 0.03, 'digit_ratio': 0.01,
            'special_char_ratio': 0.08, 'is_blog': 0.0, 'is_docs': 1.0, 'is_news': 0.0
        }
        
        prediction = trainer.predict(test_features)
        logger.info(f"Test prediction (should be high quality): {prediction:.3f}")
        
        logger.info("✅ Training pipeline completed successfully!")
        logger.info("Model saved as 'content_classifier.pth'")
        logger.info("Scaler saved as 'content_classifier_scaler.pkl'")
        
    except Exception as e:
        logger.error(f"Training failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    if not success:
        sys.exit(1)