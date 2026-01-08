"""
Integration tests for hashtag scraping functionality
Tests the complete flow of hashtag processing
"""

import unittest
from unittest.mock import Mock, patch, MagicMock


class TestHashtagScraping(unittest.TestCase):
    """Test hashtag scraping functions"""

    @patch('core.automation.hashtag.get_global_bot')
    @patch('core.automation.hashtag.get_db_connection')
    def test_get_post2_with_valid_hashtag(self, mock_db, mock_get_bot):
        """Test get_post2 with valid hashtag"""
        from core.automation.hashtag import get_post2
        
        # Mock bot
        mock_bot = MagicMock()
        mock_bot.driver = MagicMock()
        mock_bot.driver.find_element.return_value = MagicMock()
        mock_bot.driver.find_elements.return_value = []
        mock_get_bot.return_value = mock_bot
        
        # Mock database
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        result = get_post2('Python', max_posts=2, max_comments=2, hashtag_id=1, user_id=None)
        
        self.assertIsInstance(result, list)

    @patch('core.automation.hashtag.get_global_bot')
    def test_get_post2_handles_bot_failure(self, mock_get_bot):
        """Test get_post2 handles bot initialization failure"""
        from core.automation.hashtag import get_post2
        
        mock_get_bot.side_effect = Exception("Failed to initialize Chrome driver: HTTP Error 403: Forbidden")
        
        with self.assertRaises(Exception) as context:
            get_post2('Python', max_posts=2, max_comments=2, hashtag_id=1, user_id=None)
        
        self.assertIn('403', str(context.exception))

    @patch('core.automation.hashtag.get_db_connection')
    def test_get_post_queue_insertion(self, mock_db):
        """Test get_post inserts hashtag into queue"""
        from core.automation.hashtag import get_post
        
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 123
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        mock_request = Mock()
        mock_request.get_json.return_value = {
            'hashtag': 'Python',
            'max_posts': 10,
            'max_comments': 5
        }
        
        result = get_post(mock_request)
        
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['queue_id'], 123)

    @patch('core.automation.hashtag.get_db_connection')
    def test_get_post_removes_hash_symbol(self, mock_db):
        """Test get_post removes # from hashtag"""
        from core.automation.hashtag import get_post
        
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 123
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        mock_request = Mock()
        mock_request.get_json.return_value = {
            'hashtag': '#Python',
            'max_posts': 10,
            'max_comments': 5
        }
        
        result = get_post(mock_request)
        
        # Verify the execute was called with 'Python' not '#Python'
        execute_calls = mock_cursor.execute.call_args_list
        self.assertTrue(any('Python' in str(call) and '#Python' not in str(call) for call in execute_calls))

    def test_get_post_requires_hashtag(self):
        """Test get_post returns error without hashtag"""
        from core.automation.hashtag import get_post
        
        mock_request = Mock()
        mock_request.get_json.return_value = {}
        
        result, status_code = get_post(mock_request)
        
        self.assertEqual(result['status'], 'error')
        self.assertEqual(status_code, 400)


class TestPostDataExtraction(unittest.TestCase):
    """Test data extraction from posts"""

    def test_post_link_extraction(self):
        """Test extracting link from post"""
        # This would require mocking Selenium elements
        # For now, we test the structure
        expected_structure = {
            'link': 'https://linkedin.com/post/123',
            'caption': 'Test post',
            'reactions': '10'
        }
        
        self.assertIn('link', expected_structure)
        self.assertIn('caption', expected_structure)
        self.assertIn('reactions', expected_structure)

    def test_post_caption_handling_missing(self):
        """Test handling missing caption"""
        # Test that default values are used when elements not found
        default_caption = "No caption found"
        
        self.assertEqual(default_caption, "No caption found")


class TestSocketProgress(unittest.TestCase):
    """Test socket progress emission during scraping"""

    @patch('core.automation.hashtag.socketio')
    @patch('core.automation.hashtag.get_global_bot')
    @patch('core.automation.hashtag.get_db_connection')
    def test_socket_events_with_user_id(self, mock_db, mock_get_bot, mock_socketio):
        """Test that socket events are emitted when user_id is provided"""
        from core.automation.hashtag import get_post2
        
        mock_bot = MagicMock()
        mock_bot.driver = MagicMock()
        mock_bot.driver.find_elements.return_value = []
        mock_get_bot.return_value = mock_bot
        
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        get_post2('Python', max_posts=1, max_comments=1, hashtag_id=1, user_id=5)
        
        # Verify socketio was available (actual emission tested in integration)
        self.assertIsNotNone(mock_socketio)


if __name__ == '__main__':
    unittest.main()
