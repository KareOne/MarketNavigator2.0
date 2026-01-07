"""
API Routes برای مدیریت کلمات کلیدی
"""

from flask import request, jsonify
from flask_restx import Resource
from config.config import get_db_connection, keyword_ns
from utils.logger import bot_logger
from core.automation.hashtag import get_keyword
from api.models.swagger import (
    keyword_input_model,
    keyword_queue_response,
    keyword_data_input,
    keyword_full_data_response,
    keyword_list_response,
    keywords_batch_input_model,
    keywords_batch_response,
    keywords_batch_results_input,
    keywords_batch_results_response
)
import json
import os
from datetime import datetime


@keyword_ns.route('/start/keyword/')
class StartKeyword(Resource):
    @keyword_ns.expect(keyword_input_model)
    @keyword_ns.marshal_with(keyword_queue_response, code=200)
    @keyword_ns.doc(
        description='این endpoint کلمه کلیدی را در صف ذخیره می‌کند و Worker به صورت خودکار پردازش می‌کند',
        responses={
            200: 'موفق',
            400: 'خطا در ورودی',
            500: 'خطای سرور'
        }
    )
    def post(self):
        """افزودن کلمه کلیدی به صف برای پردازش"""
        try:
            result = get_keyword(request)
            
            # اگر tuple برگشت (با status code)
            if isinstance(result, tuple):
                return result[0], result[1]
            
            return result, 200
            
        except Exception as e:
            bot_logger.error(f"❌ Error in start_keyword: {e}")
            return {
                "status": "error",
                "message": str(e)
            }, 500


