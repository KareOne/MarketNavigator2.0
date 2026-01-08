"""
Background Worker برای پردازش صف هشتگ‌ها و لینک‌ها
این Worker به صورت مستقل و متوالی (یکی یکی) task‌ها را پردازش می‌کند
"""

import time
import threading
from datetime import datetime
from config.config import get_db_connection
from core.automation.hashtag import get_post2
from core.automation.page_scraper import get_page2
from utils.logger import bot_logger

# قفل سراسری برای جلوگیری از اجرای همزمان
worker_lock = threading.Lock()
is_processing = False


class HashtagWorker:
    """Worker برای پردازش صف هشتگ‌ها، صفحات و لینک‌ها (به‌صورت متوالی)"""

    def __init__(self):
        self.is_running = False
        self.worker_thread = None
        self.current_task_type = None  # 'hashtag' | 'page' | 'link'
        self.current_task_id = None

    def start(self):
        """شروع Worker در background"""
        if self.is_running:
            bot_logger.warning("⚠️ Worker already running!")
            return

        self.is_running = True
        self.worker_thread = threading.Thread(target=self._process_loop, daemon=True)
        self.worker_thread.start()
        bot_logger.info("✅ Hashtag Worker started successfully")

    def stop(self):
        """توقف Worker"""
        self.is_running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=10)
        bot_logger.info("🛑 Hashtag Worker stopped")

    def get_status(self):
        """دریافت وضعیت فعلی Worker"""
        return {
            "is_running": self.is_running,
            "is_processing": is_processing,
            "current_task_type": self.current_task_type,
            "current_task_id": self.current_task_id,
        }

    def _process_loop(self):
        """حلقه اصلی پردازش - یکی یکی"""
        global is_processing

        bot_logger.info("🔄 Worker loop started")

        while self.is_running:
            try:
                # بررسی قفل - فقط یک task در یک زمان
                with worker_lock:
                    if is_processing:
                        time.sleep(5)
                        continue
                    is_processing = True

                try:
                    # 1) Hashtags first
                    hashtag_task = self._get_pending_hashtag()
                    if hashtag_task:
                        self._process_hashtag(hashtag_task)
                        time.sleep(2)
                        continue

                    # 2) Keywords second
                    keyword_task = self._get_pending_keyword()
                    if keyword_task:
                        self._process_keyword(keyword_task)
                        time.sleep(2)
                        continue

                    # 3) Pages next
                    page_task = self._get_pending_page()
                    if page_task:
                        self._process_page(page_task)
                        time.sleep(2)
                        continue

                    # 4) Links last
                    # link_task = self._get_pending_link()
                    # if link_task:
                    #     self._process_link(link_task)
                    #     time.sleep(2)
                    #     continue

                    bot_logger.info("⏳ No pending tasks. Waiting 30 seconds...")
                    time.sleep(30)

                finally:
                    is_processing = False
                    self.current_task_type = None
                    self.current_task_id = None

            except Exception as e:
                bot_logger.error(f"❌ Critical error in Worker loop: {e}")
                is_processing = False
                time.sleep(10)

    def _get_pending_hashtag(self):
        """دریافت اولین هشتگ pending از صف"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, hashtag, max_posts, max_comments, user_id FROM hashtags_queue WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1"
            )
            task = cursor.fetchone()
            cursor.close()
            conn.close()
            return task
        except Exception as e:
            bot_logger.error(f"❌ Error fetching pending hashtag: {e}")
            return None

    def _get_pending_keyword(self):
        """دریافت اولین کلمه کلیدی pending از صف"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, keyword, max_posts, max_comments, user_id FROM keywords_queue WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1"
            )
            task = cursor.fetchone()
            cursor.close()
            conn.close()
            return task
        except Exception as e:
            bot_logger.error(f"❌ Error fetching pending keyword: {e}")
            return None

    def _get_pending_page(self):
        """دریافت اولین Page pending از صف"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, page_name, user_id FROM pages_queue WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1"
            )
            task = cursor.fetchone()
            cursor.close()
            conn.close()
            return task
        except Exception as e:
            bot_logger.error(f"❌ Error fetching pending page: {e}")
            return None

    def _get_pending_link(self):
        """دریافت اولین لینک تحلیل نشده"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM linkdeen_posts WHERE analyzed = 0 AND analysis_status = 'pending' ORDER BY id ASC LIMIT 1"
            )
            task = cursor.fetchone()
            cursor.close()
            conn.close()
            return task
        except Exception as e:
            bot_logger.error(f"❌ Error fetching pending link: {e}")
            return None

    def _process_hashtag(self, task):
        """پردازش یک هشتگ - استخراج پست‌ها"""
        hashtag_id = task['id']
        hashtag = task['hashtag']
        max_posts = task['max_posts']
        max_comments = task['max_comments']
        user_id = task.get('user_id')

        self.current_task_type = 'hashtag'
        self.current_task_id = hashtag_id

        bot_logger.info(f"🔄 Processing hashtag: '{hashtag}' (ID: {hashtag_id})")

        conn = None
        cursor = None

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE hashtags_queue SET status = 'processing', started_at = NOW() WHERE id = %s",
                (hashtag_id,)
            )
            conn.commit()
            cursor.close()
            conn.close()

            posts = get_post2(hashtag, max_posts, max_comments, hashtag_id, user_id)

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE hashtags_queue SET status = 'completed', completed_at = NOW() WHERE id = %s",
                (hashtag_id,)
            )
            conn.commit()

            bot_logger.info(f"✅ Hashtag '{hashtag}' completed successfully ({len(posts)} posts)")

        except Exception as e:
            bot_logger.error(f"❌ Error processing hashtag '{hashtag}': {e}")
            try:
                # ایجاد connection و cursor جدید برای ذخیره خطا
                conn = get_db_connection()
                cursor = conn.cursor()

                error_msg = str(e)[:500]
                cursor.execute(
                    "UPDATE hashtags_queue SET status = 'failed', error_message = %s, completed_at = NOW() WHERE id = %s",
                    (error_msg, hashtag_id)
                )
                conn.commit()
                cursor.close()
                conn.close()
                bot_logger.info(f"📝 Error saved to database for hashtag ID {hashtag_id}")
            except Exception as db_error:
                bot_logger.error(f"❌ Failed to save error to database: {db_error}")
        finally:
            # اطمینان از بستن منابع
            try:
                if cursor and not cursor.closed:
                    cursor.close()
            except:
                pass
            try:
                if conn:
                    conn.close()
            except:
                pass

    def _process_keyword(self, task):
        """پردازش یک کلمه کلیدی - استخراج پست‌ها"""
        from core.automation.hashtag import get_keyword_posts
        
        keyword_id = task['id']
        keyword = task['keyword']
        max_posts = task['max_posts']
        max_comments = task['max_comments']
        user_id = task.get('user_id')

        self.current_task_type = 'keyword'
        self.current_task_id = keyword_id

        bot_logger.info(f"🔄 Processing keyword: '{keyword}' (ID: {keyword_id})")

        conn = None
        cursor = None

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE keywords_queue SET status = 'processing', started_at = NOW() WHERE id = %s",
                (keyword_id,)
            )
            conn.commit()
            cursor.close()
            conn.close()

            posts = get_keyword_posts(keyword, max_posts, max_comments, keyword_id, user_id)

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE keywords_queue SET status = 'completed', completed_at = NOW() WHERE id = %s",
                (keyword_id,)
            )
            conn.commit()

            bot_logger.info(f"✅ Keyword '{keyword}' completed successfully ({len(posts)} posts)")

        except Exception as e:
            bot_logger.error(f"❌ Error processing keyword '{keyword}': {e}")
            try:
                # ایجاد connection و cursor جدید برای ذخیره خطا
                conn = get_db_connection()
                cursor = conn.cursor()

                error_msg = str(e)[:500]
                cursor.execute(
                    "UPDATE keywords_queue SET status = 'failed', error_message = %s, completed_at = NOW() WHERE id = %s",
                    (error_msg, keyword_id)
                )
                conn.commit()
                cursor.close()
                conn.close()
                bot_logger.info(f"📝 Error saved to database for keyword ID {keyword_id}")
            except Exception as db_error:
                bot_logger.error(f"❌ Failed to save error to database: {db_error}")
        finally:
            # اطمینان از بستن منابع
            try:
                if cursor and not cursor.closed:
                    cursor.close()
            except:
                pass
            try:
                if conn:
                    conn.close()
            except:
                pass

    def _process_page(self, task):
        """پردازش یک صفحه شرکت"""
        page_queue_id = task['id']
        page_name = task['page_name']
        user_id = task.get('user_id')

        self.current_task_type = 'page'
        self.current_task_id = page_queue_id

        bot_logger.info(f"🏢 Processing page: '{page_name}' (Queue ID: {page_queue_id})")

        conn = None
        cursor = None

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE pages_queue SET status = 'processing', started_at = NOW() WHERE id = %s",
                (page_queue_id,)
            )
            conn.commit()
            cursor.close()
            conn.close()

            page_data = get_page2(page_name, page_queue_id=page_queue_id, user_id=user_id)

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE pages_queue SET status = 'completed', completed_at = NOW() WHERE id = %s",
                (page_queue_id,)
            )
            conn.commit()

            bot_logger.info(f"✅ Page '{page_name}' completed successfully")

        except Exception as e:
            bot_logger.error(f"❌ Error processing page '{page_name}': {e}")
            try:
                # ایجاد connection و cursor جدید برای ذخیره خطا
                conn = get_db_connection()
                cursor = conn.cursor()

                error_msg = str(e)[:500]
                cursor.execute(
                    "UPDATE pages_queue SET status = 'failed', error_message = %s, completed_at = NOW() WHERE id = %s",
                    (error_msg, page_queue_id)
                )
                conn.commit()
                cursor.close()
                conn.close()
                bot_logger.info(f"📝 Error saved to database for page queue ID {page_queue_id}")
            except Exception as db_error:
                bot_logger.error(f"❌ Failed to save error to database: {db_error}")
        finally:
            # اطمینان از بستن منابع
            try:
                if cursor and not cursor.closed:
                    cursor.close()
            except:
                pass
            try:
                if conn:
                    conn.close()
            except:
                pass

    def _process_link(self, task):
        """پردازش یک لینک - تحلیل محتوا"""
        post_id = task['id']
        post_link = task.get('post_link', 'N/A')

        self.current_task_type = 'link'
        self.current_task_id = post_id

        bot_logger.info(f"🔍 Analyzing link: {post_link} (ID: {post_id})")

        conn = None
        cursor = None

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE linkdeen_posts SET analysis_status = 'processing' WHERE id = %s",
                (post_id,)
            )
            conn.commit()
            cursor.close()
            conn.close()

            time.sleep(2)

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE linkdeen_posts SET analyzed = 1, analysis_status = 'completed' WHERE id = %s",
                (post_id,)
            )
            conn.commit()

            bot_logger.info(f"✅ Link ID {post_id} analyzed successfully")

        except Exception as e:
            bot_logger.error(f"❌ Error analyzing link ID {post_id}: {e}")
            try:
                if not conn:
                    conn = get_db_connection()
                if not cursor or cursor.closed:
                    cursor = conn.cursor()

                error_msg = str(e)[:500]
                cursor.execute(
                    "UPDATE linkdeen_posts SET analysis_status = 'failed', analysis_error = %s WHERE id = %s",
                    (error_msg, post_id)
                )
                conn.commit()
            except Exception as db_error:
                bot_logger.error(f"❌ Failed to save error to database: {db_error}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()


# ایجاد نمونه سراسری Worker
hashtag_worker = HashtagWorker()
