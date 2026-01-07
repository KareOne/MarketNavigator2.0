
from flask_restx import Api, Resource, fields
from config.config import api, report_ns, content_ns, follow_ns, hashtag_ns, keyword_ns


account_model = content_ns.model('Account', {
    'username': fields.String(required=True, description='نام کاربری اینستاگرام'),
    'password': fields.String(required=True, description='رمز عبور اینستاگرام'),
})


# ========================================
# 🔹 Hashtag Models (hashtag_ns)
# ========================================

# مدل ورودی برای افزودن هشتگ
hashtag_input_model = hashtag_ns.model('HashtagInput', {
    'hashtag': fields.String(required=True, description='نام هشتگ (بدون #)', example='python'),
    'max_posts': fields.Integer(required=False, default=5, description='حداکثر تعداد پست (پیش‌فرض: 5)', example=10),
    'max_comments': fields.Integer(required=False, default=5, description='حداکثر تعداد کامنت در هر پست (پیش‌فرض: 5)', example=5)
})

# مدل خروجی افزودن هشتگ به صف
hashtag_queue_response = hashtag_ns.model('HashtagQueueResponse', {
    'status': fields.String(description='وضعیت درخواست', example='success'),
    'message': fields.String(description='پیام توضیحی', example='هشتگ در صف قرار گرفت'),
    'queue_id': fields.Integer(description='شناسه صف - برای بررسی وضعیت استفاده کنید', example=5),
    'data': fields.Nested(hashtag_ns.model('HashtagQueueData', {
        'hashtag': fields.String(description='نام هشتگ', example='python'),
        'max_posts': fields.Integer(description='حداکثر تعداد پست', example=10),
        'max_comments': fields.Integer(description='حداکثر تعداد کامنت', example=5)
    }))
})

# مدل ورودی دریافت داده هشتگ
hashtag_data_input = hashtag_ns.model('HashtagDataInput', {
    'queue_id': fields.Integer(required=True, description='شناسه صف', example=5)
})

# مدل کامنت
comment_detail_model = hashtag_ns.model('CommentDetail', {
    'commenter': fields.String(description='نام کامنت‌گذار', example='John Doe'),
    'comment_text': fields.String(description='متن کامنت', example='Great post!'),
    'created_at': fields.String(description='تاریخ ایجاد', example='2025-10-23 14:30:00')
})

# مدل پست با کامنت‌ها
post_with_comments_model = hashtag_ns.model('PostWithComments', {
    'post_id': fields.Integer(description='شناسه پست', example=123),
    'post_link': fields.String(description='لینک پست', example='https://linkedin.com/posts/...'),
    'caption': fields.String(description='متن پست', example='Amazing content!'),
    'reactions': fields.String(description='تعداد ری‌اکشن', example='245'),
    'comments_count': fields.Integer(description='تعداد کامنت', example=8),
    'username': fields.String(description='نام کاربر', example='Jane Developer'),
    'created_at': fields.String(description='تاریخ ایجاد', example='2025-10-23 14:35:00'),
    'comments': fields.List(fields.Nested(comment_detail_model), description='لیست کامنت‌ها')
})

# مدل صف هشتگ
hashtag_queue_info = hashtag_ns.model('HashtagQueueInfo', {
    'id': fields.Integer(description='شناسه صف', example=5),
    'hashtag': fields.String(description='نام هشتگ', example='python'),
    'status': fields.String(description='وضعیت', example='completed', enum=['pending', 'processing', 'completed', 'failed']),
    'max_posts': fields.Integer(description='حداکثر پست', example=10),
    'max_comments': fields.Integer(description='حداکثر کامنت', example=5),
    'created_at': fields.String(description='تاریخ ایجاد', example='2025-10-23 14:30:00'),
    'started_at': fields.String(description='تاریخ شروع', example='2025-10-23 14:31:00'),
    'completed_at': fields.String(description='تاریخ اتمام', example='2025-10-23 14:45:00'),
    'error_message': fields.String(description='پیام خطا (در صورت وجود)', example=None)
})

# مدل آمار هشتگ
hashtag_statistics = hashtag_ns.model('HashtagStatistics', {
    'total_posts': fields.Integer(description='تعداد کل پست‌ها', example=10),
    'total_comments': fields.Integer(description='تعداد کل کامنت‌ها', example=47),
    'duration_seconds': fields.Float(description='مدت زمان پردازش (ثانیه)', example=840.5)
})

# مدل خروجی کامل داده هشتگ
hashtag_full_data_response = hashtag_ns.model('HashtagFullDataResponse', {
    'status': fields.String(description='وضعیت', example='success', enum=['success', 'processing', 'pending', 'failed', 'error']),
    'message': fields.String(description='پیام', example='داده‌های هشتگ با موفقیت دریافت شد'),
    'data': fields.Nested(hashtag_ns.model('HashtagFullData', {
        'queue': fields.Nested(hashtag_queue_info, description='اطلاعات صف'),
        'statistics': fields.Nested(hashtag_statistics, description='آمار'),
        'posts': fields.List(fields.Nested(post_with_comments_model), description='لیست پست‌ها با کامنت‌ها')
    }))
})