@keyword_ns.route('/get-data/keyword/')
class GetKeywordData(Resource):
    @keyword_ns.expect(keyword_data_input)
    @keyword_ns.marshal_with(keyword_full_data_response, code=200)
    @keyword_ns.doc(
        description='دریافت وضعیت کامل یک کلمه کلیدی شامل تمام پست‌ها و کامنت‌ها',
        responses={
            200: 'موفق',
            400: 'خطا در ورودی',
            404: 'کلمه کلیدی یافت نشد',
            500: 'خطای سرور'
        }
    )
    def post(self):
        """دریافت اطلاعات کامل کلمه کلیدی با تمام پست‌ها و کامنت‌ها"""
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
            
            # پیدا کردن کلمه کلیدی
            cursor.execute("SELECT * FROM keywords_queue WHERE id = %s", (queue_id,))
            
            queue = cursor.fetchone()
            
            if not queue:
                cursor.close()
                conn.close()
                return {
                    "status": "error",
                    "message": "کلمه کلیدی یافت نشد"
                }, 404
            
            queue_status = queue['status']
            queue_id = queue['id']
            
            # اگر در حال پردازش است
            if queue_status == 'processing':
                # تعداد پست‌های جمع‌آوری شده تا الان
                cursor.execute("SELECT COUNT(*) as count FROM linkdeen_posts WHERE keyword_id = %s", (queue_id,))
                collected = cursor.fetchone()
                
                cursor.close()
                conn.close()
                
                return {
                    "status": "processing",
                    "message": f"در حال پردازش... تاکنون {collected['count']} پست جمع‌آوری شده است",
                    "data": {
                        "queue": {
                            "id": queue['id'],
                            "keyword": queue['keyword'],
                            "status": queue['status'],
                            "max_posts": queue['max_posts'],
                            "max_comments": queue['max_comments'],
                            "created_at": str(queue['created_at']) if queue['created_at'] else None,
                            "started_at": str(queue['started_at']) if queue['started_at'] else None,
                            "completed_at": None,
                            "error_message": None
                        },
                        "statistics": {
                            "total_posts": collected['count'],
                            "total_comments": 0,
                            "duration_seconds": None
                        },
                        "posts": []
                    }
                }, 200
            
            # اگر در صف انتظار است
            if queue_status == 'pending':
                cursor.close()
                conn.close()
                
                return {
                    "status": "pending",
                    "message": "کلمه کلیدی در صف انتظار است و به زودی پردازش می‌شود",
                    "data": {
                        "queue": {
                            "id": queue['id'],
                            "keyword": queue['keyword'],
                            "status": queue['status'],
                            "max_posts": queue['max_posts'],
                            "max_comments": queue['max_comments'],
                            "created_at": str(queue['created_at']) if queue['created_at'] else None,
                            "started_at": None,
                            "completed_at": None,
                            "error_message": None
                        },
                        "statistics": {
                            "total_posts": 0,
                            "total_comments": 0,
                            "duration_seconds": None
                        },
                        "posts": []
                    }
                }, 200
            
            # اگر ناموفق بوده
            if queue_status == 'failed':
                cursor.close()
                conn.close()
                
                return {
                    "status": "failed",
                    "message": f"پردازش کلمه کلیدی با خطا مواجه شد: {queue.get('error_message', 'خطای ناشناخته')}",
                    "data": {
                        "queue": {
                            "id": queue['id'],
                            "keyword": queue['keyword'],
                            "status": queue['status'],
                            "max_posts": queue['max_posts'],
                            "max_comments": queue['max_comments'],
                            "created_at": str(queue['created_at']) if queue['created_at'] else None,
                            "started_at": str(queue['started_at']) if queue['started_at'] else None,
                            "completed_at": str(queue['completed_at']) if queue['completed_at'] else None,
                            "error_message": queue.get('error_message')
                        },
                        "statistics": {
                            "total_posts": 0,
                            "total_comments": 0,
                            "duration_seconds": None
                        },
                        "posts": []
                    }
                }, 200
            
            # ✅ اگر تکمیل شده - پست‌ها و کامنت‌ها را برگردان
            if queue_status == 'completed':
                # دریافت پست‌ها
                cursor.execute("""
                    SELECT id, post_link, caption, reactions, comments as comments_count, 
                           username, created_at 
                    FROM linkdeen_posts 
                    WHERE keyword_id = %s 
                    ORDER BY created_at DESC
                """, (queue_id,))
                posts = cursor.fetchall()
                
                posts_data = []
                total_comments = 0
                
                for post in posts:
                    # دریافت کامنت‌های این پست
                    cursor.execute("""
                        SELECT commenter, comment_text, created_at 
                        FROM linkdeen_comments 
                        WHERE linkdeen_post_id = %s 
                        ORDER BY created_at DESC
                    """, (post['id'],))
                    comments = cursor.fetchall()
                    
                    comments_list = [{
                        'commenter': c['commenter'],
                        'comment_text': c['comment_text'],
                        'created_at': str(c['created_at']) if c['created_at'] else None
                    } for c in comments]
                    
                    total_comments += len(comments_list)
                    
                    posts_data.append({
                        'post_id': post['id'],
                        'post_link': post['post_link'],
                        'caption': post['caption'],
                        'reactions': post['reactions'],
                        'comments_count': len(comments_list),
                        'username': post['username'],
                        'created_at': str(post['created_at']) if post['created_at'] else None,
                        'comments': comments_list
                    })
                
                # محاسبه مدت زمان
                duration = None
                if queue['started_at'] and queue['completed_at']:
                    duration = (queue['completed_at'] - queue['started_at']).total_seconds()
                
                cursor.close()
                conn.close()
                
                return {
                    "status": "success",
                    "message": "داده‌های کلمه کلیدی با موفقیت دریافت شد",
                    "data": {
                        "queue": {
                            "id": queue['id'],
                            "keyword": queue['keyword'],
                            "status": queue['status'],
                            "max_posts": queue['max_posts'],
                            "max_comments": queue['max_comments'],
                            "created_at": str(queue['created_at']) if queue['created_at'] else None,
                            "started_at": str(queue['started_at']) if queue['started_at'] else None,
                            "completed_at": str(queue['completed_at']) if queue['completed_at'] else None,
                            "error_message": None
                        },
                        "statistics": {
                            "total_posts": len(posts_data),
                            "total_comments": total_comments,
                            "duration_seconds": duration
                        },
                        "posts": posts_data
                    }
                }, 200
            
        except Exception as e:
            bot_logger.error(f"❌ Error in get_keyword_data: {e}")
            return {
                "status": "error",
                "message": str(e)
            }, 500


