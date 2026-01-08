"""
API Routes برای مدیریت صفحات (Pages)
"""

from flask import request, jsonify
from flask_restx import Resource
from config.config import get_db_connection, content_ns
from utils.logger import bot_logger
from api.models.swagger import (
    page_input_model,
    page_queue_response,
    page_data_input,
    page_full_data_response,
    page_list_response
)


@content_ns.route('/start/page/')
class StartPage(Resource):
    @content_ns.expect(page_input_model)
    @content_ns.marshal_with(page_queue_response, code=200)
    @content_ns.doc(
        description='این endpoint پیج را در صف ذخیره می‌کند و Worker به صورت خودکار پردازش می‌کند',
        responses={
            200: 'موفق',
            400: 'خطا در ورودی',
            500: 'خطای سرور'
        }
    )
    def post(self):
        """افزودن صفحه LinkedIn شرکت به صف برای پردازش"""
        try:
            data = request.get_json()
            page_name = data.get('page_name') or data.get('page')
            user_id = data.get('user_id')
            
            if not page_name:
                return {
                    "status": "error",
                    "message": "page_name الزامی است"
                }, 400
            
            # حذف URL اضافی اگر وجود دارد
            page_name = page_name.strip()
            if 'linkedin.com/company/' in page_name:
                page_name = page_name.split('linkedin.com/company/')[-1].rstrip('/')
            
            # ✅ حذف چک تکراری - اجازه به ایجاد page تکراری
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # ذخیره مستقیم در صف
            cursor.execute(
                "INSERT INTO pages_queue (page_name, user_id, status) VALUES (%s, %s, 'pending')",
                (page_name, user_id)
            )
            conn.commit()
            queue_id = cursor.lastrowid
            cursor.close()
            conn.close()
            
            bot_logger.info(f"✅ صفحه '{page_name}' با ID {queue_id} در صف قرار گرفت")
            
            return {
                "status": "success",
                "message": f"صفحه '{page_name}' در صف قرار گرفت و به زودی پردازش می‌شود",
                "queue_id": queue_id,
                "data": {
                    "page_name": page_name
                }
            }, 200
            
        except Exception as e:
            bot_logger.error(f"❌ Error in start_page: {e}")
            return {
                "status": "error",
                "message": str(e)
            }, 500