# مدل آیتم لیست هشتگ
hashtag_list_item = hashtag_ns.model('HashtagListItem', {
    'id': fields.Integer(description='شناسه', example=5),
    'hashtag': fields.String(description='نام هشتگ', example='python'),
    'status': fields.String(description='وضعیت', example='completed'),
    'max_posts': fields.Integer(description='حداکثر پست', example=10),
    'max_comments': fields.Integer(description='حداکثر کامنت', example=5),
    'collected_posts': fields.Integer(description='تعداد پست‌های جمع‌آوری شده', example=10),
    'total_comments': fields.Integer(description='تعداد کل کامنت‌ها', example=47),
    'created_at': fields.String(description='تاریخ ایجاد', example='2025-10-23 14:30:00'),
    'started_at': fields.String(description='تاریخ شروع', example='2025-10-23 14:31:00'),
    'completed_at': fields.String(description='تاریخ اتمام', example='2025-10-23 14:45:00'),
    'duration_seconds': fields.Float(description='مدت زمان (ثانیه)', example=840.5),
    'error_message': fields.String(description='پیام خطا', example=None)
})

# مدل خروجی لیست هشتگ‌ها
hashtag_list_response = hashtag_ns.model('HashtagListResponse', {
    'status': fields.String(description='وضعیت', example='success'),
    'message': fields.String(description='پیام', example='لیست هشتگ‌ها با موفقیت دریافت شد'),
    'total': fields.Integer(description='تعداد کل', example=25),
    'data': fields.List(fields.Nested(hashtag_list_item), description='لیست هشتگ‌ها')
})

# مدل Worker Status
worker_info_model = hashtag_ns.model('WorkerInfo', {
    'is_running': fields.Boolean(description='آیا Worker در حال اجرا است', example=True),
    'is_processing': fields.Boolean(description='آیا در حال پردازش است', example=True),
    'current_task': fields.Raw(description='تسک فعلی', example={'type': 'hashtag', 'id': 5})
})

queue_stats_model = hashtag_ns.model('QueueStats', {
    'pending': fields.Integer(description='در انتظار', example=2),
    'processing': fields.Integer(description='در حال پردازش', example=1),
    'completed': fields.Integer(description='تکمیل شده', example=15),
    'failed': fields.Integer(description='ناموفق', example=1),
    'total': fields.Integer(description='مجموع', example=19)
})

worker_status_response = hashtag_ns.model('WorkerStatusResponse', {
    'status': fields.String(description='وضعیت', example='success'),
    'message': fields.String(description='پیام', example='وضعیت Worker دریافت شد'),
    'data': fields.Nested(hashtag_ns.model('WorkerStatusData', {
        'worker': fields.Nested(worker_info_model, description='اطلاعات Worker'),
        'queue': fields.Nested(hashtag_ns.model('QueueInfo', {
            'hashtags': fields.Nested(queue_stats_model, description='آمار صف هشتگ‌ها'),
            'pages': fields.Nested(queue_stats_model, description='آمار صف صفحات')
        })),
        'statistics': fields.Nested(hashtag_ns.model('Statistics', {
            'total_posts_collected': fields.Integer(description='کل پست‌های جمع‌آوری شده', example=245),
            'total_comments_collected': fields.Integer(description='کل کامنت‌های جمع‌آوری شده', example=1023),
            'total_pages_scraped': fields.Integer(description='کل صفحات اسکرپ شده', example=8)
        }))
    }))
})


# ========================================
# 🔹 Keyword Models (keyword_ns)
# ========================================

# مدل ورودی برای افزودن کلمه کلیدی
keyword_input_model = keyword_ns.model('KeywordInput', {
    'keyword': fields.String(required=True, description='کلمه کلیدی برای جستجو', example='artificial intelligence'),
    'max_posts': fields.Integer(required=False, default=5, description='حداکثر تعداد پست (پیش‌فرض: 5)', example=10),
    'max_comments': fields.Integer(required=False, default=5, description='حداکثر تعداد کامنت در هر پست (پیش‌فرض: 5)', example=5)
})

# مدل خروجی افزودن کلمه کلیدی به صف
keyword_queue_response = keyword_ns.model('KeywordQueueResponse', {
    'status': fields.String(description='وضعیت درخواست', example='success'),
    'message': fields.String(description='پیام توضیحی', example='کلمه کلیدی در صف قرار گرفت'),
    'queue_id': fields.Integer(description='شناسه صف - برای بررسی وضعیت استفاده کنید', example=5),
    'data': fields.Nested(keyword_ns.model('KeywordQueueData', {
        'keyword': fields.String(description='کلمه کلیدی', example='artificial intelligence'),
        'max_posts': fields.Integer(description='حداکثر تعداد پست', example=10),
        'max_comments': fields.Integer(description='حداکثر تعداد کامنت', example=5)
    }))
})

# مدل ورودی دریافت داده کلمه کلیدی
keyword_data_input = keyword_ns.model('KeywordDataInput', {
    'queue_id': fields.Integer(required=True, description='شناسه صف', example=5)
})

