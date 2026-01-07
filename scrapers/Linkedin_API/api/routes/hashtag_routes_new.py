"""
API Routes برای مدیریت هشتگ‌ها
"""

from flask import request, jsonify
from flask_restx import Resource
from config.config import get_db_connection, hashtag_ns
from utils.logger import bot_logger
from core.automation.hashtag import get_post
from api.models.swagger import (
    hashtag_input_model,
    hashtag_queue_response,
    hashtag_data_input,
    hashtag_full_data_response,
    hashtag_list_response,
    worker_status_response
)


@hashtag_ns.route('/start/hashtag/')
class StartHashtag(Resource):
    @hashtag_ns.expect(hashtag_input_model)
    @hashtag_ns.marshal_with(hashtag_queue_response, code=200)
    @hashtag_ns.doc(
        description='این endpoint هشتگ را در صف ذخیره می‌کند و Worker به صورت خودکار پردازش می‌کند',
        responses={
            200: 'موفق',
            400: 'خطا در ورودی',
            500: 'خطای سرور'
        }
    )
    def post(self):
        """افزودن هشتگ به صف برای پردازش"""
        try:
            result = get_post(request)
            
            # اگر tuple برگشت (با status code)
            if isinstance(result, tuple):
                return result[0], result[1]
            
            return result, 200
            
        except Exception as e:
            bot_logger.error(f"❌ Error in start_hashtag: {e}")
            return {
                "status": "error",
                "message": str(e)
            }, 500


@hashtag_ns.route('/get-data/hashtag/')
class GetHashtagData(Resource):
    @hashtag_ns.expect(hashtag_data_input)
    @hashtag_ns.marshal_with(hashtag_full_data_response, code=200)
    @hashtag_ns.doc(
        description='دریافت وضعیت کامل یک هشتگ شامل تمام پست‌ها و کامنت‌ها',
        responses={
            200: 'موفق',
            400: 'خطا در ورودی',
            404: 'هشتگ یافت نشد',
            500: 'خطای سرور'
        }
    )
    def post(self):
        """دریافت اطلاعات کامل هشتگ با تمام پست‌ها و کامنت‌ها"""
        try:
            data = request.get_json()
            queue_id = data.get('queue_id')
            
            if not queue_id:
                return {
                    "status": "error",
                    "message": "queue_id الزامی است"
                }, 400
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # پیدا کردن هشتگ
            cursor.execute("SELECT * FROM hashtags_queue WHERE id = %s", (queue_id,))
            
            queue = cursor.fetchone()
            
            if not queue:
                cursor.close()
                conn.close()
                return {
                    "status": "error",
                    "message": "هشتگ یافت نشد"
                }, 404
            
            queue_status = queue['status']
            queue_id = queue['id']
            
            # اگر در حال پردازش است
            if queue_status == 'processing':
                # تعداد پست‌های جمع‌آوری شده تا الان
                cursor.execute("SELECT COUNT(*) as count FROM linkdeen_posts WHERE hashtag_id = %s", (queue_id,))
                collected = cursor.fetchone()
                
                cursor.close()
                conn.close()
                
                progress = (collected['count'] / queue['max_posts']) * 100 if queue['max_posts'] > 0 else 0
                
                return {
                    "status": "processing",
                    "message": "هشتگ در حال پردازش است",
                    "data": {
                        "queue": {
                            "id": queue['id'],
                            "hashtag": queue['hashtag'],
                            "status": queue_status,
                            "max_posts": queue['max_posts'],
                            "max_comments": queue['max_comments'],
                            "created_at": str(queue['created_at']),
                            "started_at": str(queue['started_at']) if queue.get('started_at') else None,
                            "completed_at": None,
                            "error_message": None
                        },
                        "statistics": {
                            "collected_posts": collected['count'],
                            "progress_percentage": round(progress, 2)
                        }
                    }
                }, 200
            
            # اگر pending است
            if queue_status == 'pending':
                cursor.close()
                conn.close()
                return {
                    "status": "pending",
                    "message": "هشتگ در صف انتظار است",
                    "data": {
                        "queue": {
                            "id": queue['id'],
                            "hashtag": queue['hashtag'],
                            "status": queue_status,
                            "max_posts": queue['max_posts'],
                            "max_comments": queue['max_comments'],
                            "created_at": str(queue['created_at'])
                        }
                    }
                }, 200
            
            # اگر failed است
            if queue_status == 'failed':
                cursor.close()
                conn.close()
                return {
                    "status": "failed",
                    "message": "پردازش هشتگ با خطا مواجه شد",
                    "data": {
                        "queue": {
                            "id": queue['id'],
                            "hashtag": queue['hashtag'],
                            "status": queue_status,
                            "error_message": queue.get('error_message'),
                            "created_at": str(queue['created_at']),
                            "started_at": str(queue['started_at']) if queue.get('started_at') else None,
                            "completed_at": str(queue['completed_at']) if queue.get('completed_at') else None
                        }
                    }
                }, 200
            
            # اگر completed است - دریافت تمام پست‌ها و کامنت‌ها
            cursor.execute("""
                SELECT 
                    id, post_link, caption, reactions, comments as comments_count,
                    username, created_at
                FROM linkdeen_posts
                WHERE hashtag_id = %s
                ORDER BY created_at DESC
            """, (queue_id,))
            
            posts = cursor.fetchall()
            
            # برای هر پست، کامنت‌ها را بگیر
            posts_with_comments = []
            for post in posts:
                cursor.execute("""
                    SELECT commenter, comment_text, created_at
                    FROM linkdeen_comments
                    WHERE linkdeen_post_id = %s
                    ORDER BY created_at DESC
                """, (post['id'],))
                
                comments = cursor.fetchall()
                
                posts_with_comments.append({
                    "post_id": post['id'],
                    "post_link": post.get('post_link'),
                    "caption": post.get('caption'),
                    "reactions": post.get('reactions'),
                    "comments_count": post.get('comments_count'),
                    "username": post.get('username'),
                    "created_at": str(post['created_at']) if post.get('created_at') else None,
                    "comments": [
                        {
                            "commenter": c.get('commenter'),
                            "comment_text": c.get('comment_text'),
                            "created_at": str(c['created_at']) if c.get('created_at') else None
                        } for c in comments
                    ]
                })
            
            # محاسبه آمار
            total_comments = sum(len(p['comments']) for p in posts_with_comments)
            duration = None
            if queue.get('started_at') and queue.get('completed_at'):
                duration = (queue['completed_at'] - queue['started_at']).total_seconds()
            
            cursor.close()
            conn.close()
            
            return {
                "status": "success",
                "message": "داده‌های هشتگ با موفقیت دریافت شد",
                "data": {
                    "queue": {
                        "id": queue['id'],
                        "hashtag": queue['hashtag'],
                        "status": queue_status,
                        "max_posts": queue['max_posts'],
                        "max_comments": queue['max_comments'],
                        "created_at": str(queue['created_at']),
                        "started_at": str(queue['started_at']) if queue.get('started_at') else None,
                        "completed_at": str(queue['completed_at']) if queue.get('completed_at') else None,
                        "error_message": queue.get('error_message')
                    },
                    "statistics": {
                        "total_posts": len(posts_with_comments),
                        "total_comments": total_comments,
                        "duration_seconds": duration
                    },
                    "posts": posts_with_comments
                }
            }, 200
            
        except Exception as e:
            bot_logger.error(f"❌ Error in get_hashtag_data: {e}")
            return {
                "status": "error",
                "message": str(e)
            }, 500


