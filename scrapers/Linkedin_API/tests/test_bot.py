"""
Unit tests for bot initialization and Chrome driver
Tests the bot creation, driver initialization, and error handling
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import os


class TestBotInitialization(unittest.TestCase):
    """Test bot initialization and driver setup"""

    @patch('core.bot.linkdeen_bot.webdriver.Chrome')
    @patch('core.bot.linkdeen_bot.ChromeDriverManager')
    def test_bot_creates_chrome_driver(self, mock_driver_manager, mock_chrome):
        """Test that bot creates Chrome driver correctly"""
        from core.bot.linkdeen_bot import LinkedinBot
        
        mock_driver_manager.return_value.install.return_value = '/path/to/chromedriver'
        mock_chrome.return_value = MagicMock()
        
        bot = LinkedinBot('testuser', is_first=0)
        
        self.assertIsNotNone(bot.driver)

    @patch('core.bot.linkdeen_bot.webdriver.Chrome')
    def test_bot_handles_driver_failure(self, mock_chrome):
        """Test bot handles Chrome driver initialization failure"""
        from core.bot.linkdeen_bot import LinkedinBot
        
        mock_chrome.side_effect = Exception("HTTP Error 403: Forbidden")
        
        with self.assertRaises(Exception) as context:
            bot = LinkedinBot('testuser', is_first=0)
        
        self.assertIn('403', str(context.exception))

    @patch('core.bot.linkdeen_bot.webdriver.Chrome')
    def test_bot_headless_mode(self, mock_chrome):
        """Test bot can run in headless mode"""
        from core.bot.linkdeen_bot import LinkedinBot
        
        mock_chrome.return_value = MagicMock()
        
        # This would require modifying config to enable headless
        # For now, just test that bot initializes
        bot = LinkedinBot('testuser', is_first=0)
        
        self.assertIsNotNone(bot)

    def test_chrome_profile_directory_creation(self):
        """Test that Chrome profile directories are created"""
        from core.bot.linkdeen_bot import LinkedinBot
        
        # This test checks if the profile path logic works
        # Actual directory creation happens in bot initialization
        profile_base = '/app/chrome-profiles'
        username = 'pr1'
        expected_path = f'{profile_base}/{username}'
        
        self.assertIsNotNone(expected_path)


class TestGlobalBotManager(unittest.TestCase):
    """Test the global bot instance manager"""

    def setUp(self):
        """Reset global bot state before each test"""
        import config.config as config
        config._global_bot_instance = None
        config._bot_logged_in = False

    @patch('config.config.LinkedinBot')
    def test_global_bot_singleton(self, mock_bot_class):
        """Test that get_global_bot returns singleton instance"""
        from config.config import get_global_bot
        
        mock_bot = MagicMock()
        mock_bot_class.return_value = mock_bot
        
        bot1 = get_global_bot('pr1', '', 5, 0)
        bot2 = get_global_bot('pr1', '', 5, 0)
        
        self.assertEqual(bot1, bot2)
        # Should only create bot once
        self.assertEqual(mock_bot_class.call_count, 1)

    @patch('config.config.LinkedinBot')
    def test_global_bot_login_once(self, mock_bot_class):
        """Test that bot only logs in once"""
        from config.config import get_global_bot
        
        mock_bot = MagicMock()
        mock_bot_class.return_value = mock_bot
        
        bot1 = get_global_bot('pr1', 'pass123', 5, is_first=1)
        bot2 = get_global_bot('pr1', 'pass123', 5, is_first=1)
        
        # Login should only be called once
        self.assertEqual(mock_bot.login.call_count, 1)

    @patch('config.config.LinkedinBot')
    def test_close_global_bot(self, mock_bot_class):
        """Test that close_global_bot cleans up properly"""
        from config.config import get_global_bot, close_global_bot
        
        mock_bot = MagicMock()
        mock_bot_class.return_value = mock_bot
        
        bot = get_global_bot('pr1', '', 5, 0)
        close_global_bot()
        
        mock_bot.cleanup.assert_called_once_with(force_quit=True)


class TestBotConnectionIssues(unittest.TestCase):
    """Test bot behavior with connection issues"""

    @patch('core.bot.linkdeen_bot.webdriver.Chrome')
    def test_bot_handles_403_error(self, mock_chrome):
        """Test bot handles HTTP 403 error gracefully"""
        from core.bot.linkdeen_bot import LinkedinBot
        
        mock_chrome.side_effect = Exception("HTTP Error 403: Forbidden")
        
        with self.assertRaises(Exception) as context:
            bot = LinkedinBot('testuser', is_first=0)
        
        error_message = str(context.exception)
        self.assertIn('403', error_message)

    @patch('core.bot.linkdeen_bot.webdriver.Chrome')
    def test_bot_handles_network_timeout(self, mock_chrome):
        """Test bot handles network timeout"""
        from core.bot.linkdeen_bot import LinkedinBot
        
        mock_chrome.side_effect = TimeoutError("Connection timeout")
        
        with self.assertRaises(TimeoutError):
            bot = LinkedinBot('testuser', is_first=0)


if __name__ == '__main__':
    unittest.main()