# مدل صف کلمه کلیدی
keyword_queue_info = keyword_ns.model('KeywordQueueInfo', {
    'id': fields.Integer(description='شناسه صف', example=5),
    'keyword': fields.String(description='کلمه کلیدی', example='artificial intelligence'),
    'status': fields.String(description='وضعیت', example='completed', enum=['pending', 'processing', 'completed', 'failed']),
    'max_posts': fields.Integer(description='حداکثر پست', example=10),
    'max_comments': fields.Integer(description='حداکثر کامنت', example=5),
    'created_at': fields.String(description='تاریخ ایجاد', example='2025-10-23 14:30:00'),
    'started_at': fields.String(description='تاریخ شروع', example='2025-10-23 14:31:00'),
    'completed_at': fields.String(description='تاریخ اتمام', example='2025-10-23 14:45:00'),
    'error_message': fields.String(description='پیام خطا (در صورت وجود)', example=None)
})

# استفاده از همان مدل‌های comment و post
keyword_comment_detail_model = keyword_ns.model('KeywordCommentDetail', {
    'commenter': fields.String(description='نام کامنت‌گذار', example='John Doe'),
    'comment_text': fields.String(description='متن کامنت', example='Great post!'),
    'created_at': fields.String(description='تاریخ ایجاد', example='2025-10-23 14:30:00')
})

keyword_post_with_comments_model = keyword_ns.model('KeywordPostWithComments', {
    'post_id': fields.Integer(description='شناسه پست', example=123),
    'post_link': fields.String(description='لینک پست', example='https://linkedin.com/posts/...'),
    'caption': fields.String(description='متن پست', example='Amazing content!'),
    'reactions': fields.String(description='تعداد ری‌اکشن', example='245'),
    'comments_count': fields.Integer(description='تعداد کامنت', example=8),
    'username': fields.String(description='نام کاربر', example='Jane Developer'),
    'created_at': fields.String(description='تاریخ ایجاد', example='2025-10-23 14:35:00'),
    'comments': fields.List(fields.Nested(keyword_comment_detail_model), description='لیست کامنت‌ها')
})

# مدل آمار کلمه کلیدی
keyword_statistics = keyword_ns.model('KeywordStatistics', {
    'total_posts': fields.Integer(description='تعداد کل پست‌ها', example=10),
    'total_comments': fields.Integer(description='تعداد کل کامنت‌ها', example=47),
    'duration_seconds': fields.Float(description='مدت زمان پردازش (ثانیه)', example=840.5)
})

# مدل خروجی کامل داده کلمه کلیدی
keyword_full_data_response = keyword_ns.model('KeywordFullDataResponse', {
    'status': fields.String(description='وضعیت', example='success', enum=['success', 'processing', 'pending', 'failed', 'error']),
    'message': fields.String(description='پیام', example='داده‌های کلمه کلیدی با موفقیت دریافت شد'),
    'data': fields.Nested(keyword_ns.model('KeywordFullData', {
        'queue': fields.Nested(keyword_queue_info, description='اطلاعات صف'),
        'statistics': fields.Nested(keyword_statistics, description='آمار'),
        'posts': fields.List(fields.Nested(keyword_post_with_comments_model), description='لیست پست‌ها با کامنت‌ها')
    }))
})

# مدل آیتم لیست کلمات کلیدی
keyword_list_item = keyword_ns.model('KeywordListItem', {
    'id': fields.Integer(description='شناسه', example=5),
    'keyword': fields.String(description='کلمه کلیدی', example='artificial intelligence'),
    'status': fields.String(description='وضعیت', example='completed'),
    'max_posts': fields.Integer(description='حداکثر پست', example=10),
    'max_comments': fields.Integer(description='حداکثر کامنت', example=5),
    'collected_posts': fields.Integer(description='تعداد پست‌های جمع‌آوری شده', example=10),
    'total_comments': fields.Integer(description='تعداد کل کامنت‌ها', example=47),
    'created_at': fields.String(description='تاریخ ایجاد', example='2025-10-23 14:30:00'),
    'started_at': fields.String(description='تاریخ شروع', example='2025-10-23 14:31:00'),
    'completed_at': fields.String(description='تاریخ اتمام', example='2025-10-23 14:45:00'),
    'duration_seconds': fields.Float(description='مدت زمان (ثانیه)', example=840.5),
    'error_message': fields.String(description='پیام خطا', example=None)
})

# مدل خروجی لیست کلمات کلیدی
keyword_list_response = keyword_ns.model('KeywordListResponse', {
    'status': fields.String(description='وضعیت', example='success'),
    'message': fields.String(description='پیام', example='لیست کلمات کلیدی با موفقیت دریافت شد'),
    'total': fields.Integer(description='تعداد کل', example=25),
    'data': fields.List(fields.Nested(keyword_list_item), description='لیست کلمات کلیدی')
})

# مدل ورودی دسته‌ای کلمات کلیدی
keywords_batch_input_model = keyword_ns.model('KeywordsBatchInput', {
    'keywords': fields.List(fields.String, required=True, description='لیست کلمات کلیدی', example=['AI storytelling', 'machine learning']),
    'max_posts': fields.Integer(required=False, default=5, description='حداکثر تعداد پست برای هر کلمه (پیش‌فرض: 5)', example=10),
    'max_comments': fields.Integer(required=False, default=5, description='حداکثر تعداد کامنت در هر پست (پیش‌فرض: 5)', example=5)
})