@hashtag_ns.route('/hashtag/list')
class HashtagList(Resource):
    @hashtag_ns.marshal_with(hashtag_list_response, code=200)
    @hashtag_ns.doc(
        description='لیست صف هشتگ‌ها با فیلتر و صفحه‌بندی',
        params={
            'status': {'description': 'فیلتر بر اساس وضعیت', 'enum': ['pending', 'processing', 'completed', 'failed'], 'in': 'query'},
            'limit': {'description': 'تعداد نتایج (پیش‌فرض: 50)', 'type': 'integer', 'default': 50, 'in': 'query'},
            'offset': {'description': 'شروع از (پیش‌فرض: 0)', 'type': 'integer', 'default': 0, 'in': 'query'}
        },
        responses={
            200: 'موفق',
            500: 'خطای سرور'
        }
    )
    def get(self):
        """لیست تمام هشتگ‌های موجود در صف"""
        try:
            status = request.args.get('status')
            limit = int(request.args.get('limit', 50))
            offset = int(request.args.get('offset', 0))
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # کوئری با فیلتر
            if status:
                cursor.execute("""
                    SELECT 
                        hq.*,
                        (SELECT COUNT(*) FROM linkdeen_posts WHERE hashtag_id = hq.id) as collected_posts,
                        (SELECT COUNT(*) FROM linkdeen_comments lc 
                         JOIN linkdeen_posts lp ON lc.linkdeen_post_id = lp.id 
                         WHERE lp.hashtag_id = hq.id) as total_comments
                    FROM hashtags_queue hq
                    WHERE hq.status = %s
                    ORDER BY hq.created_at DESC
                    LIMIT %s OFFSET %s
                """, (status, limit, offset))
            else:
                cursor.execute("""
                    SELECT 
                        hq.*,
                        (SELECT COUNT(*) FROM linkdeen_posts WHERE hashtag_id = hq.id) as collected_posts,
                        (SELECT COUNT(*) FROM linkdeen_comments lc 
                         JOIN linkdeen_posts lp ON lc.linkdeen_post_id = lp.id 
                         WHERE lp.hashtag_id = hq.id) as total_comments
                    FROM hashtags_queue hq
                    ORDER BY hq.created_at DESC
                    LIMIT %s OFFSET %s
                """, (limit, offset))
            
            hashtags = cursor.fetchall()
            
            # تعداد کل
            if status:
                cursor.execute("SELECT COUNT(*) as total FROM hashtags_queue WHERE status = %s", (status,))
            else:
                cursor.execute("SELECT COUNT(*) as total FROM hashtags_queue")
            
            total = cursor.fetchone()['total']
            
            cursor.close()
            conn.close()
            
            # فرمت کردن نتایج
            data = []
            for h in hashtags:
                duration = None
                if h.get('started_at') and h.get('completed_at'):
                    duration = (h['completed_at'] - h['started_at']).total_seconds()
                
                data.append({
                    "id": h['id'],
                    "hashtag": h['hashtag'],
                    "status": h['status'],
                    "max_posts": h['max_posts'],
                    "max_comments": h['max_comments'],
                    "collected_posts": h.get('collected_posts', 0),
                    "total_comments": h.get('total_comments', 0),
                    "created_at": str(h['created_at']),
                    "started_at": str(h['started_at']) if h.get('started_at') else None,
                    "completed_at": str(h['completed_at']) if h.get('completed_at') else None,
                    "duration_seconds": duration,
                    "error_message": h.get('error_message')
                })
            
            return {
                "status": "success",
                "message": "لیست هشتگ‌ها با موفقیت دریافت شد",
                "total": total,
                "data": data
            }, 200
            
        except Exception as e:
            bot_logger.error(f"❌ Error in hashtag_list: {e}")
            return {
                "status": "error",
                "message": str(e)
            }, 500


