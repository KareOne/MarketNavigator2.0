#!/usr/bin/env python3
"""
Setup script for TracXN API
Initializes database and verifies configuration
"""

import sys
import os
from database import DatabaseManager, test_database_connection

def setup_database():
    """Setup and initialize the database"""
    print("🔧 Setting up TracXN database...")
    
    # Create database if it doesn't exist
    print("\n1. Creating database if it doesn't exist...")
    try:
        # First connect without specifying database
        import mysql.connector
        from config import DB_CONFIG_HOST, DB_CONFIG_PORT, DB_CONFIG_USER, DB_CONFIG_PASSWORD, DB_CONFIG_DATABASE
        
        connection = mysql.connector.connect(
            host=DB_CONFIG_HOST,
            port=DB_CONFIG_PORT,
            user=DB_CONFIG_USER,
            password=DB_CONFIG_PASSWORD,
            auth_plugin='mysql_native_password'
        )
        
        cursor = connection.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG_DATABASE} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        connection.commit()
        cursor.close()
        connection.close()
        
        print(f"✅ Database '{DB_CONFIG_DATABASE}' created/verified")
        
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        return False
    
    # Test connection with database
    print("\n2. Testing database connection...")
    if not test_database_connection():
        print("❌ Database connection failed!")
        print("Please check your database configuration in config.py")
        return False
    
    # Initialize database manager and create tables
    print("\n3. Creating database tables...")
    db = DatabaseManager()
    try:
        if db.connect():
            db.create_tables()
            print("✅ Database tables created successfully")
            return True
        else:
            print("❌ Failed to connect to database for table creation")
            return False
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return False
    finally:
        db.disconnect()

def verify_dependencies():
    """Verify all required dependencies are installed"""
    print("📦 Verifying dependencies...")
    
    required_packages = [
        'fastapi',
        'uvicorn',
        'pydantic',
        'mysql.connector',
        'playwright',
        'requests',
        'dotenv'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'mysql.connector':
                import mysql.connector
            elif package == 'dotenv':
                import dotenv
            else:
                __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package}")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Please install missing packages with:")
        print("pip install -r requirements.txt")
        return False
    
    print("✅ All dependencies are installed")
    return True

def create_directories():
    """Create necessary directories"""
    print("\n📁 Creating necessary directories...")
    
    directories = [
        'company_data',
        'images_cache',
        'logs',
        'exported_companies'
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"✅ {directory}/")
        except Exception as e:
            print(f"❌ Error creating {directory}/: {e}")
            return False
    
    return True

def main():
    print("🚀 TracXN API Setup")
    print("=" * 50)
    
    success = True
    
    # Verify dependencies
    if not verify_dependencies():
        success = False
    
    # Create directories
    if not create_directories():
        success = False
    
    # Setup database
    if not setup_database():
        success = False
    
    print("\n" + "=" * 50)
    
    if success:
        print("✅ Setup completed successfully!")
        print("\nNext steps:")
        print("1. Start the API server:")
        print("   python api.py")
        print("   or")
        print("   uvicorn api:app --reload --host 0.0.0.0 --port 8000")
        print("\n2. Access the API documentation:")
        print("   http://localhost:8000/docs")
        print("\n3. Test database connection:")
        print("   python db_manager.py --check")
        print("\n4. Export data (when you have some):")
        print("   python db_manager.py --export")
        
    else:
        print("❌ Setup failed!")
        print("Please fix the errors above and run setup again.")
        sys.exit(1)

if __name__ == "__main__":
    main()