# مدل خروجی دسته‌ای کلمات کلیدی
keywords_batch_response = keyword_ns.model('KeywordsBatchResponse', {
    'status': fields.String(description='وضعیت درخواست', example='success'),
    'message': fields.String(description='پیام توضیحی', example='20 کلمه کلیدی در صف قرار گرفت'),
    'total_keywords': fields.Integer(description='تعداد کل کلمات', example=20),
    'queue_ids': fields.List(fields.Integer, description='لیست شناسه‌های صف', example=[1, 2, 3]),
    'keywords': fields.List(fields.Nested(keyword_ns.model('BatchKeywordItem', {
        'keyword': fields.String(description='کلمه کلیدی', example='AI storytelling'),
        'queue_id': fields.Integer(description='شناسه صف', example=1)
    })), description='اطلاعات هر کلمه کلیدی')
})

# مدل ورودی دریافت دسته‌ای نتایج
keywords_batch_results_input = keyword_ns.model('KeywordsBatchResultsInput', {
    'queue_ids': fields.List(fields.Integer, required=True, description='لیست شناسه‌های صف', example=[1, 2, 3]),
    'save_to_file': fields.Boolean(required=False, default=True, description='ذخیره در فایل JSON', example=True),
    'filename': fields.String(required=False, description='نام فایل (اختیاری)', example='keywords_results.json')
})

# مدل خروجی دریافت دسته‌ای نتایج
keywords_batch_results_response = keyword_ns.model('KeywordsBatchResultsResponse', {
    'status': fields.String(description='وضعیت', example='success'),
    'message': fields.String(description='پیام', example='نتایج 20 کلمه کلیدی دریافت شد'),
    'total_keywords': fields.Integer(description='تعداد کل', example=20),
    'completed': fields.Integer(description='تکمیل شده', example=18),
    'processing': fields.Integer(description='در حال پردازش', example=2),
    'failed': fields.Integer(description='ناموفق', example=0),
    'file_path': fields.String(description='مسیر فایل ذخیره شده', example='/app/exports/keywords_results_20251122_120530.json'),
    'results': fields.Raw(description='نتایج کامل تمام کلمات کلیدی')
})


# ========================================
# 🔹 Page Models (content_ns)
# ========================================

# مدل ورودی افزودن صفحه
page_input_model = content_ns.model('PageInput', {
    'page_name': fields.String(required=True, description='نام صفحه LinkedIn شرکت', example='microsoft')
})

# مدل خروجی افزودن صفحه
page_queue_response = content_ns.model('PageQueueResponse', {
    'status': fields.String(description='وضعیت', example='success'),
    'message': fields.String(description='پیام', example='صفحه در صف قرار گرفت'),
    'queue_id': fields.Integer(description='شناسه صف', example=3),
    'data': fields.Nested(content_ns.model('PageQueueData', {
        'page_name': fields.String(description='نام صفحه', example='microsoft')
    }))
})

# مدل ورودی دریافت داده صفحه
page_data_input = content_ns.model('PageDataInput', {
    'queue_id': fields.Integer(required=True, description='شناسه صف', example=3)
})

# مدل اطلاعات شرکت
company_info_model = content_ns.model('CompanyInfo', {
    'industry': fields.String(description='صنعت شرکت', example='Software Development', attribute='company_industry'),
    'location': fields.String(description='موقعیت مکانی شرکت', example='Redmond, Washington', attribute='company_location'),
    'followers': fields.String(description='تعداد فالوئرهای شرکت در LinkedIn', example='20,456,789 followers', attribute='company_followers'),
    'employees': fields.String(description='تعداد کارمندان شرکت', example='10,001+ employees', attribute='company_employees')
})

# مدل داده صفحه
page_data_detail = content_ns.model('PageDataDetail', {
    'id': fields.Integer(description='شناسه رکورد در دیتابیس', example=1),
    'page_title': fields.String(description='عنوان صفحه / نام شرکت', example='Microsoft'),
    'page_description': fields.String(description='توضیحات کوتاه شرکت', example='At Microsoft, our mission is to empower...'),
    'page_overview': fields.String(description='بررسی کلی و جزئیات شرکت', example='Microsoft is a leading technology company...'),
    'company_info': fields.Nested(company_info_model, description='اطلاعات شرکت (صنعت، موقعیت، فالوئرها، کارمندان)', attribute=lambda x: x),
    'company_link': fields.String(description='وبسایت رسمی شرکت', example='https://www.microsoft.com'),
    'company_phone': fields.String(description='شماره تماس شرکت', example='+1-425-882-8080'),
    'company_value': fields.String(description='سال تاسیس شرکت', example='1975'),
    'last_post_content': fields.String(description='محتوای آخرین پست شرکت در LinkedIn', example='Excited to announce our new product...'),
    'post_created_at': fields.String(description='تاریخ انتشار پست در LinkedIn', example='2025-10-23 10:30:00', allow_null=True),
    'comments': fields.Integer(description='تعداد کامنت‌های پست', example=42),
    'comments_text': fields.String(description='محتوای کامنت‌ها (جدا شده با |)', example='Great work! | Looking forward to this | Amazing innovation')
})