@hashtag_ns.route('/worker/status')
class WorkerStatus(Resource):
    @hashtag_ns.marshal_with(worker_status_response, code=200)
    @hashtag_ns.doc(
        description='دریافت وضعیت Worker و صف‌ها',
        responses={
            200: 'موفق',
            500: 'خطای سرور'
        }
    )
    def get(self):
        """دریافت وضعیت Worker و آمار صف‌ها"""
        try:
            from core.scheduler.worker import hashtag_worker
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # آمار هشتگ‌ها
            cursor.execute("""
                SELECT 
                    status,
                    COUNT(*) as count
                FROM hashtags_queue
                GROUP BY status
            """)
            hashtag_stats = cursor.fetchall()
            
            # آمار page ها
            cursor.execute("""
                SELECT 
                    status,
                    COUNT(*) as count
                FROM pages_queue
                GROUP BY status
            """)
            page_stats = cursor.fetchall()
            
            # تعداد کل پست‌ها و کامنت‌ها
            cursor.execute("SELECT COUNT(*) as total FROM linkdeen_posts")
            total_posts = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as total FROM linkdeen_comments")
            total_comments = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as total FROM linkdeen_pages")
            total_pages = cursor.fetchone()['total']
            
            cursor.close()
            conn.close()
            
            # فرمت آمار
            hashtag_queue = {"pending": 0, "processing": 0, "completed": 0, "failed": 0, "total": 0}
            for stat in hashtag_stats:
                hashtag_queue[stat['status']] = stat['count']
                hashtag_queue['total'] += stat['count']
            
            page_queue = {"pending": 0, "processing": 0, "completed": 0, "failed": 0, "total": 0}
            for stat in page_stats:
                page_queue[stat['status']] = stat['count']
                page_queue['total'] += stat['count']
            
            # وضعیت Worker
            worker_data = {
                "is_running": hashtag_worker.is_running if hashtag_worker else False,
                "is_processing": hashtag_worker.current_task_id is not None if hashtag_worker else False
            }
            
            if hashtag_worker and hashtag_worker.current_task_id:
                worker_data["current_task"] = {
                    "type": hashtag_worker.current_task_type,
                    "id": hashtag_worker.current_task_id
                }
            
            return {
                "status": "success",
                "message": "وضعیت Worker دریافت شد",
                "data": {
                    "worker": worker_data,
                    "queue": {
                        "hashtags": hashtag_queue,
                        "pages": page_queue
                    },
                    "statistics": {
                        "total_posts_collected": total_posts,
                        "total_comments_collected": total_comments,
                        "total_pages_scraped": total_pages
                    }
                }
            }, 200
            
        except Exception as e:
            bot_logger.error(f"❌ Error in worker_status: {e}")
            return {
                "status": "error",
                "message": str(e)
            }, 500
