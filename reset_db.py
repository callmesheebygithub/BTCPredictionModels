# reset_db.py
import sqlite3
import os

def reset_predictions_table():
    db_path = 'btc_data.db'
    
    if not os.path.exists(db_path):
        print(f"❌ Database '{db_path}' not found!")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("DROP TABLE IF EXISTS predictions")
        cursor.execute('''
            CREATE TABLE predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE,
                predicted_close REAL,
                actual_close REAL,
                error_percentage REAL,
                absolute_error REAL,
                direction_correct INTEGER,
                direction_type TEXT,
                actual_direction_type TEXT,
                predicted_return REAL,
                actual_return REAL,
                confidence_score REAL,
                range_low REAL,
                range_high REAL,
                regime TEXT,
                signal TEXT,
                model_version TEXT,
                timestamp TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Predictions table reset successfully!")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    reset_predictions_table()