# مدل صف صفحه
page_queue_info = content_ns.model('PageQueueInfo', {
    'id': fields.Integer(description='شناسه صف', example=3),
    'page_name': fields.String(description='نام صفحه', example='microsoft'),
    'status': fields.String(description='وضعیت', example='completed', enum=['pending', 'processing', 'completed', 'failed']),
    'created_at': fields.String(description='تاریخ ایجاد', example='2025-10-23 14:00:00'),
    'started_at': fields.String(description='تاریخ شروع', example='2025-10-23 14:01:00'),
    'completed_at': fields.String(description='تاریخ اتمام', example='2025-10-23 14:05:00'),
    'error_message': fields.String(description='پیام خطا', example=None)
})

# مدل خروجی کامل داده صفحه
page_full_data_response = content_ns.model('PageFullDataResponse', {
    'status': fields.String(description='وضعیت', example='success', enum=['success', 'processing', 'pending', 'failed', 'error']),
    'message': fields.String(description='پیام', example='اطلاعات صفحه با موفقیت دریافت شد'),
    'data': fields.Nested(content_ns.model('PageFullData', {
        'queue': fields.Nested(page_queue_info, description='اطلاعات صف'),
        'page_data': fields.Nested(page_data_detail, description='اطلاعات صفحه', allow_null=True)
    }))
})

# مدل آیتم لیست صفحات
page_list_item = content_ns.model('PageListItem', {
    'id': fields.Integer(description='شناسه صف', example=3),
    'page_name': fields.String(description='نام صفحه شرکت', example='microsoft'),
    'status': fields.String(description='وضعیت پردازش', example='completed', enum=['pending', 'processing', 'completed', 'failed']),
    'created_at': fields.String(description='تاریخ افزودن به صف', example='2025-10-23 14:00:00'),
    'started_at': fields.String(description='تاریخ شروع پردازش', example='2025-10-23 14:01:00'),
    'completed_at': fields.String(description='تاریخ اتمام پردازش', example='2025-10-23 14:05:00'),
    'duration_seconds': fields.Float(description='مدت زمان پردازش (ثانیه)', example=240.0),
    'page_title': fields.String(description='عنوان کامل صفحه', example='Microsoft'),
    # برای سازگاری با نسخه‌های قبلی، فیلد قدیمی حفظ شده است
    'company_followers': fields.String(description='تعداد فالوئرهای شرکت (سازگار با نسخه قدیم)', example='20,456,789 followers'),
    # نسخه جدید: اطلاعات شرکت به صورت شیء تو در تو
    'company_info': fields.Nested(content_ns.model('CompanyInfoList', {
        'industry': fields.String(description='صنعت شرکت', example='Software Development'),
        'location': fields.String(description='موقعیت مکانی شرکت', example='Tehran, Tehran'),
        'followers': fields.String(description='تعداد فالوئرهای شرکت در LinkedIn', example='5K followers'),
        'employees': fields.String(description='تعداد کارمندان شرکت', example='51-200 employees')
    }), description='اطلاعات شرکت (برای نمایش در لیست)'),
    'error_message': fields.String(description='پیام خطا در صورت شکست', example=None)
})

# مدل خروجی لیست صفحات
page_list_response = content_ns.model('PageListResponse', {
    'status': fields.String(description='وضعیت', example='success'),
    'message': fields.String(description='پیام', example='لیست صفحات با موفقیت دریافت شد'),
    'total': fields.Integer(description='تعداد کل', example=12),
    'data': fields.List(fields.Nested(page_list_item), description='لیست صفحات')
})


# ========================================
# 📦 Legacy Models (برای سازگاری با کدهای قدیمی)
# ========================================

page_list_model = api.model('PageList', {
    'status': fields.String(description='وضعیت درخواست', example='success'),
    'message': fields.String(description='پیام پاسخ'),
    'data': fields.List(fields.Nested(api.model('Page', {
        'id': fields.Integer(description='شناسه پیج'),
        'username': fields.String(description='نام کاربری پیج'),
        'followers': fields.Integer(description='تعداد فالوئرها', required=False),
        'following': fields.Integer(description='تعداد فالوئینگ‌ها', required=False),
        'caption': fields.String(description='بیوی پیج', required=False),
        'number_of_posts': fields.Integer(description='تعداد پست‌ها', required=False),
        'profile_picture_base64': fields.String(description='بیس 64 '),

    })), description='لیست پیج‌ها')
})


hashtag_model = api.model('HashtagRequest', {
    'hashtags': fields.List(fields.String, required=True, description='لیست هشتگ‌ها برای پردازش'),
    'post_count': fields.Integer(description='نهایت تعداد پست بررسی شده'),
    'comment_count': fields.Integer(description='نهایت تعداد کامنت بررسی شده'),
})


comment_model = api.model('Comment', {
    'id': fields.Integer(description='شناسه کامنت'),
    'text': fields.String(description='متن کامنت'),
})

post_model = api.model('Post', {
    'id': fields.Integer(description='شناسه پست'),
    'caption': fields.String(description='کپشن پست'),
    'post_url': fields.String(description='یو آر ال پست'),
    'comments': fields.List(fields.Nested(comment_model), description='لیست کامنت‌ها')
})






