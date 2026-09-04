# check_model.py
import os
import pickle
import torch
from datetime import datetime
from models.lstm_model import ModelTrainer
from database.db_manager import DatabaseManager

# Check if model exists
model_dir = 'models/v20260903_094502'
model_path = os.path.join(model_dir, 'model.pth')

if os.path.exists(model_path):
    print(f"✅ Model exists at: {model_path}")
    print(f"   Size: {os.path.getsize(model_path)} bytes")
else:
    print(f"❌ Model not found: {model_path}")
    print("🔄 Training new model...")
    
    # Train new model
    trainer = ModelTrainer()
    db = DatabaseManager()
    df = db.get_all_data()
    
    if not df.empty:
        version = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        trainer.train(df, force=True, version=version)
        print(f"✅ New model trained: {version}")
    else:
        print("❌ No data in database!")