"""
Unit tests for database operations
Tests database connections, queries, and queue management
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import pymysql


class TestDatabaseConnection(unittest.TestCase):
    """Test database connection functionality"""

    @patch('config.config.pymysql.connect')
    def test_get_db_connection_success(self, mock_connect):
        """Test successful database connection"""
        from config.config import get_db_connection
        
        mock_conn = MagicMock()
        mock_conn.open = True
        mock_connect.return_value = mock_conn
        
        conn = get_db_connection()
        
        self.assertIsNotNone(conn)
        mock_connect.assert_called_once()

    @patch('config.config.pymysql.connect')
    def test_get_db_connection_retry(self, mock_connect):
        """Test database connection retry on closed connection"""
        from config.config import get_db_connection
        
        # First connection is closed, second is open
        mock_conn_closed = MagicMock()
        mock_conn_closed.open = False
        mock_conn_open = MagicMock()
        mock_conn_open.open = True
        
        mock_connect.side_effect = [mock_conn_closed, mock_conn_open]
        
        conn = get_db_connection()
        
        self.assertIsNotNone(conn)
        self.assertEqual(mock_connect.call_count, 2)

    @patch('config.config.pymysql.connect')
    def test_get_db_connection_failure(self, mock_connect):
        """Test database connection failure"""
        from config.config import get_db_connection
        
        mock_connect.side_effect = pymysql.err.OperationalError(2003, "Can't connect to MySQL server")
        
        with self.assertRaises(pymysql.err.OperationalError):
            get_db_connection()


class TestHashtagQueue(unittest.TestCase):
    """Test hashtag queue operations"""

    @patch('config.config.get_db_connection')
    def test_insert_hashtag_queue(self, mock_db):
        """Test inserting hashtag into queue"""
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 42
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        conn = mock_db()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO hashtags_queue (hashtag, max_posts, max_comments, status) VALUES (%s, %s, %s, %s)",
            ('Python', 10, 5, 'pending')
        )
        conn.commit()
        
        queue_id = cursor.lastrowid
        
        self.assertEqual(queue_id, 42)

    @patch('config.config.get_db_connection')
    def test_update_hashtag_status(self, mock_db):
        """Test updating hashtag status"""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        conn = mock_db()
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE hashtags_queue SET status = %s WHERE id = %s",
            ('processing', 1)
        )
        conn.commit()
        
        cursor.execute.assert_called_with(
            "UPDATE hashtags_queue SET status = %s WHERE id = %s",
            ('processing', 1)
        )

    @patch('config.config.get_db_connection')
    def test_fetch_pending_hashtags(self, mock_db):
        """Test fetching pending hashtags"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'hashtag': 'Python', 'status': 'pending'},
            {'id': 2, 'hashtag': 'Java', 'status': 'pending'}
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        conn = mock_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hashtags_queue WHERE status = 'pending'")
        results = cursor.fetchall()
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['hashtag'], 'Python')


class TestPageQueue(unittest.TestCase):
    """Test page queue operations"""

    @patch('config.config.get_db_connection')
    def test_insert_page_queue(self, mock_db):
        """Test inserting page into queue"""
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 10
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        conn = mock_db()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO pages_queue (page_name, status) VALUES (%s, %s)",
            ('microsoft', 'pending')
        )
        conn.commit()
        
        queue_id = cursor.lastrowid
        
        self.assertEqual(queue_id, 10)

    @patch('config.config.get_db_connection')
    def test_fetch_pending_pages(self, mock_db):
        """Test fetching pending pages"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'id': 1,
            'page_name': 'microsoft',
            'status': 'pending'
        }
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        conn = mock_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pages_queue WHERE status = 'pending' LIMIT 1")
        result = cursor.fetchone()
        
        self.assertIsNotNone(result)
        self.assertEqual(result['page_name'], 'microsoft')


class TestPostStorage(unittest.TestCase):
    """Test post data storage"""

    @patch('config.config.get_db_connection')
    def test_insert_post(self, mock_db):
        """Test inserting post into database"""
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 100
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        conn = mock_db()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO linkdeen_posts (link, caption, reactions) VALUES (%s, %s, %s)",
            ('https://linkedin.com/post/123', 'Test post', '10')
        )
        conn.commit()
        
        post_id = cursor.lastrowid
        
        self.assertEqual(post_id, 100)

    @patch('config.config.get_db_connection')
    def test_fetch_posts_by_hashtag(self, mock_db):
        """Test fetching posts by hashtag_id"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'link': 'post1', 'caption': 'Test 1'},
            {'id': 2, 'link': 'post2', 'caption': 'Test 2'}
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        conn = mock_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM linkdeen_posts WHERE hashtag_queue_id = %s", (1,))
        results = cursor.fetchall()
        
        self.assertEqual(len(results), 2)


class TestErrorHandling(unittest.TestCase):
    """Test database error handling"""

    @patch('config.config.get_db_connection')
    def test_save_error_to_queue(self, mock_db):
        """Test saving error message to queue"""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        conn = mock_db()
        cursor = conn.cursor()
        
        error_message = "Failed to initialize Chrome driver"
        cursor.execute(
            "UPDATE hashtags_queue SET status = %s, error_message = %s WHERE id = %s",
            ('failed', error_message, 1)
        )
        conn.commit()
        
        # Verify error was saved
        cursor.execute.assert_called_with(
            "UPDATE hashtags_queue SET status = %s, error_message = %s WHERE id = %s",
            ('failed', error_message, 1)
        )


if __name__ == '__main__':
    unittest.main()
