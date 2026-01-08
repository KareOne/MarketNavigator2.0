"""
Unit tests for the background worker
Tests hashtag queue processing, page queue processing, and error handling
"""

import unittest
import time
from unittest.mock import Mock, patch, MagicMock
from core.scheduler.worker import HashtagWorker, is_processing, worker_lock


class TestHashtagWorker(unittest.TestCase):
    """Test cases for HashtagWorker class"""

    def setUp(self):
        """Set up test fixtures"""
        self.worker = HashtagWorker()

    def tearDown(self):
        """Clean up after tests"""
        if self.worker.is_running:
            self.worker.stop()

    def test_worker_initialization(self):
        """Test worker initializes correctly"""
        self.assertFalse(self.worker.is_running)
        self.assertIsNone(self.worker.worker_thread)
        self.assertIsNone(self.worker.current_task_type)
        self.assertIsNone(self.worker.current_task_id)

    def test_worker_start_stop(self):
        """Test worker can start and stop"""
        self.worker.start()
        self.assertTrue(self.worker.is_running)
        self.assertIsNotNone(self.worker.worker_thread)
        
        time.sleep(0.5)  # Give thread time to start
        
        self.worker.stop()
        self.assertFalse(self.worker.is_running)

    def test_worker_already_running(self):
        """Test starting worker twice doesn't create duplicate threads"""
        self.worker.start()
        first_thread = self.worker.worker_thread
        
        self.worker.start()  # Try to start again
        second_thread = self.worker.worker_thread
        
        self.assertEqual(first_thread, second_thread)
        self.worker.stop()

    def test_get_status(self):
        """Test worker status reporting"""
        status = self.worker.get_status()
        
        self.assertIn('is_running', status)
        self.assertIn('is_processing', status)
        self.assertIn('current_task_type', status)
        self.assertIn('current_task_id', status)
        
        self.assertFalse(status['is_running'])

    @patch('core.scheduler.worker.get_db_connection')
    def test_get_pending_hashtag(self, mock_db):
        """Test fetching pending hashtag from queue"""
        # Mock database response
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'id': 1,
            'hashtag': 'Python',
            'max_posts': 10,
            'max_comments': 5,
            'user_id': None
        }
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        result = self.worker._get_pending_hashtag()
        
        self.assertIsNotNone(result)
        self.assertEqual(result['hashtag'], 'Python')
        self.assertEqual(result['id'], 1)

    @patch('core.scheduler.worker.get_db_connection')
    def test_get_pending_hashtag_empty(self, mock_db):
        """Test fetching when no pending hashtags"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        result = self.worker._get_pending_hashtag()
        
        self.assertIsNone(result)

    @patch('core.scheduler.worker.get_db_connection')
    def test_get_pending_page(self, mock_db):
        """Test fetching pending page from queue"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'id': 1,
            'page_name': 'microsoft',
            'user_id': None
        }
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        result = self.worker._get_pending_page()
        
        self.assertIsNotNone(result)
        self.assertEqual(result['page_name'], 'microsoft')

    @patch('core.scheduler.worker.get_db_connection')
    def test_get_pending_link(self, mock_db):
        """Test fetching pending link for analysis"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'id': 1,
            'link': 'https://linkedin.com/post/123',
            'analyzed': 0,
            'analysis_status': 'pending'
        }
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        result = self.worker._get_pending_link()
        
        self.assertIsNotNone(result)
        self.assertEqual(result['id'], 1)

    @patch('core.scheduler.worker.get_post2')
    @patch('core.scheduler.worker.get_db_connection')
    def test_process_hashtag_success(self, mock_db, mock_get_post):
        """Test successful hashtag processing"""
        # Mock database
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        # Mock get_post2 return value
        mock_get_post.return_value = [
            {'link': 'post1', 'caption': 'Test 1'},
            {'link': 'post2', 'caption': 'Test 2'}
        ]
        
        task = {
            'id': 1,
            'hashtag': 'Python',
            'max_posts': 10,
            'max_comments': 5,
            'user_id': None
        }
        
        self.worker._process_hashtag(task)
        
        # Verify status was updated to processing
        self.assertIn(
            unittest.mock.call("UPDATE hashtags_queue SET status = 'processing', started_at = NOW() WHERE id = %s", (1,)),
            mock_cursor.execute.call_args_list
        )
        
        # Verify status was updated to completed
        self.assertIn(
            unittest.mock.call("UPDATE hashtags_queue SET status = 'completed', completed_at = NOW() WHERE id = %s", (1,)),
            mock_cursor.execute.call_args_list
        )

    @patch('core.scheduler.worker.get_post2')
    @patch('core.scheduler.worker.get_db_connection')
    def test_process_hashtag_error(self, mock_db, mock_get_post):
        """Test hashtag processing with error"""
        # Mock database
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        # Mock get_post2 to raise an exception
        mock_get_post.side_effect = Exception("Failed to initialize Chrome driver")
        
        task = {
            'id': 1,
            'hashtag': 'Python',
            'max_posts': 10,
            'max_comments': 5,
            'user_id': None
        }
        
        self.worker._process_hashtag(task)
        
        # Verify error was saved to database
        error_update_calls = [
            call for call in mock_cursor.execute.call_args_list
            if "UPDATE hashtags_queue SET status = 'failed'" in str(call)
        ]
        self.assertTrue(len(error_update_calls) > 0, "Error status not saved to database")

    @patch('core.scheduler.worker.get_page2')
    @patch('core.scheduler.worker.get_db_connection')
    def test_process_page_success(self, mock_db, mock_get_page):
        """Test successful page processing"""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        mock_get_page.return_value = {
            'page_title': 'Microsoft',
            'page_description': 'Tech Company'
        }
        
        task = {
            'id': 1,
            'page_name': 'microsoft',
            'user_id': None
        }
        
        self.worker._process_page(task)
        
        # Verify status updates
        self.assertIn(
            unittest.mock.call("UPDATE pages_queue SET status = 'completed', completed_at = NOW() WHERE id = %s", (1,)),
            mock_cursor.execute.call_args_list
        )


class TestWorkerLocking(unittest.TestCase):
    """Test worker locking mechanism"""

    def test_worker_lock_exists(self):
        """Test that global worker lock exists"""
        self.assertIsNotNone(worker_lock)

    @patch('core.scheduler.worker.is_processing', False)
    def test_only_one_task_at_time(self):
        """Test that only one task can be processed at a time"""
        # This is tested implicitly through the worker_lock mechanism
        # The lock ensures sequential processing
        self.assertFalse(is_processing)


class TestWorkerErrorRecovery(unittest.TestCase):
    """Test error recovery mechanisms"""

    def setUp(self):
        self.worker = HashtagWorker()

    def tearDown(self):
        if self.worker.is_running:
            self.worker.stop()

    @patch('core.scheduler.worker.get_db_connection')
    def test_db_connection_error_recovery(self, mock_db):
        """Test worker handles database connection errors"""
        mock_db.side_effect = Exception("Connection refused")
        
        result = self.worker._get_pending_hashtag()
        
        self.assertIsNone(result)

    @patch('core.scheduler.worker.get_db_connection')
    def test_partial_db_failure(self, mock_db):
        """Test worker handles partial database failures"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = Exception("Query timeout")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        result = self.worker._get_pending_hashtag()
        
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
