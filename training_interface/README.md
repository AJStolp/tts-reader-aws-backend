# Training Interface

This directory contains the human-in-the-loop training system for the content classifier.

## Directory Structure

```
training_interface/
├── data/
│   └── medium_training_data.json # Human-labeled training data
├── models/
│   ├── content_classifier.pth    # Trained PyTorch model
│   └── content_classifier_scaler.pkl # Feature scaler
├── human_labeling_interface.py  # CLI labeling interface
├── train_from_labels.py         # Model training script
├── demo_medium.py              # Demo content extraction
└── test_labeling_demo.py       # Test labeling demo
```

## Quick Start

### 1. Start API Server (for frontend integration)
```bash
cd training_interface/api
python training_api.py
```

### 2. Use CLI Interface (standalone)
```bash
cd training_interface
python human_labeling_interface.py
```

### 3. Train Model from Labeled Data
```bash
cd training_interface
python train_from_labels.py
```

## API Endpoints

- **POST /api/extract-content** - Extract content blocks from URL
- **POST /api/submit-labels** - Submit human labels and train model  
- **POST /api/test-model** - Test trained model on new URL

## Workflow

1. **Extract Content**: API extracts content blocks with visual positioning
2. **Human Labeling**: User labels each block as ✅ include / ❌ exclude for TTS
3. **Model Training**: System learns from labels and improves predictions
4. **Testing**: Test improved model on new articles

## Features

- Visual layout analysis (center/sidebar/header/footer detection)
- Content quality scoring with 38+ features
- Incremental learning from multiple labeling sessions
- Clean text processing (removes emojis/SVGs)
- CORS-enabled API for frontend integration