@content_ns.route('/get-data/page/')
class GetPageData(Resource):
    @content_ns.expect(page_data_input)
    @content_ns.marshal_with(page_full_data_response, code=200)
    @content_ns.doc(
        description='دریافت وضعیت کامل یک پیج',
        responses={
            200: 'موفق',
            400: 'خطا در ورودی',
            404: 'صفحه یافت نشد',
            500: 'خطای سرور'
        }
    )
    def post(self):
        """دریافت اطلاعات کامل صفحه"""
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
            
            # پیدا کردن صفحه
            cursor.execute("SELECT * FROM pages_queue WHERE id = %s", (queue_id,))
            
            queue = cursor.fetchone()
            
            if not queue:
                cursor.close()
                conn.close()
                return {
                    "status": "error",
                    "message": "صفحه یافت نشد"
                }, 404
            
            queue_status = queue['status']
            queue_id = queue['id']
            
            # اگر در حال پردازش است
            if queue_status == 'processing':
                cursor.close()
                conn.close()
                return {
                    "status": "processing",
                    "message": "صفحه در حال پردازش است",
                    "data": {
                        "queue": {
                            "id": queue['id'],
                            "page_name": queue['page_name'],
                            "status": queue_status,
                            "created_at": str(queue['created_at']),
                            "started_at": str(queue['started_at']) if queue.get('started_at') else None,
                            "completed_at": None
                        },
                        "progress": {
                            "message": "در حال استخراج اطلاعات شرکت..."
                        }
                    }
                }, 200
            
            # اگر pending است
            if queue_status == 'pending':
                cursor.close()
                conn.close()
                return {
                    "status": "pending",
                    "message": "صفحه در صف انتظار است",
                    "data": {
                        "queue": {
                            "id": queue['id'],
                            "page_name": queue['page_name'],
                            "status": queue_status,
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
                    "message": "پردازش صفحه با خطا مواجه شد",
                    "data": {
                        "queue": {
                            "id": queue['id'],
                            "page_name": queue['page_name'],
                            "status": queue_status,
                            "error_message": queue.get('error_message'),
                            "created_at": str(queue['created_at']),
                            "started_at": str(queue['started_at']) if queue.get('started_at') else None,
                            "completed_at": str(queue['completed_at']) if queue.get('completed_at') else None
                        }
                    }
                }, 200
            
            # اگر completed است - دریافت اطلاعات صفحه
            cursor.execute("""
                SELECT *
                FROM linkdeen_pages
                WHERE page_queue_id = %s
                ORDER BY id DESC
                LIMIT 1
            """, (queue_id,))
            
            page_data = cursor.fetchone()
            
            # محاسبه مدت زمان
            duration = None
            if queue.get('started_at') and queue.get('completed_at'):
                duration = (queue['completed_at'] - queue['started_at']).total_seconds()
            
            cursor.close()
            conn.close()
            
            page_info = None
            if page_data:
                # نکته کلیدی: برای کارکرد درست attribute در Swagger، کل ردیف DB را پاس می‌دهیم
                # تا فیلدهای company_info از ستون‌های company_industry/location/followers/employees نگاشت شوند.
                page_info = dict(page_data)
                # Remove created_at (scrape timestamp) to avoid duplicate - queue.created_at is the task creation time
                if 'created_at' in page_info:
                    del page_info['created_at']
                # Keep post_created_at (LinkedIn post timestamp) if it exists
                if page_info.get('post_created_at'):
                    page_info['post_created_at'] = str(page_info['post_created_at'])
            
            return {
                "status": "success",
                "message": "اطلاعات صفحه با موفقیت دریافت شد",
                "data": {
                    "queue": {
                        "id": queue['id'],
                        "page_name": queue['page_name'],
                        "status": queue_status,
                        "created_at": str(queue['created_at']),
                        "started_at": str(queue['started_at']) if queue.get('started_at') else None,
                        "completed_at": str(queue['completed_at']) if queue.get('completed_at') else None,
                        "error_message": queue.get('error_message')
                    },
                    "page_data": page_info
                }
            }, 200
            
        except Exception as e:
            bot_logger.error(f"❌ Error in get_page_data: {e}")
            return {
                "status": "error",
                "message": str(e)
            }, 500


@content_ns.route('/page/list')
class PageList(Resource):
    @content_ns.marshal_with(page_list_response, code=200)
    @content_ns.doc(
        description='دریافت لیست صفحات موجود در صف',
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
        """لیست تمام صفحات موجود در صف"""
        try:
            status = request.args.get('status')
            limit = int(request.args.get('limit', 50))
            offset = int(request.args.get('offset', 0))
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # کوئری با فیلتر
            query = """
                SELECT 
                    pq.*,
                    lp.page_title,
                    lp.company_industry,
                    lp.company_location,
                    lp.company_followers,
                    lp.company_employees
                FROM pages_queue pq
                LEFT JOIN linkdeen_pages lp ON lp.page_queue_id = pq.id
            """
            params = []

            if status:
                query += " WHERE pq.status = %s"
                params.append(status)
            
            query += " ORDER BY pq.created_at DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])

            cursor.execute(query, tuple(params))
            
            pages = cursor.fetchall()
            
            # تعداد کل
            if status:
                cursor.execute("SELECT COUNT(*) as total FROM pages_queue WHERE status = %s", (status,))
            else:
                cursor.execute("SELECT COUNT(*) as total FROM pages_queue")
            
            total = cursor.fetchone()['total']
            
            cursor.close()
            conn.close()
            
            # فرمت کردن نتایج
            data = []
            for p in pages:
                duration = None
                if p.get('started_at') and p.get('completed_at'):
                    duration = (p['completed_at'] - p['started_at']).total_seconds()
                
                item = {
                    "id": p['id'],
                    "page_name": p['page_name'],
                    "status": p['status'],
                    "created_at": str(p['created_at']),
                    "started_at": str(p.get('started_at')) if p.get('started_at') else None,
                    "completed_at": str(p.get('completed_at')) if p.get('completed_at') else None,
                    "duration_seconds": duration,
                    "page_title": p.get('page_title'),
                    "company_info": {
                        "industry": p.get('company_industry'),
                        "location": p.get('company_location'),
                        "followers": p.get('company_followers'),
                        "employees": p.get('company_employees')
                    },
                    "error_message": p.get('error_message')
                }
                # برای سازگاری با مدل قدیمی که company_followers را سطح بالا می‌خواهد
                if p.get('company_followers') is not None:
                    item['company_followers'] = p.get('company_followers')

                data.append(item)
            
            return {
                "status": "success",
                "message": "لیست صفحات با موفقیت دریافت شد",
                "total": total,
                "data": data
            }, 200
            
        except Exception as e:
            bot_logger.error(f"❌ Error in page_list: {e}")
            return {
                "status": "error",
                "message": str(e)
            }, 500
