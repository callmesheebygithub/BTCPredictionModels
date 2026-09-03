# check_files.py
import os

def check_for_null_bytes(filepath):
    try:
        with open(filepath, 'rb') as f:
            content = f.read()
            if b'\x00' in content:
                print(f"❌ NULL bytes found: {filepath}")
                return True
            else:
                print(f"✅ Clean: {filepath}")
                return False
    except Exception as e:
        print(f"⚠️ Error reading {filepath}: {e}")
        return False

# Check all python files
python_files = [
    'main.py',
    'config.py',
    'prediction/predictor.py',
    'prediction/__init__.py',
    'prediction/confidence.py',
    'prediction/intervals.py',
    'prediction/signal.py',
    'models/__init__.py',
    'models/lstm_model.py',
    'models/ensemble.py',
    'models/advanced_ml.py',
    'database/__init__.py',
    'database/db_manager.py',
    'data/__init__.py',
    'data/pipeline.py',
    'data/yahoo_fetcher.py',
    'validation/__init__.py',
    'validation/champion.py',
    'validation/walk_forward.py',
    'utils/__init__.py',
    'utils/helpers.py'
]

print("Checking files for null bytes...\n")
for file in python_files:
    if os.path.exists(file):
        check_for_null_bytes(file)
    else:
        print(f"⚠️ File not found: {file}")