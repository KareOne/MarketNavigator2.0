#!/usr/bin/env python3
"""
Diagnostic script to debug worker failures
Run this inside the container to identify issues with:
- Chrome/ChromeDriver installation
- Selenium configuration
- Network connectivity
- File permissions
- Environment setup
"""

import sys
import os
import subprocess
from pathlib import Path


def print_section(title):
    """Print a section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def check_chrome_installation():
    """Check if Chrome is installed"""
    print_section("Chrome Installation Check")
    
    try:
        result = subprocess.run(['which', 'google-chrome'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Chrome found at: {result.stdout.strip()}")
            
            # Get Chrome version
            version_result = subprocess.run(['google-chrome', '--version'], capture_output=True, text=True)
            print(f"   Version: {version_result.stdout.strip()}")
        else:
            print("❌ Chrome NOT found")
            print("   Install with: apt-get update && apt-get install -y google-chrome-stable")
    except Exception as e:
        print(f"❌ Error checking Chrome: {e}")


def check_chromedriver():
    """Check if ChromeDriver is installed"""
    print_section("ChromeDriver Check")
    
    try:
        result = subprocess.run(['which', 'chromedriver'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ ChromeDriver found at: {result.stdout.strip()}")
            
            # Get version
            version_result = subprocess.run(['chromedriver', '--version'], capture_output=True, text=True)
            print(f"   Version: {version_result.stdout.strip()}")
        else:
            print("⚠️  ChromeDriver not in PATH")
            print("   Will be downloaded by webdriver-manager")
    except Exception as e:
        print(f"⚠️  Error checking ChromeDriver: {e}")


def check_selenium():
    """Check Selenium installation"""
    print_section("Selenium Check")
    
    try:
        import selenium
        print(f"✅ Selenium installed: {selenium.__version__}")
        
        from selenium import webdriver
        print("✅ selenium.webdriver module available")
        
        from selenium.webdriver.chrome.service import Service
        print("✅ Chrome service available")
        
    except ImportError as e:
        print(f"❌ Selenium import error: {e}")


def check_webdriver_manager():
    """Check webdriver-manager installation"""
    print_section("WebDriver Manager Check")
    
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        print("✅ webdriver-manager installed")
        
        # Try to get chromedriver path (without actually installing)
        print("   Testing ChromeDriverManager...")
        try:
            manager = ChromeDriverManager()
            print(f"   ✅ ChromeDriverManager initialized")
        except Exception as e:
            print(f"   ⚠️  ChromeDriverManager init warning: {e}")
        
    except ImportError as e:
        print(f"❌ webdriver-manager not installed: {e}")


def check_display():
    """Check display configuration for headless mode"""
    print_section("Display Configuration")
    
    display = os.getenv('DISPLAY')
    if display:
        print(f"✅ DISPLAY set to: {display}")
    else:
        print("⚠️  DISPLAY not set (headless mode required)")
    
    # Check if Xvfb is available (for virtual display)
    try:
        result = subprocess.run(['which', 'Xvfb'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Xvfb available at: {result.stdout.strip()}")
        else:
            print("⚠️  Xvfb not available (headless mode required)")
    except Exception as e:
        print(f"⚠️  Error checking Xvfb: {e}")


def check_profile_directories():
    """Check Chrome profile directories"""
    print_section("Chrome Profile Directories")
    
    profile_paths = [
        '/app/chrome-profiles',
        '/app/browser_data',
        '/tmp'
    ]
    
    for path in profile_paths:
        path_obj = Path(path)
        if path_obj.exists():
            print(f"✅ {path} exists")
            
            # Check permissions
            if os.access(path, os.W_OK):
                print(f"   ✅ Writable")
            else:
                print(f"   ❌ NOT writable")
        else:
            print(f"⚠️  {path} does not exist")


def check_network():
    """Check network connectivity"""
    print_section("Network Connectivity")
    
    urls = [
        'google.com',
        'linkedin.com',
        'chromedriver.storage.googleapis.com'
    ]
    
    for url in urls:
        try:
            result = subprocess.run(['ping', '-c', '1', '-W', '2', url], 
                                   capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print(f"✅ Can reach {url}")
            else:
                print(f"❌ Cannot reach {url}")
        except subprocess.TimeoutExpired:
            print(f"⏱️  Timeout reaching {url}")
        except Exception as e:
            print(f"❌ Error pinging {url}: {e}")


def check_python_packages():
    """Check required Python packages"""
    print_section("Python Packages")
    
    packages = [
        'selenium',
        'webdriver_manager',
        'pyperclip',
        'pymysql',
        'flask',
        'flask_restx'
    ]
    
    for package in packages:
        try:
            __import__(package)
            print(f"✅ {package} installed")
        except ImportError:
            print(f"❌ {package} NOT installed")


def test_bot_initialization():
    """Test bot initialization"""
    print_section("Bot Initialization Test")
    
    try:
        print("Attempting to import LinkedinBot...")
        from core.bot.linkdeen_bot import LinkedinBot
        print("✅ LinkedinBot imported successfully")
        
        print("\nAttempting to create bot instance...")
        try:
            bot = LinkedinBot('test_user', is_first=0)
            print("✅ Bot instance created")
            
            if hasattr(bot, 'driver') and bot.driver:
                print("✅ Bot driver initialized")
                
                # Try to navigate to a page
                try:
                    bot.driver.get('https://www.google.com')
                    print("✅ Bot can navigate to URLs")
                    
                    # Cleanup
                    bot.cleanup(force_quit=True)
                    print("✅ Bot cleanup successful")
                    
                except Exception as e:
                    print(f"❌ Navigation error: {e}")
                    try:
                        bot.cleanup(force_quit=True)
                    except:
                        pass
            else:
                print("❌ Bot driver not initialized")
                
        except Exception as e:
            print(f"❌ Bot creation failed: {e}")
            import traceback
            traceback.print_exc()
            
    except ImportError as e:
        print(f"❌ Cannot import LinkedinBot: {e}")


def check_database():
    """Check database connectivity"""
    print_section("Database Connectivity")
    
    try:
        from config.config import get_db_connection
        print("✅ get_db_connection imported")
        
        try:
            conn = get_db_connection()
            print("✅ Database connection successful")
            
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            print("✅ Database query successful")
            
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            
    except ImportError as e:
        print(f"❌ Cannot import config: {e}")


def main():
    """Run all diagnostic checks"""
    print("""
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║         LinkedIn Bot Worker Diagnostic Tool                ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    # Run all checks
    check_chrome_installation()
    check_chromedriver()
    check_selenium()
    check_webdriver_manager()
    check_display()
    check_profile_directories()
    check_network()
    check_python_packages()
    check_database()
    test_bot_initialization()
    
    print_section("Diagnostic Complete")
    print("\n📋 Review the output above to identify issues.")
    print("🔧 Common fixes:")
    print("   1. Install Chrome: apt-get install -y google-chrome-stable")
    print("   2. Run in headless mode: Set CHROME['is_headless'] = True in config")
    print("   3. Fix permissions: chmod -R 777 /app/chrome-profiles")
    print("   4. Check network: Ensure container has internet access")
    print("   5. Update ChromeDriver: pip install --upgrade webdriver-manager")
    print()


if __name__ == '__main__':
    main()
