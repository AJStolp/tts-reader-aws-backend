import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader, random_split
import numpy as np
import json
import logging
from typing import Tuple, List
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, r2_score
import pickle

logger = logging.getLogger(__name__)

class ContentQualityDataset(Dataset):
    """Dataset for content quality classification"""
    
    def __init__(self, features: np.ndarray, labels: np.ndarray):
        self.features = torch.FloatTensor(features)
        self.labels = torch.FloatTensor(labels)
    
    def __len__(self):
        return len(self.features)
    
    def __getitem__(self, idx):
        return self.features[idx], self.labels[idx]

class ContentClassifier(nn.Module):
    """Neural network for predicting content quality scores"""
    
    def __init__(self, input_size: int, hidden_sizes: List[int] = [128, 64, 32]):
        super(ContentClassifier, self).__init__()
        
        layers = []
        prev_size = input_size
        
        for hidden_size in hidden_sizes:
            layers.extend([
                nn.Linear(prev_size, hidden_size),
                nn.ReLU(),
                nn.Dropout(0.2)
            ])
            prev_size = hidden_size
        
        # Output layer - single value between 0 and 1
        layers.append(nn.Linear(prev_size, 1))
        layers.append(nn.Sigmoid())  # Ensures output is between 0 and 1
        
        self.network = nn.Sequential(*layers)
    
    def forward(self, x):
        return self.network(x).squeeze()

class ContentClassifierTrainer:
    """Trainer class for the content classifier"""
    
    def __init__(self, model_save_path: str = "content_classifier.pth"):
        self.model = None
        self.scaler = StandardScaler()
        self.model_save_path = model_save_path
        self.feature_names = None
        self.device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        logger.info(f"Using device: {self.device}")
    
    def prepare_data(self, training_data_path: str) -> Tuple[DataLoader, DataLoader]:
        """Load and prepare training data"""
        
        with open(training_data_path, 'r') as f:
            training_data = json.load(f)
        
        if not training_data:
            raise ValueError("No training data found")
        
        # Extract features and labels
        self.feature_names = list(training_data[0]['features'].keys())
        
        features = []
        labels = []
        
        for example in training_data:
            feature_vector = [example['features'][name] for name in self.feature_names]
            features.append(feature_vector)
            labels.append(example['label'])
        
        features = np.array(features)
        labels = np.array(labels)
        
        # Normalize features
        features = self.scaler.fit_transform(features)
        
        # Create dataset
        dataset = ContentQualityDataset(features, labels)
        
        # Split into train/validation
        train_size = int(0.8 * len(dataset))
        val_size = len(dataset) - train_size
        train_dataset, val_dataset = random_split(dataset, [train_size, val_size])
        
        # Create data loaders
        train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)
        
        logger.info(f"Training data: {train_size} examples, Validation: {val_size} examples")
        logger.info(f"Features: {len(self.feature_names)}")
        
        return train_loader, val_loader
    
    def create_model(self, input_size: int):
        """Create the neural network model"""
        self.model = ContentClassifier(input_size).to(self.device)
        logger.info(f"Created model with {input_size} input features")
        logger.info(f"Model architecture:\n{self.model}")
    
    def train(self, train_loader: DataLoader, val_loader: DataLoader, epochs: int = 100):
        """Train the model"""
        
        if self.model is None:
            input_size = len(self.feature_names)
            self.create_model(input_size)
        
        criterion = nn.MSELoss()  # Mean Squared Error for regression
        optimizer = optim.Adam(self.model.parameters(), lr=0.001)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10, factor=0.5)
        
        best_val_loss = float('inf')
        patience_counter = 0
        
        for epoch in range(epochs):
            # Training phase
            self.model.train()
            train_loss = 0.0
            
            for features, labels in train_loader:
                features, labels = features.to(self.device), labels.to(self.device)
                
                optimizer.zero_grad()
                outputs = self.model(features)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()
                
                train_loss += loss.item()
            
            # Validation phase
            self.model.eval()
            val_loss = 0.0
            val_predictions = []
            val_labels = []
            
            with torch.no_grad():
                for features, labels in val_loader:
                    features, labels = features.to(self.device), labels.to(self.device)
                    outputs = self.model(features)
                    loss = criterion(outputs, labels)
                    val_loss += loss.item()
                    
                    val_predictions.extend(outputs.cpu().numpy())
                    val_labels.extend(labels.cpu().numpy())
            
            # Calculate metrics
            train_loss /= len(train_loader)
            val_loss /= len(val_loader)
            
            r2 = r2_score(val_labels, val_predictions)
            
            scheduler.step(val_loss)
            
            if epoch % 10 == 0:
                logger.info(f"Epoch {epoch}/{epochs}: Train Loss: {train_loss:.4f}, "
                           f"Val Loss: {val_loss:.4f}, R²: {r2:.4f}")
            
            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                self.save_model()
            else:
                patience_counter += 1
                if patience_counter >= 20:
                    logger.info(f"Early stopping at epoch {epoch}")
                    break
        
        logger.info(f"Training completed. Best validation loss: {best_val_loss:.4f}")
    
    def save_model(self):
        """Save the trained model and scaler"""
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'feature_names': self.feature_names,
            'input_size': len(self.feature_names)
        }, self.model_save_path)
        
        # Save scaler separately
        with open(self.model_save_path.replace('.pth', '_scaler.pkl'), 'wb') as f:
            pickle.dump(self.scaler, f)
        
        logger.info(f"Model saved to {self.model_save_path}")
    
    def load_model(self, model_path: str = None):
        """Load a trained model"""
        if model_path is None:
            model_path = self.model_save_path
        
        checkpoint = torch.load(model_path, map_location=self.device)
        
        self.feature_names = checkpoint['feature_names']
        input_size = checkpoint['input_size']
        
        self.model = ContentClassifier(input_size).to(self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        
        # Load scaler
        scaler_path = model_path.replace('.pth', '_scaler.pkl')
        with open(scaler_path, 'rb') as f:
            self.scaler = pickle.load(f)
        
        logger.info(f"Model loaded from {model_path}")
    
    def predict(self, features: dict) -> float:
        """Predict content quality score for a single example"""
        if self.model is None:
            raise ValueError("Model not loaded")
        
        # Convert features dict to array in correct order
        feature_vector = [features.get(name, 0.0) for name in self.feature_names]
        feature_array = np.array([feature_vector])
        
        # Normalize features
        feature_array = self.scaler.transform(feature_array)
        
        # Convert to tensor and predict
        feature_tensor = torch.FloatTensor(feature_array).to(self.device)
        
        self.model.eval()
        with torch.no_grad():
            prediction = self.model(feature_tensor).cpu().item()
        
        return prediction

# Example training script
async def train_content_classifier():
    """Main training function"""
    
    trainer = ContentClassifierTrainer()
    
    try:
        # Prepare data
        train_loader, val_loader = trainer.prepare_data('training_data.json')
        
        # Train model
        trainer.train(train_loader, val_loader, epochs=100)
        
        logger.info("Training completed successfully!")
        
    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(train_content_classifier())