@keyword_ns.route('/list/')
class KeywordList(Resource):
    @keyword_ns.marshal_with(keyword_list_response, code=200)
    @keyword_ns.doc(
        description='دریافت لیست تمام کلمات کلیدی با آمار کامل',
        responses={
            200: 'موفق',
            500: 'خطای سرور'
        }
    )
    def get(self):
        """دریافت لیست تمام کلمات کلیدی"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # دریافت تمام کلمات کلیدی
            cursor.execute("""
                SELECT 
                    kq.*,
                    COUNT(DISTINCT lp.id) as collected_posts,
                    COUNT(lc.id) as total_comments
                FROM keywords_queue kq
                LEFT JOIN linkdeen_posts lp ON lp.keyword_id = kq.id
                LEFT JOIN linkdeen_comments lc ON lc.linkdeen_post_id = lp.id
                GROUP BY kq.id
                ORDER BY kq.created_at DESC
            """)
            
            keywords = cursor.fetchall()
            cursor.close()
            conn.close()
            
            keywords_list = []
            for keyword in keywords:
                # محاسبه مدت زمان
                duration = None
                if keyword['started_at'] and keyword['completed_at']:
                    duration = (keyword['completed_at'] - keyword['started_at']).total_seconds()
                
                keywords_list.append({
                    'id': keyword['id'],
                    'keyword': keyword['keyword'],
                    'status': keyword['status'],
                    'max_posts': keyword['max_posts'],
                    'max_comments': keyword['max_comments'],
                    'collected_posts': keyword['collected_posts'],
                    'total_comments': keyword['total_comments'],
                    'created_at': str(keyword['created_at']) if keyword['created_at'] else None,
                    'started_at': str(keyword['started_at']) if keyword['started_at'] else None,
                    'completed_at': str(keyword['completed_at']) if keyword['completed_at'] else None,
                    'duration_seconds': duration,
                    'error_message': keyword.get('error_message')
                })
            
            return {
                "status": "success",
                "message": "لیست کلمات کلیدی با موفقیت دریافت شد",
                "total": len(keywords_list),
                "data": keywords_list
            }, 200
            
        except Exception as e:
            bot_logger.error(f"❌ Error in keyword_list: {e}")
            return {
                "status": "error",
                "message": str(e)
            }, 500


@keyword_ns.route('/start/batch/')
class StartKeywordsBatch(Resource):
    @keyword_ns.expect(keywords_batch_input_model)
    @keyword_ns.marshal_with(keywords_batch_response, code=200)
    @keyword_ns.doc(
        description='افزودن دسته‌ای از کلمات کلیدی به صف - برای پردازش چندین کلمه کلیدی به صورت همزمان',
        responses={
            200: 'موفق',
            400: 'خطا در ورودی',
            500: 'خطای سرور'
        }
    )
    def post(self):
        """افزودن دسته‌ای از کلمات کلیدی به صف"""
        try:
            data = request.get_json()
            keywords = data.get('keywords', [])
            max_posts = data.get('max_posts', 5)
            max_comments = data.get('max_comments', 5)
            user_id = data.get('user_id')  # اختیاری
            
            if not keywords or not isinstance(keywords, list):
                return {
                    "status": "error",
                    "message": "لیست کلمات کلیدی الزامی است و باید آرایه باشد"
                }, 400
            
            if len(keywords) == 0:
                return {
                    "status": "error",
                    "message": "لیست کلمات کلیدی نمی‌تواند خالی باشد"
                }, 400
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            queue_ids = []
            keywords_info = []
            
            # افزودن هر کلمه کلیدی به صف
            for keyword in keywords:
                keyword = str(keyword).strip()
                if not keyword:
                    continue
                
                try:
                    cursor.execute(
                        "INSERT INTO keywords_queue (keyword, max_posts, max_comments, user_id, status) VALUES (%s, %s, %s, %s, 'pending')",
                        (keyword, max_posts, max_comments, user_id)
                    )
                    conn.commit()
                    queue_id = cursor.lastrowid
                    queue_ids.append(queue_id)
                    keywords_info.append({
                        'keyword': keyword,
                        'queue_id': queue_id
                    })
                    bot_logger.info(f"✅ کلمه کلیدی '{keyword}' با ID {queue_id} در صف قرار گرفت")
                except Exception as e:
                    bot_logger.error(f"❌ خطا در افزودن کلمه کلیدی '{keyword}': {e}")
                    continue
            
            cursor.close()
            conn.close()
            
            if len(queue_ids) == 0:
                return {
                    "status": "error",
                    "message": "هیچ کلمه کلیدی معتبری در صف قرار نگرفت"
                }, 400
            
            return {
                "status": "success",
                "message": f"{len(queue_ids)} کلمه کلیدی در صف قرار گرفت و به زودی توسط Worker پردازش می‌شوند",
                "total_keywords": len(queue_ids),
                "queue_ids": queue_ids,
                "keywords": keywords_info
            }, 200
            
        except Exception as e:
            bot_logger.error(f"❌ Error in start_keywords_batch: {e}")
            return {
                "status": "error",
                "message": str(e)
            }, 500


@keyword_ns.route('/get-batch-results/')
class GetKeywordsBatchResults(Resource):
    @keyword_ns.expect(keywords_batch_results_input)
    @keyword_ns.marshal_with(keywords_batch_results_response, code=200)
    @keyword_ns.doc(
        description='دریافت نتایج دسته‌ای کلمات کلیدی و ذخیره در فایل JSON',
        responses={
            200: 'موفق',
            400: 'خطا در ورودی',
            500: 'خطای سرور'
        }
    )
    def post(self):
        """دریافت نتایج چندین کلمه کلیدی و ذخیره در JSON"""
        try:
            data = request.get_json()
            queue_ids = data.get('queue_ids', [])
            save_to_file = data.get('save_to_file', True)
            filename = data.get('filename')
            
            if not queue_ids or not isinstance(queue_ids, list):
                return {
                    "status": "error",
                    "message": "لیست queue_ids الزامی است"
                }, 400
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            all_results = []
            stats = {
                'completed': 0,
                'processing': 0,
                'pending': 0,
                'failed': 0
            }
            
            for queue_id in queue_ids:
                try:
                    # دریافت اطلاعات صف
                    cursor.execute("SELECT * FROM keywords_queue WHERE id = %s", (queue_id,))
                    queue = cursor.fetchone()
                    
                    if not queue:
                        continue
                    
                    # شمارش وضعیت
                    stats[queue['status']] = stats.get(queue['status'], 0) + 1
                    
                    keyword_result = {
                        'queue_id': queue['id'],
                        'keyword': queue['keyword'],
                        'status': queue['status'],
                        'max_posts': queue['max_posts'],
                        'max_comments': queue['max_comments'],
                        'created_at': str(queue['created_at']) if queue['created_at'] else None,
                        'started_at': str(queue['started_at']) if queue['started_at'] else None,
                        'completed_at': str(queue['completed_at']) if queue['completed_at'] else None,
                        'error_message': queue.get('error_message'),
                        'posts': []
                    }
                    
                    # اگر تکمیل شده، پست‌ها را دریافت کن
                    if queue['status'] == 'completed':
                        cursor.execute("""
                            SELECT id, post_link, caption, reactions, comments as comments_count, 
                                   username, created_at 
                            FROM linkdeen_posts 
                            WHERE keyword_id = %s 
                            ORDER BY created_at DESC
                        """, (queue_id,))
                        posts = cursor.fetchall()
                        
                        for post in posts:
                            # دریافت کامنت‌های این پست
                            cursor.execute("""
                                SELECT commenter, comment_text, created_at 
                                FROM linkdeen_comments 
                                WHERE linkdeen_post_id = %s 
                                ORDER BY created_at DESC
                            """, (post['id'],))
                            comments = cursor.fetchall()
                            
                            keyword_result['posts'].append({
                                'post_id': post['id'],
                                'post_link': post['post_link'],
                                'caption': post['caption'],
                                'reactions': post['reactions'],
                                'comments_count': len(comments),
                                'username': post['username'],
                                'created_at': str(post['created_at']) if post['created_at'] else None,
                                'comments': [{
                                    'commenter': c['commenter'],
                                    'comment_text': c['comment_text'],
                                    'created_at': str(c['created_at']) if c['created_at'] else None
                                } for c in comments]
                            })
                    
                    all_results.append(keyword_result)
                    
                except Exception as e:
                    bot_logger.error(f"❌ Error processing queue_id {queue_id}: {e}")
                    continue
            
            cursor.close()
            conn.close()
            
            # آماده‌سازی نتیجه نهایی
            final_result = {
                'metadata': {
                    'total_keywords': len(queue_ids),
                    'completed': stats.get('completed', 0),
                    'processing': stats.get('processing', 0),
                    'pending': stats.get('pending', 0),
                    'failed': stats.get('failed', 0),
                    'generated_at': datetime.now().isoformat()
                },
                'keywords': all_results
            }
            
            file_path = None
            
            # ذخیره در فایل
            if save_to_file:
                # ایجاد پوشه exports اگر وجود ندارد
                exports_dir = '/app/exports'
                os.makedirs(exports_dir, exist_ok=True)
                
                # تولید نام فایل
                if not filename:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f'keywords_results_{timestamp}.json'
                
                if not filename.endswith('.json'):
                    filename += '.json'
                
                file_path = os.path.join(exports_dir, filename)
                
                # ذخیره در فایل
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(final_result, f, ensure_ascii=False, indent=2)
                
                bot_logger.info(f"✅ نتایج در فایل {file_path} ذخیره شد")
            
            return {
                "status": "success",
                "message": f"نتایج {len(all_results)} کلمه کلیدی دریافت شد",
                "total_keywords": len(queue_ids),
                "completed": stats.get('completed', 0),
                "processing": stats.get('processing', 0),
                "failed": stats.get('failed', 0),
                "file_path": file_path,
                "results": final_result
            }, 200
            
        except Exception as e:
            bot_logger.error(f"❌ Error in get_keywords_batch_results: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "message": str(e)
            }, 500
