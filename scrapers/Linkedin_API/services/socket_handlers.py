"""
Socket Handlers برای مدیریت ارتباطات Real-time
این ماژول تمام event handler های Socket.IO را مدیریت می‌کند
"""

from flask_socketio import join_room, emit
from utils.logger import bot_logger
from config.config import get_db_connection, socketio


class SocketHandlers:
    """کلاس مدیریت Socket Event Handlers"""
    
    def __init__(self, socketio_instance):
        self.socketio = socketio_instance
        self._register_handlers()
    
    def _register_handlers(self):
        """ثبت تمام event handlers"""
        self.socketio.on_event('connect', self.on_connect)
        self.socketio.on_event('disconnect', self.on_disconnect)
        self.socketio.on_event('send_start_hashtag', self.handle_start_hashtag)
        self.socketio.on_event('send_start_page', self.handle_start_page)
        bot_logger.info("✅ Socket handlers ثبت شدند")
    
    def on_connect(self):
        """هنگام اتصال کاربر"""
        join_room("1")
        bot_logger.info("👤 کاربر جدید متصل شد")
    
    def on_disconnect(self):
        """هنگام قطع اتصال کاربر"""
        bot_logger.info("👤 کاربر قطع شد")
    
    def handle_start_hashtag(self, data):
        """
        Socket handler برای افزودن هشتگ به صف
        Worker خودش پردازش می‌کند
        """
        try:
            bot_logger.info("=" * 60)
            hashtag = data.get("hashtags")
            max_posts = data.get("post_count", 5)
            max_comments = data.get("comment_count", 5)
            
            bot_logger.info(f"📨 درخواست Socket برای هشتگ: {hashtag}")
            
            if not hashtag:
                self._emit_error("هشتگ الزامی است")
                return
            
            # حذف # از ابتدا
            hashtag = hashtag.strip()
            if hashtag.startswith('#'):
                hashtag = hashtag[1:]
            
            # ✅ افزودن مستقیم به صف (بدون چک تکراری)
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # ذخیره مستقیم در صف
            cursor.execute(
                "INSERT INTO hashtags_queue (hashtag, max_posts, max_comments, status) VALUES (%s, %s, %s, 'pending')",
                (hashtag, max_posts, max_comments)
            )
            conn.commit()
            queue_id = cursor.lastrowid
            cursor.close()
            conn.close()
            
            bot_logger.info(f"✅ هشتگ '{hashtag}' با ID {queue_id} در صف قرار گرفت")
            
            self._emit_queue_status(
                status="success",
                message=f"هشتگ '{hashtag}' در صف قرار گرفت و Worker به زودی پردازش می‌کند",
                queue_id=queue_id,
                data={
                    "hashtag": hashtag,
                    "max_posts": max_posts,
                    "max_comments": max_comments
                }
            )
            
        except Exception as e:
            bot_logger.error(f"❌ خطا در Socket handler (hashtag): {str(e)}")
            self._emit_error(str(e))
    
    def handle_start_page(self, data):
        """
        Socket handler برای افزودن صفحه به صف
        Worker خودش پردازش می‌کند
        """
        try:
            bot_logger.info("=" * 60)
            page = data.get("page")
            
            bot_logger.info(f"📨 درخواست Socket برای صفحه: {page}")
            
            if not page:
                self._emit_error("نام صفحه الزامی است")
                return
            
            # حذف URL اضافی اگر وجود دارد
            page = page.strip()
            if 'linkedin.com/company/' in page:
                page = page.split('linkedin.com/company/')[-1].rstrip('/')
            
            # ✅ افزودن مستقیم به صف (بدون چک تکراری)
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # ذخیره مستقیم در صف
            cursor.execute(
                "INSERT INTO pages_queue (page_name, status) VALUES (%s, 'pending')",
                (page,)
            )
            conn.commit()
            queue_id = cursor.lastrowid
            cursor.close()
            conn.close()
            
            bot_logger.info(f"✅ صفحه '{page}' با ID {queue_id} در صف قرار گرفت")
            
            self._emit_page_status(
                status="success",
                message=f"صفحه '{page}' در صف قرار گرفت و Worker به زودی پردازش می‌کند",
                queue_id=queue_id,
                data={
                    "page_name": page
                }
            )
            
        except Exception as e:
            bot_logger.error(f"❌ خطا در Socket handler (page): {str(e)}")
            self._emit_error(str(e))
    
    def _emit_queue_status(self, status, message, queue_id=None, queue_status=None, data=None):
        """ارسال وضعیت صف به کلاینت"""
        payload = {
            "status": status,
            "message": message
        }
        
        if queue_id is not None:
            payload["queue_id"] = queue_id
        
        if queue_status is not None:
            payload["queue_status"] = queue_status
        
        if data is not None:
            payload["data"] = data
        
        self.socketio.emit('queue_status', payload, to='1')
    
    def _emit_page_status(self, status, message, queue_id=None, data=None):
        """ارسال وضعیت صفحه به کلاینت"""
        payload = {
            "status": status,
            "message": message
        }
        
        if queue_id is not None:
            payload["queue_id"] = queue_id
        
        if data is not None:
            payload["data"] = data
        
        self.socketio.emit('page_status', payload, to='1')
    
    def _emit_error(self, message):
        """ارسال خطا به کلاینت"""
        self.socketio.emit('error', {
            "status": "error",
            "message": message
        }, to='1')
    
    def emit_progress(self, event_type, data):
        """
        ارسال پیشرفت پردازش به کلاینت
        برای استفاده در Worker و توابع اسکرپ
        
        Args:
            event_type: نوع رویداد (hashtag_progress, page_progress, post_collected, comment_collected, etc.)
            data: داده‌های مربوط به رویداد
        
        مثال:
            emit_progress('hashtag_progress', {
                'queue_id': 5,
                'status': 'processing',
                'current_post': 3,
                'total_posts': 10,
                'message': 'در حال پردازش پست 3 از 10'
            })
        """
        self.socketio.emit(event_type, data, to='1')
        bot_logger.debug(f"📤 Event '{event_type}' ارسال شد")
    
    def emit_hashtag_completed(self, queue_id, hashtag, total_posts, total_comments):
        """ارسال اطلاع تکمیل هشتگ"""
        self.socketio.emit('hashtag_completed', {
            'queue_id': queue_id,
            'hashtag': hashtag,
            'status': 'completed',
            'total_posts': total_posts,
            'total_comments': total_comments,
            'message': f'هشتگ {hashtag} با موفقیت پردازش شد'
        }, to='1')
        bot_logger.info(f"✅ اطلاع تکمیل هشتگ {hashtag} ارسال شد")
    
    def emit_hashtag_failed(self, queue_id, hashtag, error_message):
        """ارسال اطلاع خطا در پردازش هشتگ"""
        self.socketio.emit('hashtag_failed', {
            'queue_id': queue_id,
            'hashtag': hashtag,
            'status': 'failed',
            'error_message': error_message,
            'message': f'خطا در پردازش هشتگ {hashtag}'
        }, to='1')
        bot_logger.error(f"❌ اطلاع خطای هشتگ {hashtag} ارسال شد")
    
    def emit_page_completed(self, queue_id, page_name):
        """ارسال اطلاع تکمیل صفحه"""
        self.socketio.emit('page_completed', {
            'queue_id': queue_id,
            'page_name': page_name,
            'status': 'completed',
            'message': f'صفحه {page_name} با موفقیت پردازش شد'
        }, to='1')
        bot_logger.info(f"✅ اطلاع تکمیل صفحه {page_name} ارسال شد")
    
    def emit_page_failed(self, queue_id, page_name, error_message):
        """ارسال اطلاع خطا در پردازش صفحه"""
        self.socketio.emit('page_failed', {
            'queue_id': queue_id,
            'page_name': page_name,
            'status': 'failed',
            'error_message': error_message,
            'message': f'خطا در پردازش صفحه {page_name}'
        }, to='1')
        bot_logger.error(f"❌ اطلاع خطای صفحه {page_name} ارسال شد")


# ایجاد نمونه سراسری
socket_handlers = None


def initialize_socket_handlers(socketio_instance):
    """مقداردهی اولیه Socket Handlers"""
    global socket_handlers
    socket_handlers = SocketHandlers(socketio_instance)
    return socket_handlers


def get_socket_handlers():
    """دریافت نمونه Socket Handlers"""
    return socket_handlers