create_output_model = api.model('PostList', {
    'status': fields.String(description='وضعیت درخواست', example='success'),
    'message': fields.String(description='پیام پاسخ'),
    'group_id': fields.Integer(description='شناسه گروه'),
})


start_input_model = api.model('StartHashtagInput', {
    'hashtag': fields.String(required=True, description='هشتگ مورد نظر'),
    'max_posts': fields.Integer(description='حداکثر تعداد پست برای جمع‌آوری (پیش‌فرض: 5)'),
    'max_comments': fields.Integer(description='حداکثر تعداد کامنت برای هر پست (پیش‌فرض: 5)'),
    'user_id': fields.Integer(description='شناسه کاربر برای دریافت Socket Events (اختیاری)'),
})

# مدل Response برای افزودن به صف
queue_hashtag_response = api.model('QueueHashtagResponse', {
    'status': fields.String(description='وضعیت درخواست', example='success'),
    'message': fields.String(description='پیام توضیحی'),
    'queue_id': fields.Integer(description='شناسه صف - برای بررسی وضعیت استفاده کنید'),
    'data': fields.Nested(api.model('QueueHashtagData', {
        'hashtag': fields.String(description='هشتگ ثبت شده'),
        'max_posts': fields.Integer(description='حداکثر پست'),
        'max_comments': fields.Integer(description='حداکثر کامنت'),
        'user_id': fields.Integer(description='شناسه کاربر', allow_null=True)
    }), description='اطلاعات هشتگ در صف')
})

post_list_model = api.model('Post', {
    'link': fields.String(description='لینک پست'),
    'caption': fields.String(description='متن کپشن'),
    'reactions': fields.String(description='تعداد واکنش‌ها'),
    'comments': fields.String(description='تعداد کامنت‌ها'),
    'username': fields.String(description='نام کاربری پست'),
    'comments_detail': fields.List(fields.Nested(api.model('Comment', {
        'commenter': fields.String(description='نام کامنت گذار'),
        'comment_text': fields.String(description='متن کامنت')
    })), description='جزئیات کامنت‌ها')
})

all_model = api.model('HashtagGroup', {
    'group_id': fields.Integer(description='شناسه گروه'),
    'post_count': fields.Integer(description='تعداد پست‌ها در گروه'),
    'hashtags': fields.List(fields.Nested(api.model('Hashtag', {
        'hashtag_name': fields.String(description='نام هشتگ'),
        'posts': fields.List(fields.Nested(api.model('Post', {
            'post_url': fields.String(description='یو آر ال پست'),
            'caption': fields.String(description='کپشن پست'),
            'comments': fields.List(fields.Nested(api.model('Comment', {
                'text': fields.String(description='متن کامنت'),
            })), description='لیست کامنت‌ها')
        })), description='لیست پست‌های مرتبط با هشتگ')
    })), description='لیست هشتگ‌ها و پست‌های مربوط به آن‌ها')
})

all_data_model = api.model('PostList', {
    'status': fields.String(description='وضعیت درخواست', example='success'),
    'message': fields.String(description='پیام پاسخ'),
    'data': fields.List(fields.Nested(all_model), description='لیست پست‌ها')
})


start_page_model2 = api.model('Page', {
    'page': fields.String(description='پیج'),
})

page_list_model2 = api.model('PageDetails', {
    'page_title': fields.String(description='عنوان صفحه لینکدین / نام شرکت', example='Microsoft'),
    'page_description': fields.String(description='توضیحات صفحه', example='At Microsoft, our mission is...'),
    'page_overview': fields.String(description='بررسی کلی صفحه', example='Microsoft is a leading technology company...'),
    'last_post_content': fields.String(description='محتوای آخرین پست', example='Excited to announce...'),
    'company_info': fields.Nested(api.model('CompanyInfoLegacy', {
        'industry': fields.String(description='صنعت شرکت', example='Software Development', attribute='company_industry'),
        'location': fields.String(description='موقعیت شرکت', example='Redmond, Washington', attribute='company_location'),
        'followers': fields.String(description='تعداد فالوئرهای شرکت در LinkedIn', example='20,456,789 followers', attribute='company_followers'),
        'employees': fields.String(description='تعداد کارمندان شرکت', example='10,001+ employees', attribute='company_employees')
    }), attribute=lambda x: x),
    'company_link': fields.String(description='وبسایت شرکت', example='https://www.microsoft.com'),
    'company_phone': fields.String(description='شماره تلفن شرکت', example='+1-425-882-8080'),
    'members_count': fields.String(description='تعداد اعضای شرکت', example=''),
    'company_value': fields.String(description='سال تاسیس شرکت', example='1975')
})




page_output = api.model('SingleTask', {
    'status': fields.String(description='وضعیت درخواست', example='success'),
    'message': fields.String(description='پیام پاسخ'),
    'data': fields.Nested(page_list_model2, description='اطلاعات تسک')
})

post_output = api.model('SingleTask', {
    'status': fields.String(description='وضعیت درخواست', example='success'),
    'message': fields.String(description='پیام پاسخ'),
    'data': fields.Nested(post_list_model, description='اطلاعات تسک')
})


