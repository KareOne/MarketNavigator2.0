"""
API Routes برای مدیریت صف هشتگ‌ها
"""

from flask import Blueprint, request, jsonify
from flask_restx import Resource
from config.config import get_db_connection, hashtag_ns
from utils.logger import bot_logger
from core.scheduler.worker import hashtag_worker
from api.models.swagger import (
    hashtag_queue_input, 
    queue_response, 
    hashtag_full_status, 
    hashtag_queue_list,
    worker_status_model
)

hashtag_bp = Blueprint('hashtag', __name__)


@hashtag_ns.route('/queue')
class QueueHashtag(Resource):
    @hashtag_ns.expect(hashtag_queue_input)
    @hashtag_ns.marshal_with(queue_response)
    @hashtag_ns.doc('افزودن هشتگ به صف پردازش')
    def post(self):
        """افزودن هشتگ به صف برای پردازش توسط Worker"""
        return queue_hashtag()


@hashtag_bp.route('/api/hashtag/queue', methods=['POST'])
def queue_hashtag():
    """
    افزودن هشتگ به صف
    Body: {
        "hashtag": "python",
        "max_posts": 10,
        "max_comments": 5
    }
    """
    try:
        data = request.get_json()
        hashtag = data.get("hashtag")
        max_posts = data.get("max_posts", 5)
        max_comments = data.get("max_comments", 5)
        
        if not hashtag:
            return jsonify({
                "status": "error",
                "message": "Hashtag is required"
            }), 400
        
        # حذف # از ابتدای هشتگ اگر وجود داشت
        hashtag = hashtag.strip()
        if hashtag.startswith('#'):
            hashtag = hashtag[1:]
        
        # چک کردن تکراری بودن
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, status FROM hashtags_queue WHERE hashtag = %s AND status IN ('pending', 'processing') LIMIT 1",
            (hashtag,)
        )
        existing = cursor.fetchone()
        
        if existing:
            cursor.close()
            conn.close()
            return jsonify({
                "status": "info",
                "message": f"Hashtag '{hashtag}' is already in queue",
                "queue_id": existing['id'],
                "queue_status": existing['status']
            }), 200
        
        # ذخیره در صف
        cursor.execute(
            "INSERT INTO hashtags_queue (hashtag, max_posts, max_comments, status) VALUES (%s, %s, %s, 'pending')",
            (hashtag, max_posts, max_comments)
        )
        conn.commit()
        queue_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        bot_logger.info(f"✅ Hashtag '{hashtag}' added to queue with ID {queue_id}")
        
        return jsonify({
            "status": "success",
            "message": f"Hashtag '{hashtag}' added to queue successfully",
            "queue_id": queue_id,
            "data": {
                "hashtag": hashtag,
                "max_posts": max_posts,
                "max_comments": max_comments
            }
        }), 200
        
    except Exception as e:
        bot_logger.error(f"❌ Error adding hashtag to queue: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@hashtag_ns.route('/worker/status')
class WorkerStatusResource(Resource):
    @hashtag_ns.marshal_with(worker_status_model)
    @hashtag_ns.doc('دریافت وضعیت Worker و آمار صف‌ها')
    def get(self):
        """دریافت وضعیت فعلی Worker و آمار کامل صف‌ها"""
        return worker_status()


@hashtag_bp.route('/api/worker/status', methods=['GET'])
def worker_status():
    """دریافت وضعیت Worker و صف"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # آمار هشتگ‌ها
        cursor.execute("SELECT COUNT(*) as count FROM hashtags_queue WHERE status = 'pending'")
        pending_hashtags = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM hashtags_queue WHERE status = 'processing'")
        processing_hashtags = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM hashtags_queue WHERE status = 'completed'")
        completed_hashtags = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM hashtags_queue WHERE status = 'failed'")
        failed_hashtags = cursor.fetchone()['count']
        
        # آمار لینک‌ها
        cursor.execute("SELECT COUNT(*) as count FROM linkdeen_posts WHERE analyzed = 0 AND analysis_status = 'pending'")
        pending_links = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM linkdeen_posts WHERE analysis_status = 'processing'")
        processing_links = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM linkdeen_posts WHERE analyzed = 1")
        completed_links = cursor.fetchone()['count']
        
        cursor.close()
        conn.close()
        
        # وضعیت Worker
        worker_info = hashtag_worker.get_status()
        
        return jsonify({
            "status": "success",
            "data": {
                "worker": {
                    "is_running": worker_info['is_running'],
                    "is_processing": worker_info['is_processing'],
                    "current_task_type": worker_info['current_task_type'],
                    "current_task_id": worker_info['current_task_id']
                },
                "hashtags_queue": {
                    "pending": pending_hashtags,
                    "processing": processing_hashtags,
                    "completed": completed_hashtags,
                    "failed": failed_hashtags,
                    "total": pending_hashtags + processing_hashtags + completed_hashtags + failed_hashtags
                },
                "links_analysis": {
                    "pending": pending_links,
                    "processing": processing_links,
                    "completed": completed_links,
                    "total": pending_links + processing_links + completed_links
                }
            }
        }), 200
        
    except Exception as e:
        bot_logger.error(f"❌ Error getting worker status: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@hashtag_ns.route('/queue/list')
class ListQueueResource(Resource):
    @hashtag_ns.marshal_with(hashtag_queue_list)
    @hashtag_ns.doc('لیست صف هشتگ‌ها', params={
        'status': 'فیلتر بر اساس وضعیت (pending, processing, completed, failed)',
        'limit': 'تعداد نتایج (پیش‌فرض: 50)'
    })
    def get(self):
        """دریافت لیست هشتگ‌های موجود در صف"""
        return list_queue()


@hashtag_bp.route('/api/hashtag/queue/list', methods=['GET'])
def list_queue():
    """
    لیست صف هشتگ‌ها
    Query params: ?status=pending&limit=50
    """
    try:
        status = request.args.get('status')  # pending, processing, completed, failed
        limit = request.args.get('limit', 50, type=int)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if status:
            cursor.execute(
                "SELECT * FROM hashtags_queue WHERE status = %s ORDER BY created_at DESC LIMIT %s",
                (status, limit)
            )
        else:
            cursor.execute(
                "SELECT * FROM hashtags_queue ORDER BY created_at DESC LIMIT %s",
                (limit,)
            )
        
        queue_items = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({
            "status": "success",
            "count": len(queue_items),
            "data": queue_items
        }), 200
        
    except Exception as e:
        bot_logger.error(f"❌ Error listing queue: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@hashtag_bp.route('/api/hashtag/<int:queue_id>', methods=['GET'])
def get_hashtag_details(queue_id):
    """دریافت جزئیات یک هشتگ خاص و پست‌های آن"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # اطلاعات هشتگ
        cursor.execute("SELECT * FROM hashtags_queue WHERE id = %s", (queue_id,))
        hashtag_info = cursor.fetchone()
        
        if not hashtag_info:
            cursor.close()
            conn.close()
            return jsonify({
                "status": "error",
                "message": "Hashtag not found"
            }), 404
        
        # پست‌های مربوط به این هشتگ
        cursor.execute(
            "SELECT * FROM linkdeen_posts WHERE hashtag_id = %s ORDER BY id DESC",
            (queue_id,)
        )
        posts = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "status": "success",
            "data": {
                "hashtag": hashtag_info,
                "posts": posts,
                "posts_count": len(posts)
            }
        }), 200
        
    except Exception as e:
        bot_logger.error(f"❌ Error getting hashtag details: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@hashtag_bp.route('/api/hashtag/<int:queue_id>/retry', methods=['POST'])
def retry_failed_hashtag(queue_id):
    """تلاش مجدد برای هشتگ‌های failed"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # چک کردن وضعیت
        cursor.execute("SELECT status FROM hashtags_queue WHERE id = %s", (queue_id,))
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            conn.close()
            return jsonify({
                "status": "error",
                "message": "Hashtag not found"
            }), 404
        
        if result['status'] != 'failed':
            cursor.close()
            conn.close()
            return jsonify({
                "status": "error",
                "message": f"Hashtag status is '{result['status']}', only 'failed' can be retried"
            }), 400
        
        # بازگشت به pending
        cursor.execute(
            "UPDATE hashtags_queue SET status = 'pending', error_message = NULL WHERE id = %s",
            (queue_id,)
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        bot_logger.info(f"♻️ Hashtag ID {queue_id} set to pending for retry")
        
        return jsonify({
            "status": "success",
            "message": f"Hashtag ID {queue_id} queued for retry"
        }), 200
        
    except Exception as e:
        bot_logger.error(f"❌ Error retrying hashtag: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@hashtag_ns.route('/<int:queue_id>/status')
class HashtagStatusResource(Resource):
    @hashtag_ns.marshal_with(hashtag_full_status)
    @hashtag_ns.doc('دریافت وضعیت کامل هشتگ و پست‌های جمع‌آوری شده')
    def get(self, queue_id):
        """دریافت وضعیت کامل یک هشتگ شامل تمام پست‌ها و کامنت‌ها"""
        return get_hashtag_status(queue_id)


@hashtag_bp.route('/api/hashtag/<int:queue_id>/status', methods=['GET'])
def get_hashtag_status(queue_id):
    """
    🔹 دریافت وضعیت کامل یک هشتگ شامل صف و تمام پست‌های جمع‌آوری شده
    
    Response:
    {
        "status": "success",
        "data": {
            "queue": {...},
            "posts": [...],
            "posts_count": 10,
            "comments_count": 45
        }
    }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1️⃣ اطلاعات صف
        cursor.execute("""
            SELECT id, hashtag, max_posts, max_comments, user_id, status, 
                   error_message, created_at, started_at, completed_at
            FROM hashtags_queue 
            WHERE id = %s
        """, (queue_id,))
        
        queue_data = cursor.fetchone()
        
        if not queue_data:
            cursor.close()
            conn.close()
            return jsonify({
                "status": "error",
                "message": f"Hashtag با queue_id {queue_id} یافت نشد"
            }), 404
        
        # 2️⃣ پست‌های مربوط به این هشتگ
        posts_data = []
        comments_count = 0
        
        if queue_data['status'] in ['completed', 'processing']:
            cursor.execute("""
                SELECT id, post_link, caption, reactions, comments, username, 
                       analyzed, analysis_status, created_at
                FROM linkdeen_posts 
                WHERE hashtag_id = %s
                ORDER BY id DESC
            """, (queue_id,))
            
            posts = cursor.fetchall()
            
            for post in posts:
                # شمردن کامنت‌های هر پست
                cursor.execute(
                    "SELECT COUNT(*) as count FROM linkdeen_comments WHERE linkdeen_post_id = %s",
                    (post['id'],)
                )
                post_comments_count = cursor.fetchone()['count']
                comments_count += post_comments_count
                
                posts_data.append({
                    "post_id": post['id'],
                    "post_link": post.get('post_link'),
                    "caption": post.get('caption'),
                    "reactions": post.get('reactions'),
                    "comments": post.get('comments'),
                    "username": post.get('username'),
                    "analyzed": post.get('analyzed'),
                    "analysis_status": post.get('analysis_status'),
                    "created_at": str(post['created_at']) if post.get('created_at') else None,
                    "comments_count": post_comments_count
                })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "status": "success",
            "data": {
                "queue": {
                    "id": queue_data['id'],
                    "hashtag": queue_data['hashtag'],
                    "max_posts": queue_data['max_posts'],
                    "max_comments": queue_data['max_comments'],
                    "user_id": queue_data.get('user_id'),
                    "status": queue_data['status'],
                    "error_message": queue_data.get('error_message'),
                    "created_at": str(queue_data['created_at']) if queue_data.get('created_at') else None,
                    "started_at": str(queue_data['started_at']) if queue_data.get('started_at') else None,
                    "completed_at": str(queue_data['completed_at']) if queue_data.get('completed_at') else None
                },
                "posts": posts_data,
                "posts_count": len(posts_data),
                "total_comments_count": comments_count
            }
        }), 200
        
    except Exception as e:
        bot_logger.error(f"❌ Error getting hashtag status: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@hashtag_bp.route('/api/hashtag/<int:queue_id>/full', methods=['GET'])
def get_hashtag_full_results(queue_id):
    """
    🎯 دریافت نتایج کامل هشتگ شامل تمام پست‌ها و تمام کامنت‌های هر پست
    
    این endpoint برای دریافت نتیجه نهایی استفاده می‌شود
    
    Response:
    {
        "status": "success",
        "data": {
            "hashtag": "python",
            "queue_status": "completed",
            "posts": [
                {
                    "post_link": "...",
                    "caption": "...",
                    "reactions": "123",
                    "username": "...",
                    "comments": [
                        {
                            "commenter": "user1",
                            "comment_text": "Great post!"
                        }
                    ]
                }
            ]
        }
    }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1️⃣ اطلاعات صف
        cursor.execute("""
            SELECT id, hashtag, status, max_posts, max_comments, created_at, completed_at
            FROM hashtags_queue 
            WHERE id = %s
        """, (queue_id,))
        
        queue_data = cursor.fetchone()
        
        if not queue_data:
            cursor.close()
            conn.close()
            return jsonify({
                "status": "error",
                "message": f"هشتگ با شناسه {queue_id} یافت نشد"
            }), 404
        
        # 2️⃣ پست‌ها با کامنت‌های کامل
        cursor.execute("""
            SELECT id, post_link, caption, reactions, comments, username, created_at
            FROM linkdeen_posts 
            WHERE hashtag_id = %s
            ORDER BY id DESC
        """, (queue_id,))
        
        posts = cursor.fetchall()
        posts_with_comments = []
        
        for post in posts:
            # دریافت کامنت‌های هر پست
            cursor.execute("""
                SELECT commenter, comment_text, created_at
                FROM linkdeen_comments 
                WHERE linkdeen_post_id = %s
                ORDER BY id ASC
            """, (post['id'],))
            
            comments = cursor.fetchall()
            
            posts_with_comments.append({
                "post_id": post['id'],
                "post_link": post.get('post_link'),
                "caption": post.get('caption'),
                "reactions": post.get('reactions'),
                "comments_count": post.get('comments'),
                "username": post.get('username'),
                "created_at": str(post['created_at']) if post.get('created_at') else None,
                "comments": [
                    {
                        "commenter": c.get('commenter'),
                        "comment_text": c.get('comment_text'),
                        "created_at": str(c['created_at']) if c.get('created_at') else None
                    }
                    for c in comments
                ]
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "status": "success",
            "data": {
                "hashtag": queue_data['hashtag'],
                "queue_id": queue_data['id'],
                "queue_status": queue_data['status'],
                "max_posts": queue_data['max_posts'],
                "max_comments": queue_data['max_comments'],
                "created_at": str(queue_data['created_at']) if queue_data.get('created_at') else None,
                "completed_at": str(queue_data['completed_at']) if queue_data.get('completed_at') else None,
                "total_posts": len(posts_with_comments),
                "posts": posts_with_comments
            }
        }), 200
        
    except Exception as e:
        bot_logger.error(f"❌ Error getting full hashtag results: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

