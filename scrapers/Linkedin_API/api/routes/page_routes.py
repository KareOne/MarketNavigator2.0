"""
API Routes برای پردازش صفحات LinkedIn
"""

from flask import Blueprint, request, jsonify
from flask_restx import Resource
from core.automation.page_scraper import get_page
from config.config import get_db_connection, page_ns
from utils.logger import bot_logger
from api.models.swagger import (
    page_queue_input,
    queue_response,
    page_full_status,
    page_queue_list,
    page_queue_stats
)

page_bp = Blueprint('page', __name__)


@page_ns.route('/queue')
class QueuePage(Resource):
    @page_ns.expect(page_queue_input)
    @page_ns.marshal_with(queue_response)
    @page_ns.doc('افزودن صفحه شرکت به صف پردازش')
    def post(self):
        """افزودن صفحه LinkedIn شرکت به صف برای پردازش"""
        return queue_page()


@page_bp.route('/api/page/queue', methods=['POST'])
def queue_page():
    """
    🔹 افزودن Page به صف
    
    Body:
    {
        "page_name": "microsoft",
        "user_id": 1  # اختیاری - برای socket events
    }
    
    Response:
    {
        "status": "success",
        "message": "Page در صف قرار گرفت",
        "queue_id": 5
    }
    """
    try:
        result = get_page(request)
        if isinstance(result, tuple):
            return jsonify(result[0]), result[1]
        return jsonify(result)
    except Exception as e:
        bot_logger.error(f"❌ Error in queue_page: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@page_ns.route('/<int:queue_id>/status')
class PageStatus(Resource):
    @page_ns.marshal_with(page_full_status)
    @page_ns.doc('دریافت وضعیت کامل صفحه و اطلاعات جمع‌آوری شده')
    def get(self, queue_id):
        """دریافت وضعیت و اطلاعات کامل یک صفحه شرکت"""
        return get_page_status(queue_id)


@page_bp.route('/api/page/<int:queue_id>/status', methods=['GET'])
def get_page_status(queue_id):
    """
    🔹 دریافت وضعیت یک Page در صف
    
    Response:
    {
        "status": "success",
        "data": {
            "queue_id": 5,
            "page_name": "microsoft",
            "status": "completed",
            "created_at": "...",
            "completed_at": "..."
        }
    }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, page_name, user_id, status, error_message, 
                   created_at, started_at, completed_at
            FROM pages_queue
            WHERE id = %s
        """, (queue_id,))
        
        queue_data = cursor.fetchone()
        
        if not queue_data:
            cursor.close()
            conn.close()
            return jsonify({
                "status": "error",
                "message": f"Page با queue_id {queue_id} یافت نشد"
            }), 404
        
        # اگر completed است، اطلاعات صفحه را هم بگیر
        page_info = None
        if queue_data['status'] == 'completed':
            # خواندن تمام فیلدهایی که در دیتابیس ذخیره شده‌اند
            cursor.execute(
                """
                SELECT 
                    id,
                    page_title,
                    page_description,
                    page_overview,
                    last_post_content,
                    company_industry,
                    company_location,
                    company_followers,
                    company_employees,
                    company_link,
                    company_phone,
                    company_value
                FROM linkdeen_pages
                WHERE page_queue_id = %s
                LIMIT 1
                """,
                (queue_id,),
            )
            page_info = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        response_data = {
            "queue_id": queue_data['id'],
            "page_name": queue_data['page_name'],
            "status": queue_data['status'],
            "user_id": queue_data.get('user_id'),
            "error_message": queue_data.get('error_message'),
            "created_at": str(queue_data['created_at']) if queue_data.get('created_at') else None,
            "started_at": str(queue_data['started_at']) if queue_data.get('started_at') else None,
            "completed_at": str(queue_data['completed_at']) if queue_data.get('completed_at') else None
        }
        
        if page_info:
            # نگاشت کامل تمام 11 فیلد
            response_data['page_data'] = {
                "id": page_info['id'],
                "page_title": page_info.get('page_title'),
                "page_description": page_info.get('page_description'),
                "page_overview": page_info.get('page_overview'),
                "last_post_content": page_info.get('last_post_content'),
                "company_info": {
                    "industry": page_info.get('company_industry'),
                    "location": page_info.get('company_location'),
                    "followers": page_info.get('company_followers'),
                    "employees": page_info.get('company_employees')
                },
                "company_link": page_info.get('company_link'),
                "company_phone": page_info.get('company_phone'),
                "company_value": page_info.get('company_value'),
                "members_count": ""  # این فیلد در کد قدیمی شما هم خالی بود
            }
        
        return jsonify({
            "status": "success",
            "data": response_data
        })
        
    except Exception as e:
        bot_logger.error(f"❌ Error in get_page_status: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@page_ns.route('/queue/list')
class ListPageQueue(Resource):
    @page_ns.marshal_with(page_queue_list)
    @page_ns.doc('لیست صف صفحات', params={
        'status': 'فیلتر بر اساس وضعیت (pending, processing, completed, failed)',
        'limit': 'تعداد نتایج (پیش‌فرض: 50)'
    })
    def get(self):
        """دریافت لیست صفحات موجود در صف"""
        return list_page_queue()


@page_bp.route('/api/page/queue/list', methods=['GET'])
def list_page_queue():
    """
    🔹 لیست همه Page های موجود در صف
    
    Query Params:
    - status: فیلتر بر اساس وضعیت (pending, processing, completed, failed)
    - limit: تعداد نتایج (default: 50)
    
    Response:
    {
        "status": "success",
        "count": 10,
        "data": [...]
    }
    """
    try:
        status_filter = request.args.get('status')
        limit = request.args.get('limit', 50, type=int)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if status_filter:
            cursor.execute("""
                SELECT id, page_name, user_id, status, error_message, 
                       created_at, started_at, completed_at
                FROM pages_queue
                WHERE status = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (status_filter, limit))
        else:
            cursor.execute("""
                SELECT id, page_name, user_id, status, error_message, 
                       created_at, started_at, completed_at
                FROM pages_queue
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
        
        queue_items = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # تبدیل datetime به string
        for item in queue_items:
            if item.get('created_at'):
                item['created_at'] = str(item['created_at'])
            if item.get('started_at'):
                item['started_at'] = str(item['started_at'])
            if item.get('completed_at'):
                item['completed_at'] = str(item['completed_at'])
        
        return jsonify({
            "status": "success",
            "count": len(queue_items),
            "data": queue_items
        })
        
    except Exception as e:
        bot_logger.error(f"❌ Error in list_page_queue: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@page_ns.route('/queue/stats')
class PageQueueStatsResource(Resource):
    @page_ns.marshal_with(page_queue_stats)
    @page_ns.doc('دریافت آمار کامل صف صفحات')
    def get(self):
        """دریافت آمار تعداد صفحات در وضعیت‌های مختلف"""
        return get_page_queue_stats()


@page_bp.route('/api/page/queue/stats', methods=['GET'])
def get_page_queue_stats():
    """
    🔹 آمار صف Page ها
    
    Response:
    {
        "status": "success",
        "stats": {
            "pending": 5,
            "processing": 1,
            "completed": 20,
            "failed": 2
        }
    }
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as processing,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                COUNT(*) as total
            FROM pages_queue
        """)
        
        stats = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return jsonify({
            "status": "success",
            "stats": {
                "pending": stats['pending'] or 0,
                "processing": stats['processing'] or 0,
                "completed": stats['completed'] or 0,
                "failed": stats['failed'] or 0,
                "total": stats['total'] or 0
            }
        })
        
    except Exception as e:
        bot_logger.error(f"❌ Error in get_page_queue_stats: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