# ========================================
# 🆕 Swagger Models برای Queue System
# ========================================

# مدل درخواست افزودن هشتگ به صف
hashtag_queue_input = api.model('HashtagQueueInput', {
    'hashtag': fields.String(required=True, description='هشتگ مورد نظر (بدون #)', example='python'),
    'max_posts': fields.Integer(description='حداکثر تعداد پست (پیش‌فرض: 5)', default=5, example=10),
    'max_comments': fields.Integer(description='حداکثر تعداد کامنت در هر پست (پیش‌فرض: 5)', default=5, example=5),
    'user_id': fields.Integer(description='شناسه کاربر برای Socket events (اختیاری)', required=False, example=1, allow_null=True)
})

# مدل پاسخ افزودن به صف (یکسان برای hashtag و page)
queue_response = api.model('QueueResponse', {
    'status': fields.String(description='وضعیت درخواست', example='success', enum=['success', 'error', 'info']),
    'message': fields.String(description='پیام پاسخ', example='در صف قرار گرفت'),
    'queue_id': fields.Integer(description='شناسه صف - برای بررسی وضعیت استفاده کنید', example=5),
    'data': fields.Raw(description='اطلاعات اضافی (نام صفحه یا هشتگ و تنظیمات)')
})

# مدل اطلاعات صف هشتگ
hashtag_queue_item = api.model('HashtagQueueItem', {
    'id': fields.Integer(description='شناسه صف'),
    'hashtag': fields.String(description='نام هشتگ'),
    'max_posts': fields.Integer(description='حداکثر تعداد پست'),
    'max_comments': fields.Integer(description='حداکثر تعداد کامنت'),
    'user_id': fields.Integer(description='شناسه کاربر'),
    'status': fields.String(description='وضعیت', enum=['pending', 'processing', 'completed', 'failed']),
    'error_message': fields.String(description='پیام خطا (در صورت وجود)'),
    'created_at': fields.String(description='تاریخ ایجاد'),
    'started_at': fields.String(description='تاریخ شروع پردازش'),
    'completed_at': fields.String(description='تاریخ اتمام')
})

# مدل پست جمع‌آوری شده
collected_post = api.model('CollectedPost', {
    'post_id': fields.Integer(description='شناسه پست'),
    'post_link': fields.String(description='لینک پست'),
    'caption': fields.String(description='متن کپشن'),
    'reactions': fields.String(description='تعداد ری‌اکشن‌ها'),
    'comments': fields.String(description='تعداد کامنت‌ها'),
    'username': fields.String(description='نام کاربری'),
    'analyzed': fields.Integer(description='وضعیت تحلیل'),
    'analysis_status': fields.String(description='وضعیت تحلیل', enum=['pending', 'processing', 'completed', 'failed']),
    'created_at': fields.String(description='تاریخ ایجاد'),
    'comments_count': fields.Integer(description='تعداد کامنت‌های جمع‌آوری شده')
})

# مدل وضعیت کامل هشتگ
hashtag_full_status = api.model('HashtagFullStatus', {
    'status': fields.String(description='وضعیت درخواست', example='success'),
    'data': fields.Nested(api.model('HashtagStatusData', {
        'queue': fields.Nested(hashtag_queue_item, description='اطلاعات صف'),
        'posts': fields.List(fields.Nested(collected_post), description='لیست پست‌های جمع‌آوری شده'),
        'posts_count': fields.Integer(description='تعداد کل پست‌ها'),
        'total_comments_count': fields.Integer(description='تعداد کل کامنت‌ها')
    }))
})

# مدل لیست صف هشتگ‌ها
hashtag_queue_list = api.model('HashtagQueueList', {
    'status': fields.String(description='وضعیت', example='success'),
    'count': fields.Integer(description='تعداد آیتم‌ها'),
    'data': fields.List(fields.Nested(hashtag_queue_item), description='لیست صف')
})

# مدل وضعیت Worker
worker_status_model = api.model('WorkerStatus', {
    'status': fields.String(description='وضعیت', example='success'),
    'data': fields.Nested(api.model('WorkerStatusData', {
        'worker': fields.Nested(api.model('WorkerInfo', {
            'is_running': fields.Boolean(description='آیا Worker در حال اجرا است'),
            'is_processing': fields.Boolean(description='آیا در حال پردازش است'),
            'current_task_type': fields.String(description='نوع تسک فعلی', enum=['hashtag', 'page', 'link', None]),
            'current_task_id': fields.Integer(description='شناسه تسک فعلی')
        })),
        'hashtags_queue': fields.Nested(api.model('HashtagsQueueStats', {
            'pending': fields.Integer(description='تعداد در انتظار'),
            'processing': fields.Integer(description='تعداد در حال پردازش'),
            'completed': fields.Integer(description='تعداد تکمیل شده'),
            'failed': fields.Integer(description='تعداد ناموفق'),
            'total': fields.Integer(description='مجموع')
        })),
        'links_analysis': fields.Nested(api.model('LinksAnalysisStats', {
            'pending': fields.Integer(description='تعداد در انتظار'),
            'processing': fields.Integer(description='تعداد در حال پردازش'),
            'completed': fields.Integer(description='تعداد تکمیل شده'),
            'total': fields.Integer(description='مجموع')
        }))
    }))
})

