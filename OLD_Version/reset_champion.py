# reset_champion.py
import sqlite3

def reset_champion():
    conn = sqlite3.connect('btc_data.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE model_versions SET is_champion = 0")
    cursor.execute("DELETE FROM model_versions")
    conn.commit()
    conn.close()
    print("✅ Champion reset successfully!")

if __name__ == "__main__":
    reset_champion()