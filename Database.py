"""
mysql_db_setup.py - Pure Database Setup Script
Only creates database and tables, no data fetching
"""

import mysql.connector
from mysql.connector import Error
import logging
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Read credentials from .env
DB_USER = os.getenv('db_user')
DB_PASSWORD = os.getenv('db_password')
DB_HOST = os.getenv('db_host')
DB_NAME = os.getenv('db_name')

# Check if all values are present
if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_NAME]):
    raise ValueError("❌ .env file mein kuch values missing hain! Please check .env file.")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('db_setup.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DatabaseSetup:
    def __init__(self):
        """Initialize database setup"""
        self.host = DB_HOST
        self.database = DB_NAME
        self.user = DB_USER
        self.password = DB_PASSWORD
        self.conn = None
        self.cursor = None
        
    def connect(self):
        """Connect to MySQL server"""
        try:
            logger.info(f"🔌 Connecting to MySQL server at {self.host}...")
            self.conn = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password
            )
            self.cursor = self.conn.cursor()
            logger.info("✅ Connected to MySQL server successfully!")
            return True
        except Error as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
    
    def create_database(self):
        """Create database if it doesn't exist"""
        try:
            logger.info(f"📁 Checking if database '{self.database}' exists...")
            self.cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.database}")
            logger.info(f"✅ Database '{self.database}' created/verified successfully!")
            return True
        except Error as e:
            logger.error(f"❌ Error creating database: {e}")
            return False
    
    def use_database(self):
        """Switch to the database"""
        try:
            self.cursor.execute(f"USE {self.database}")
            logger.info(f"✅ Switched to database '{self.database}'")
            return True
        except Error as e:
            logger.error(f"❌ Error switching to database: {e}")
            return False
    
    def create_tables(self):
        """Create all required tables without ID column"""
        try:
            logger.info("📊 Creating tables...")
            
            # Table 1: BTC Price History (No ID column)
            logger.info("  • Creating 'btc_price_history' table...")
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS btc_price_history (
                    date DATE PRIMARY KEY,
                    open DECIMAL(18, 8),
                    high DECIMAL(18, 8),
                    low DECIMAL(18, 8),
                    close DECIMAL(18, 8),
                    volume BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            logger.info("    ✅ 'btc_price_history' table created (date as PRIMARY KEY)")
            
            # Table 2: Predictions (No ID column)
            logger.info("  • Creating 'predictions' table...")
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS predictions (
                    date DATE PRIMARY KEY,
                    predicted_price DECIMAL(18, 8),
                    actual_price DECIMAL(18, 8),
                    direction VARCHAR(10),
                    accuracy DECIMAL(5, 2),
                    model_type VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            logger.info("    ✅ 'predictions' table created (date as PRIMARY KEY)")
            
            # Table 3: Performance (No ID column)
            logger.info("  • Creating 'performance' table...")
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance (
                    date DATE PRIMARY KEY,
                    total_predictions INT,
                    correct_predictions INT,
                    accuracy DECIMAL(5, 2),
                    avg_error DECIMAL(10, 2),
                    model_type VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            logger.info("    ✅ 'performance' table created (date as PRIMARY KEY)")
            
            self.conn.commit()
            logger.info("✅ All tables created successfully!")
            return True
            
        except Error as e:
            logger.error(f"❌ Error creating tables: {e}")
            self.conn.rollback()
            return False
    
    def show_database_info(self):
        """Show database information"""
        try:
            logger.info("\n" + "="*60)
            logger.info("📊 DATABASE INFORMATION")
            logger.info("="*60)
            logger.info(f"Database: {self.database}")
            logger.info(f"Host: {self.host}")
            logger.info(f"User: {self.user}")
            
            # Show tables
            self.cursor.execute("SHOW TABLES")
            tables = self.cursor.fetchall()
            
            if tables:
                logger.info(f"\n📋 Tables: {len(tables)}")
                for table in tables:
                    table_name = table[0]
                    self.cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = self.cursor.fetchone()[0]
                    
                    # Get columns
                    self.cursor.execute(f"SHOW COLUMNS FROM {table_name}")
                    columns = self.cursor.fetchall()
                    
                    logger.info(f"\n  📌 {table_name}")
                    logger.info(f"     Records: {count}")
                    logger.info(f"     Columns: {len(columns)}")
                    logger.info(f"     Column Names: {', '.join([col[0] for col in columns])}")
                    
                    # Show primary key
                    self.cursor.execute(f"SHOW KEYS FROM {table_name} WHERE Key_name = 'PRIMARY'")
                    primary_key = self.cursor.fetchone()
                    if primary_key:
                        logger.info(f"     Primary Key: {primary_key[4]}")
            else:
                logger.info("\nℹ️ No tables found in database")
            
            logger.info("="*60)
            
        except Error as e:
            logger.error(f"❌ Error showing database info: {e}")
    
    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            logger.info("🔒 Database connection closed")
    
    def setup(self):
        """Complete database setup"""
        logger.info("\n" + "="*60)
        logger.info("🚀 STARTING DATABASE SETUP")
        logger.info("="*60)
        
        # Step 1: Connect to MySQL
        if not self.connect():
            return False
        
        # Step 2: Create database
        if not self.create_database():
            self.close()
            return False
        
        # Step 3: Use database
        if not self.use_database():
            self.close()
            return False
        
        # Step 4: Create tables
        if not self.create_tables():
            self.close()
            return False
        
        # Step 5: Show database info
        self.show_database_info()
        
        logger.info("\n✅ DATABASE SETUP COMPLETED SUCCESSFULLY!")
        return True

def main():
    """Main function"""
    setup = DatabaseSetup()
    
    try:
        if setup.setup():
            print("\n" + "="*60)
            print("✅ Database setup completed!")
            print(f"📁 Database: {DB_NAME}")
            print(f"🔌 Host: {DB_HOST}")
            print("="*60)
        else:
            print("\n❌ Database setup failed!")
            
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        
    finally:
        setup.close()

if __name__ == "__main__":
    main()