# ========================================
# 🆕 Swagger Models برای Page Queue
# ========================================

# مدل درخواست افزودن صفحه به صف
page_queue_input = api.model('PageQueueInput', {
    'page_name': fields.String(required=True, description='نام صفحه LinkedIn شرکت (بدون @ یا پیشوند)', example='microsoft'),
    'user_id': fields.Integer(description='شناسه کاربر برای Socket events (اختیاری)', required=False, example=1, allow_null=True)
})

# مدل اطلاعات صف صفحات
page_queue_item = api.model('PageQueueItem', {
    'id': fields.Integer(description='شناسه صف'),
    'page_name': fields.String(description='نام صفحه'),
    'user_id': fields.Integer(description='شناسه کاربر'),
    'status': fields.String(description='وضعیت', enum=['pending', 'processing', 'completed', 'failed']),
    'error_message': fields.String(description='پیام خطا (در صورت وجود)'),
    'created_at': fields.String(description='تاریخ ایجاد'),
    'started_at': fields.String(description='تاریخ شروع پردازش'),
    'completed_at': fields.String(description='تاریخ اتمام')
})

# مدل اطلاعات شرکت (زیرمجموعه)
company_info_model = api.model('CompanyInfo', {
    'industry': fields.String(description='صنعت شرکت', example='Software Development', attribute='company_industry'),
    'location': fields.String(description='موقعیت مکانی شرکت', example='Redmond, Washington', attribute='company_location'),
    'followers': fields.String(description='تعداد فالوئرهای شرکت در LinkedIn', example='20,456,789 followers', attribute='company_followers'),
    'employees': fields.String(description='تعداد کارمندان شرکت', example='10,001+ employees', attribute='company_employees')
})

# مدل اطلاعات صفحه جمع‌آوری شده (کامل - 11 فیلد)
page_data_model = api.model('PageData', {
    'id': fields.Integer(description='شناسه رکورد در دیتابیس', example=1),
    'page_title': fields.String(description='عنوان صفحه / نام شرکت', example='Microsoft'),
    'page_description': fields.String(description='توضیحات کوتاه صفحه', example='At Microsoft, our mission is...'),
    'page_overview': fields.String(description='بررسی کلی شرکت (Overview)', example='Microsoft is a leading technology company...'),
    'last_post_content': fields.String(description='محتوای آخرین پست', example='Excited to announce our new product...'),
    'company_info': fields.Nested(company_info_model, description='اطلاعات شرکت (صنعت، موقعیت، فالوئرها، کارمندان)', attribute=lambda x: x),
    'company_link': fields.String(description='وبسایت شرکت', example='https://www.microsoft.com'),
    'company_phone': fields.String(description='شماره تلفن شرکت', example='+1-425-882-8080'),
    'company_value': fields.String(description='سال تاسیس شرکت', example='1975'),
    'created_at': fields.String(description='تاریخ جمع‌آوری داده', example='2025-10-23 14:05:00'),
    'page_queue_id': fields.Integer(description='شناسه صف مربوطه', example=3)
})

# مدل وضعیت کامل صفحه
page_full_status = api.model('PageFullStatus', {
    'status': fields.String(description='وضعیت درخواست', example='success', enum=['success', 'error']),
    'data': fields.Nested(api.model('PageStatusData', {
        'queue_id': fields.Integer(description='شناسه صف در pages_queue', example=3),
        'page_name': fields.String(description='نام صفحه شرکت در LinkedIn', example='microsoft'),
        'status': fields.String(description='وضعیت پردازش', example='completed', enum=['pending', 'processing', 'completed', 'failed']),
        'user_id': fields.Integer(description='شناسه کاربر', example=1, allow_null=True),
        'error_message': fields.String(description='پیام خطا در صورت شکست', example=None, allow_null=True),
        'created_at': fields.String(description='تاریخ افزودن به صف', example='2025-10-23 14:00:00'),
        'started_at': fields.String(description='تاریخ شروع پردازش', example='2025-10-23 14:01:00', allow_null=True),
        'completed_at': fields.String(description='تاریخ اتمام پردازش', example='2025-10-23 14:05:00', allow_null=True),
        'page_data': fields.Nested(page_data_model, description='اطلاعات جمع‌آوری شده صفحه (فقط برای status=completed)', allow_null=True)
    }))
})

# مدل لیست صف صفحات
page_queue_list = api.model('PageQueueList', {
    'status': fields.String(description='وضعیت', example='success'),
    'count': fields.Integer(description='تعداد آیتم‌ها'),
    'data': fields.List(fields.Nested(page_queue_item), description='لیست صف')
})

# مدل آمار صف صفحات
page_queue_stats = api.model('PageQueueStats', {
    'status': fields.String(description='وضعیت', example='success'),
    'stats': fields.Nested(api.model('PageStatsData', {
        'pending': fields.Integer(description='تعداد در انتظار'),
        'processing': fields.Integer(description='تعداد در حال پردازش'),
        'completed': fields.Integer(description='تعداد تکمیل شده'),
        'failed': fields.Integer(description='تعداد ناموفق'),
        'total': fields.Integer(description='مجموع')
    }))
})
