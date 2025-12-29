#!/usr/bin/env python3
"""
Example script demonstrating audio CAPTCHA solving with Tracxn scraper.

This script shows how to:
1. Initialize the bot
2. Handle audio CAPTCHAs
3. Switch between image and audio modes
"""

import asyncio
from playwright.async_api import async_playwright
from tracxn_scrapper import TracxnBot


async def example_audio_captcha():
    """Example: Using audio CAPTCHA mode explicitly"""
    async with async_playwright() as playwright:
        bot = TracxnBot(playwright, debug=True)
        
        try:
            # Open the target page
            await bot.open_target_page()
            
            # Perform login steps until CAPTCHA appears
            # ... (fill email, click submit, etc.)
            
            # When CAPTCHA appears, solve with audio
            print("Attempting to solve CAPTCHA with audio mode...")
            captcha_success = await bot.handle_captcha(captcha_type="audio")
            
            if captcha_success:
                print("✓ Audio CAPTCHA solved successfully!")
            else:
                print("✗ Failed to solve audio CAPTCHA")
                
        finally:
            await bot.close()


async def example_fallback_strategy():
    """Example: Try audio first, fallback to image if needed"""
    async with async_playwright() as playwright:
        bot = TracxnBot(playwright, debug=True)
        
        try:
            await bot.open_target_page()
            
            # Try audio captcha first
            print("Attempting audio CAPTCHA...")
            audio_success = await bot.handle_captcha(captcha_type="audio")
            
            if not audio_success:
                print("Audio failed, falling back to image CAPTCHA...")
                image_success = await bot.handle_captcha(captcha_type="image")
                
                if image_success:
                    print("✓ Image CAPTCHA solved successfully!")
                else:
                    print("✗ Both audio and image CAPTCHA failed")
            else:
                print("✓ Audio CAPTCHA solved on first try!")
                
        finally:
            await bot.close()


async def example_standard_login():
    """Example: Standard login (defaults to image CAPTCHA)"""
    async with async_playwright() as playwright:
        bot = TracxnBot(playwright, debug=True)
        
        try:
            # Standard login - uses image CAPTCHA by default
            success = await bot.login()
            
            if success:
                print("✓ Login successful!")
                
                # Perform scraping tasks
                companies = await bot.search_companies(
                    query="artificial intelligence",
                    type="description"
                )
                
                print(f"Found {len(companies)} companies")
            else:
                print("✗ Login failed")
                
        finally:
            await bot.close()


async def example_with_custom_settings():
    """Example: Custom audio CAPTCHA with retry logic"""
    async with async_playwright() as playwright:
        bot = TracxnBot(playwright, debug=True)
        
        try:
            await bot.open_target_page()
            
            max_retries = 3
            captcha_solved = False
            
            for attempt in range(max_retries):
                print(f"\nAttempt {attempt + 1}/{max_retries}")
                
                try:
                    # Try audio CAPTCHA
                    captcha_solved = await bot.handle_captcha(captcha_type="audio")
                    
                    if captcha_solved:
                        print("✓ CAPTCHA solved!")
                        break
                    else:
                        print(f"Attempt {attempt + 1} failed")
                        
                except Exception as e:
                    print(f"Error on attempt {attempt + 1}: {e}")
                
                if attempt < max_retries - 1:
                    print("Waiting before retry...")
                    await asyncio.sleep(5)
            
            if not captcha_solved:
                print("\n✗ All attempts failed")
            
        finally:
            await bot.close()


# Run examples
if __name__ == "__main__":
    print("=" * 60)
    print("Audio CAPTCHA Examples for Tracxn Scraper")
    print("=" * 60)
    
    # Choose which example to run
    print("\nAvailable examples:")
    print("1. Basic audio CAPTCHA")
    print("2. Fallback strategy (audio → image)")
    print("3. Standard login (default)")
    print("4. Custom retry logic")
    
    choice = input("\nEnter example number (1-4): ").strip()
    
    if choice == "1":
        asyncio.run(example_audio_captcha())
    elif choice == "2":
        asyncio.run(example_fallback_strategy())
    elif choice == "3":
        asyncio.run(example_standard_login())
    elif choice == "4":
        asyncio.run(example_with_custom_settings())
    else:
        print("Invalid choice. Running basic audio CAPTCHA example...")
        asyncio.run(example_audio_captcha())
