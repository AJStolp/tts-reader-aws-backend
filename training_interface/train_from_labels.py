#!/usr/bin/env python3
"""
Train the model from human-labeled data
"""

import json
import torch
import torch.nn as nn
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import pickle

class ContentClassifier(nn.Module):
    def __init__(self, input_size=38):
        super(ContentClassifier, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(input_size, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )
    
    def forward(self, x):
        return self.network(x)

def train_on_labeled_data():
    """Train model on human-labeled Medium article data"""
    
    print("🤖 TRAINING MODEL ON YOUR LABELS")
    print("=" * 50)
    
    # Load the labeled data
    with open('medium_training_data.json', 'r') as f:
        labeled_data = json.load(f)
    
    print(f"📊 Loaded {len(labeled_data)} labeled examples")
    
    # Extract features and labels
    X = []
    y = []
    
    for example in labeled_data:
        features = example['features']
        # Convert features dict to list in consistent order
        feature_list = [
            features['text_length'],
            features['word_count'],
            features['avg_word_length'],
            features['sentence_count'],
            features['paragraph_count'],
            features['heading_count'],
            features['is_article'],
            features['is_main'],
            features['is_section'],
            features['is_div'],
            features['is_heading'],
            features['has_content_class'],
            features['has_article_class'],
            features['has_post_class'],
            features['has_main_class'],
            features['has_navigation_class'],
            features['has_ad_class'],
            features['link_density'],
            features['uppercase_ratio'],
            features['digit_ratio'],
            features['special_char_ratio'],
            features['x_position_percent'],
            features['y_position_percent'],
            features['width_percent'],
            features['is_center_column'],
            features['is_left_sidebar'],
            features['is_right_sidebar'],
            features['is_header_area'],
            features['is_footer_area'],
            features['is_main_content_area'],
            features['is_large_element'],
            features['is_small_element'],
            features['font_size'],
            features['is_large_font'],
            features['is_small_font'],
            features['is_blog'],
            features['is_docs'],
            features['is_news']
        ]
        
        X.append(feature_list)
        y.append(example['label'])
    
    X = np.array(X)
    y = np.array(y)
    
    print(f"📈 Feature matrix shape: {X.shape}")
    print(f"📈 Labels shape: {y.shape}")
    print(f"✅ Include examples: {np.sum(y == 1.0)}")
    print(f"❌ Exclude examples: {np.sum(y == 0.0)}")
    
    # Normalize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Convert to PyTorch tensors
    X_tensor = torch.FloatTensor(X_scaled)
    y_tensor = torch.FloatTensor(y.reshape(-1, 1))
    
    # Create model
    model = ContentClassifier(input_size=38)
    criterion = nn.BCELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    
    print("\n🚀 Training model...")
    
    # Train for several epochs
    model.train()
    for epoch in range(100):
        optimizer.zero_grad()
        outputs = model(X_tensor)
        loss = criterion(outputs, y_tensor)
        loss.backward()
        optimizer.step()
        
        if (epoch + 1) % 20 == 0:
            print(f"   Epoch {epoch+1}/100, Loss: {loss.item():.4f}")
    
    # Test predictions
    model.eval()
    with torch.no_grad():
        predictions = model(X_tensor)
        
    print("\n🎯 RESULTS ON YOUR LABELED DATA:")
    print("-" * 40)
    
    for i, example in enumerate(labeled_data):
        actual = example['label']
        predicted = predictions[i].item()
        correct = "✅" if (actual == 1.0 and predicted > 0.5) or (actual == 0.0 and predicted <= 0.5) else "❌"
        
        print(f"{correct} {example['text_preview'][:60]}...")
        print(f"   Actual: {'✅ Include' if actual == 1.0 else '❌ Exclude'}")
        print(f"   Predicted: {predicted:.3f} ({'✅ Include' if predicted > 0.5 else '❌ Exclude'})")
        print(f"   Zone: {example['visual_zone']}")
        print()
    
    # Save the trained model and scaler
    torch.save(model.state_dict(), 'content_classifier.pth')
    with open('content_classifier_scaler.pkl', 'wb') as f:
        pickle.dump(scaler, f)
    
    print("💾 Model saved to content_classifier.pth")
    print("💾 Scaler saved to content_classifier_scaler.pkl")
    
    print("\n🎉 TRAINING COMPLETE!")
    print("The model has learned from your Medium article preferences:")
    print("• ✅ Main titles and subtitles in center column")
    print("• ✅ Long main article content")
    print("• ❌ Related articles in sidebar/footer")
    print("• ❌ Newsletter signups and promotional content")
    print("\nNext time you process articles, the model will better predict")
    print("what content you want included in TTS!")

if __name__ == "__main__":
    train_on_labeled_data()