"""
اسکریپت Migration برای تصحیح و آپدیت دیتابیس
این اسکریپت جداول و ستون‌های مورد نیاز سیستم صف را ایجاد می‌کند
"""

import sys
import os

# اضافه کردن مسیر پروژه به Python Path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import get_db_connection
from utils.logger import bot_logger

def check_table_exists(cursor, table_name):
    """بررسی وجود جدول"""
    cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
    return cursor.fetchone() is not None

def check_column_exists(cursor, table_name, column_name):
    """بررسی وجود ستون در جدول"""
    cursor.execute(f"""
        SELECT COUNT(*) as count 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = '{table_name}' 
        AND COLUMN_NAME = '{column_name}'
    """)
    result = cursor.fetchone()
    return result['count'] > 0 if result else False

def create_hashtags_queue_table(conn, cursor):
    """ایجاد جدول صف هشتگ‌ها"""
    try:
        if check_table_exists(cursor, 'hashtags_queue'):
            bot_logger.info("✅ جدول hashtags_queue قبلاً وجود دارد")
            return True
        
        bot_logger.info("🔨 در حال ایجاد جدول hashtags_queue...")
        
        cursor.execute("""
            CREATE TABLE hashtags_queue (
                id INT PRIMARY KEY AUTO_INCREMENT,
                hashtag VARCHAR(255) NOT NULL,
                max_posts INT DEFAULT 5,
                max_comments INT DEFAULT 5,
                status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending',
                error_message TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP NULL,
                completed_at TIMESTAMP NULL,
                INDEX idx_status (status),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        conn.commit()
        
        bot_logger.info("✅ جدول hashtags_queue با موفقیت ایجاد شد")
        return True
        
    except Exception as e:
        bot_logger.error(f"❌ خطا در ایجاد جدول hashtags_queue: {e}")
        return False

def add_column_if_not_exists(conn, cursor, table_name, column_name, column_definition):
    """اضافه کردن ستون در صورت عدم وجود"""
    try:
        if check_column_exists(cursor, table_name, column_name):
            bot_logger.info(f"✅ ستون {column_name} در جدول {table_name} قبلاً وجود دارد")
            return True
        
        bot_logger.info(f"🔨 در حال اضافه کردن ستون {column_name} به جدول {table_name}...")
        
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_definition}")
        conn.commit()
        
        bot_logger.info(f"✅ ستون {column_name} با موفقیت اضافه شد")
        return True
        
    except Exception as e:
        bot_logger.error(f"❌ خطا در اضافه کردن ستون {column_name}: {e}")
        return False

def create_keywords_queue_table(conn, cursor):
    """ایجاد جدول صف کلمات کلیدی"""
    try:
        if check_table_exists(cursor, 'keywords_queue'):
            bot_logger.info("✅ جدول keywords_queue قبلاً وجود دارد")
            return True
        
        bot_logger.info("🔨 در حال ایجاد جدول keywords_queue...")
        
        cursor.execute("""
            CREATE TABLE keywords_queue (
                id INT PRIMARY KEY AUTO_INCREMENT,
                keyword VARCHAR(500) NOT NULL COMMENT 'Search keyword or phrase',
                max_posts INT DEFAULT 5,
                max_comments INT DEFAULT 5,
                user_id INT NULL,
                status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending',
                error_message TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP NULL,
                completed_at TIMESTAMP NULL,
                INDEX idx_status (status),
                INDEX idx_created_at (created_at),
                INDEX idx_keyword (keyword)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        conn.commit()
        
        bot_logger.info("✅ جدول keywords_queue با موفقیت ایجاد شد")
        return True
        
    except Exception as e:
        bot_logger.error(f"❌ خطا در ایجاد جدول keywords_queue: {e}")
        return False

def create_pages_queue_table(conn, cursor):
    """ایجاد جدول صف Page ها"""
    try:
        if check_table_exists(cursor, 'pages_queue'):
            bot_logger.info("✅ جدول pages_queue قبلاً وجود دارد")
            return True
    
        bot_logger.info("🔨 در حال ایجاد جدول pages_queue...")
    
        cursor.execute("""
            CREATE TABLE pages_queue (
                id INT PRIMARY KEY AUTO_INCREMENT,
                page_name VARCHAR(255) NOT NULL,
                user_id INT NULL,
                status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending',
                error_message TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP NULL,
                completed_at TIMESTAMP NULL,
                INDEX idx_status (status),
                INDEX idx_created_at (created_at),
                INDEX idx_page_name (page_name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        conn.commit()
    
        bot_logger.info("✅ جدول pages_queue با موفقیت ایجاد شد")
        return True
    
    except Exception as e:
        bot_logger.error(f"❌ خطا در ایجاد جدول pages_queue: {e}")
        return False

def update_linkdeen_pages_table(conn, cursor):
    """آپدیت جدول linkdeen_pages"""
    try:
        if not check_table_exists(cursor, 'linkdeen_pages'):
            bot_logger.warning("⚠️ جدول linkdeen_pages وجود ندارد، رد می‌شود")
            return True
    
        bot_logger.info("🔨 در حال آپدیت جدول linkdeen_pages...")
    
        # اضافه کردن ستون page_queue_id
        if add_column_if_not_exists(conn, cursor, 'linkdeen_pages', 'page_queue_id', 'page_queue_id INT NULL'):
            # اضافه کردن index
            try:
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM INFORMATION_SCHEMA.STATISTICS
                    WHERE TABLE_SCHEMA = DATABASE()
                    AND TABLE_NAME = 'linkdeen_pages'
                    AND INDEX_NAME = 'idx_page_queue_id'
                """)
                result = cursor.fetchone()
            
                if result['count'] == 0:
                    cursor.execute("ALTER TABLE linkdeen_pages ADD INDEX idx_page_queue_id (page_queue_id)")
                    conn.commit()
                    bot_logger.info("✅ Index idx_page_queue_id اضافه شد")
                else:
                    bot_logger.info("✅ Index idx_page_queue_id قبلاً وجود دارد")
            except Exception as e:
                bot_logger.warning(f"⚠️ خطا در اضافه کردن index: {e}")
    
        bot_logger.info("✅ جدول linkdeen_pages با موفقیت آپدیت شد")
        return True
    
    except Exception as e:
        bot_logger.error(f"❌ خطا در آپدیت جدول linkdeen_pages: {e}")
        return False

def ensure_page_name_on_linkdeen_pages(conn, cursor):
    """اطمینان از وجود ستون page_name در جدول linkdeen_pages"""
    try:
        if not check_table_exists(cursor, 'linkdeen_pages'):
            bot_logger.warning("⚠️ جدول linkdeen_pages وجود ندارد، رد می‌شود")
            return True

        if check_column_exists(cursor, 'linkdeen_pages', 'page_name'):
            bot_logger.info("✅ ستون page_name در جدول linkdeen_pages قبلاً وجود دارد")
            return True

        bot_logger.info("🔨 در حال اضافه کردن ستون page_name به جدول linkdeen_pages...")
        cursor.execute("ALTER TABLE linkdeen_pages ADD COLUMN page_name VARCHAR(255) NULL")
        conn.commit()

        # ایجاد ایندکس اختیاری برای بهبود جستجو بر اساس نام صفحه
        try:
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'linkdeen_pages'
                AND INDEX_NAME = 'idx_page_name'
            """)
            result = cursor.fetchone()
            if result and result.get('count', 0) == 0:
                cursor.execute("ALTER TABLE linkdeen_pages ADD INDEX idx_page_name (page_name)")
                conn.commit()
                bot_logger.info("✅ Index idx_page_name به جدول linkdeen_pages اضافه شد")
        except Exception as e:
            bot_logger.warning(f"⚠️ خطا در اضافه کردن index idx_page_name: {e}")

        bot_logger.info("✅ ستون page_name به جدول linkdeen_pages اضافه شد")
        return True

    except Exception as e:
        bot_logger.error(f"❌ خطا در اضافه کردن ستون page_name به linkdeen_pages: {e}")
        return False

def ensure_linkdeen_pages_required_columns(conn, cursor):
    """اطمینان از وجود ستون‌های موردنیاز در جدول linkdeen_pages مطابق با منطق get_page2"""
    try:
        if not check_table_exists(cursor, 'linkdeen_pages'):
            bot_logger.warning("⚠️ جدول linkdeen_pages وجود ندارد، رد می‌شود")
            return True

        required_columns = [
            ( 'page_queue_id',  'page_queue_id INT NULL' )
        ]

        success = True
        for col_name, col_def in required_columns:
            ok = add_column_if_not_exists(conn, cursor, 'linkdeen_pages', col_name, col_def)
            success = success and ok

        # Index برای page_queue_id اگر نبود
        try:
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'linkdeen_pages'
                AND INDEX_NAME = 'idx_page_queue_id'
            """)
            result = cursor.fetchone()
            if result and result.get('count', 0) == 0:
                cursor.execute("ALTER TABLE linkdeen_pages ADD INDEX idx_page_queue_id (page_queue_id)")
                conn.commit()
                bot_logger.info("✅ Index idx_page_queue_id به جدول linkdeen_pages اضافه شد")
        except Exception as e:
            bot_logger.warning(f"⚠️ خطا در اضافه کردن index idx_page_queue_id: {e}")

        return success

    except Exception as e:
        bot_logger.error(f"❌ خطا در اطمینان از ستون‌های linkdeen_pages: {e}")
        return False

def fix_company_value_column_size(conn, cursor):
    """تغییر سایز ستون company_value از VARCHAR(50) به TEXT"""
    try:
        if not check_table_exists(cursor, 'linkdeen_pages'):
            bot_logger.warning("⚠️ جدول linkdeen_pages وجود ندارد")
            return False
        
        if not check_column_exists(cursor, 'linkdeen_pages', 'company_value'):
            bot_logger.info("ℹ️ ستون company_value وجود ندارد، نیازی به تغییر نیست")
            return True
        
        bot_logger.info("🔨 در حال تغییر سایز ستون company_value...")
        
        cursor.execute("""
            ALTER TABLE linkdeen_pages 
            MODIFY COLUMN company_value TEXT DEFAULT NULL
        """)
        conn.commit()
        
        bot_logger.info("✅ ستون company_value با موفقیت به TEXT تبدیل شد")
        return True
        
    except Exception as e:
        bot_logger.error(f"❌ خطا در تغییر سایز ستون company_value: {e}")
        return False

def add_post_created_at_column(conn, cursor):
    """اضافه کردن ستون post_created_at به linkdeen_pages"""
    try:
        if not check_table_exists(cursor, 'linkdeen_pages'):
            bot_logger.warning("⚠️ جدول linkdeen_pages وجود ندارد")
            return True
        
        if check_column_exists(cursor, 'linkdeen_pages', 'post_created_at'):
            bot_logger.info("✅ ستون post_created_at در جدول linkdeen_pages قبلاً وجود دارد")
            return True
        
        bot_logger.info("🔨 در حال اضافه کردن ستون post_created_at به جدول linkdeen_pages...")
        
        cursor.execute("""
            ALTER TABLE linkdeen_pages 
            ADD COLUMN post_created_at DATETIME NULL 
            COMMENT 'Timestamp when the LinkedIn post was actually created'
            AFTER last_post_content
        """)
        conn.commit()
        
        bot_logger.info("✅ ستون post_created_at با موفقیت اضافه شد")
        return True
        
    except Exception as e:
        bot_logger.error(f"❌ خطا در اضافه کردن ستون post_created_at: {e}")
        return False

def add_comments_columns(conn, cursor):
    """اضافه کردن ستون‌های comments و comments_text به linkdeen_pages"""
    try:
        if not check_table_exists(cursor, 'linkdeen_pages'):
            bot_logger.warning("⚠️ جدول linkdeen_pages وجود ندارد")
            return True
        
        success = True
        
        # Add comments count column
        if not check_column_exists(cursor, 'linkdeen_pages', 'comments'):
            bot_logger.info("🔨 در حال اضافه کردن ستون comments به جدول linkdeen_pages...")
            cursor.execute("""
                ALTER TABLE linkdeen_pages 
                ADD COLUMN comments INT DEFAULT 0 
                AFTER company_value
            """)
            conn.commit()
            bot_logger.info("✅ ستون comments با موفقیت اضافه شد")
        else:
            bot_logger.info("✅ ستون comments در جدول linkdeen_pages قبلاً وجود دارد")
        
        # Add comments_text column
        if not check_column_exists(cursor, 'linkdeen_pages', 'comments_text'):
            bot_logger.info("🔨 در حال اضافه کردن ستون comments_text به جدول linkdeen_pages...")
            cursor.execute("""
                ALTER TABLE linkdeen_pages 
                ADD COLUMN comments_text TEXT DEFAULT NULL 
                AFTER comments
            """)
            conn.commit()
            bot_logger.info("✅ ستون comments_text با موفقیت اضافه شد")
        else:
            bot_logger.info("✅ ستون comments_text در جدول linkdeen_pages قبلاً وجود دارد")
        
        return success
        
    except Exception as e:
        bot_logger.error(f"❌ خطا در اضافه کردن ستون‌های comments: {e}")
        return False

def remove_duplicate_columns_from_linkdeen_pages(conn, cursor):
    """حذف ستون‌های تکراری از linkdeen_pages"""
    try:
        if not check_table_exists(cursor, 'linkdeen_pages'):
            bot_logger.warning("⚠️ جدول linkdeen_pages وجود ندارد")
            return True
        
        bot_logger.info("🗑️ در حال حذف ستون‌های تکراری از linkdeen_pages...")
        
        duplicate_columns = [
            'page_name',      # تکراری - اطلاعات در pages_queue است
            'company_name',   # تکراری - از page_title استفاده می‌شود
            'followers',      # تکراری - company_followers موجود است
            'description',    # تکراری - page_description موجود است
            'website',        # تکراری - company_link موجود است
            'industry',       # تکراری - company_industry موجود است
            'company_size'    # تکراری - company_employees موجود است
        ]
        
        removed_count = 0
        for col in duplicate_columns:
            if check_column_exists(cursor, 'linkdeen_pages', col):
                try:
                    bot_logger.info(f"🗑️ حذف ستون تکراری '{col}' از linkdeen_pages...")
                    cursor.execute(f"ALTER TABLE linkdeen_pages DROP COLUMN `{col}`")
                    conn.commit()
                    bot_logger.info(f"✅ ستون '{col}' حذف شد")
                    removed_count += 1
                except Exception as e:
                    bot_logger.warning(f"⚠️ خطا در حذف ستون '{col}': {e}")
                    conn.rollback()
            else:
                bot_logger.info(f"✅ ستون '{col}' از قبل وجود ندارد")
        
        if removed_count > 0:
            bot_logger.info(f"✅ {removed_count} ستون تکراری حذف شد")
        else:
            bot_logger.info("✅ هیچ ستون تکراری برای حذف وجود نداشت")
        
        return True
        
    except Exception as e:
        bot_logger.error(f"❌ خطا در حذف ستون‌های تکراری: {e}")
        return False

def add_user_id_to_hashtags_queue(conn, cursor):
    """اضافه کردن user_id به جدول hashtags_queue"""
    try:
        if not check_table_exists(cursor, 'hashtags_queue'):
            bot_logger.warning("⚠️ جدول hashtags_queue وجود ندارد")
            return False
    
        bot_logger.info("🔨 در حال بررسی ستون user_id در hashtags_queue...")
    
        return add_column_if_not_exists(
            conn, cursor, 
            'hashtags_queue', 
            'user_id', 
            'user_id INT NULL AFTER max_comments'
        )
    
    except Exception as e:
        bot_logger.error(f"❌ خطا در اضافه کردن user_id: {e}")
        return False

def update_linkdeen_posts_table(conn, cursor):
    """آپدیت جدول linkdeen_posts"""
    try:
        if not check_table_exists(cursor, 'linkdeen_posts'):
            bot_logger.error("❌ جدول linkdeen_posts وجود ندارد!")
            return False
        
        bot_logger.info("🔨 در حال آپدیت جدول linkdeen_posts...")
        
        # اضافه کردن ستون‌های جدید
        columns = [
            ('hashtag_id', 'hashtag_id INT NULL'),
            ('keyword_id', 'keyword_id INT NULL'),
            ('analyzed', 'analyzed TINYINT(1) DEFAULT 0'),
            ('analysis_status', "analysis_status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending'"),
            ('analysis_error', 'analysis_error TEXT NULL')
        ]
        
        for column_name, column_def in columns:
            add_column_if_not_exists(conn, cursor, 'linkdeen_posts', column_name, column_def)
        
        # اضافه کردن index‌ها
        bot_logger.info("🔨 در حال اضافه کردن index‌ها...")
        
        indexes = [
            ('idx_analyzed', 'analyzed'),
            ('idx_analysis_status', 'analysis_status'),
            ('idx_hashtag_id', 'hashtag_id'),
            ('idx_keyword_id', 'keyword_id')
        ]
        
        for index_name, column_name in indexes:
            try:
                # بررسی وجود index
                cursor.execute(f"""
                    SELECT COUNT(*) as count
                    FROM INFORMATION_SCHEMA.STATISTICS
                    WHERE TABLE_SCHEMA = DATABASE()
                    AND TABLE_NAME = 'linkdeen_posts'
                    AND INDEX_NAME = '{index_name}'
                """)
                result = cursor.fetchone()
                
                if result['count'] == 0:
                    cursor.execute(f"ALTER TABLE linkdeen_posts ADD INDEX {index_name} ({column_name})")
                    conn.commit()
                    bot_logger.info(f"✅ Index {index_name} اضافه شد")
                else:
                    bot_logger.info(f"✅ Index {index_name} قبلاً وجود دارد")
                    
            except Exception as e:
                bot_logger.warning(f"⚠️ خطا در اضافه کردن index {index_name}: {e}")
        
        bot_logger.info("✅ جدول linkdeen_posts با موفقیت آپدیت شد")
        return True
        
    except Exception as e:
        bot_logger.error(f"❌ خطا در آپدیت جدول linkdeen_posts: {e}")
        return False

def verify_migration(cursor):
    """بررسی موفقیت‌آمیز بودن migration"""
    bot_logger.info("\n🔍 در حال بررسی نتایج migration...")
    
    errors = []
    
    # بررسی جدول hashtags_queue
    if not check_table_exists(cursor, 'hashtags_queue'):
        errors.append("جدول hashtags_queue ایجاد نشده است")
    else:
        bot_logger.info("✅ جدول hashtags_queue موجود است")
    
    # بررسی جدول pages_queue
    if not check_table_exists(cursor, 'pages_queue'):
        errors.append("جدول pages_queue ایجاد نشده است")
    else:
        bot_logger.info("✅ جدول pages_queue موجود است")
    
    # بررسی ستون user_id در hashtags_queue
    if not check_column_exists(cursor, 'hashtags_queue', 'user_id'):
        errors.append("ستون user_id در جدول hashtags_queue وجود ندارد")
    else:
        bot_logger.info("✅ ستون user_id در hashtags_queue موجود است")
    
    # بررسی ستون‌های جدول linkdeen_posts
    required_columns = ['hashtag_id', 'analyzed', 'analysis_status', 'analysis_error']
    for column in required_columns:
        if not check_column_exists(cursor, 'linkdeen_posts', column):
            errors.append(f"ستون {column} در جدول linkdeen_posts وجود ندارد")
        else:
            bot_logger.info(f"✅ ستون {column} موجود است")
    
    # بررسی ستون page_queue_id در linkdeen_pages (اختیاری)
    if check_table_exists(cursor, 'linkdeen_pages'):
        if not check_column_exists(cursor, 'linkdeen_pages', 'page_queue_id'):
            bot_logger.warning("⚠️ ستون page_queue_id در جدول linkdeen_pages وجود ندارد")
        else:
            bot_logger.info("✅ ستون page_queue_id در linkdeen_pages موجود است")
        
        # بررسی که ستون‌های تکراری حذف شده باشند
        duplicate_cols = ['page_name', 'company_name', 'followers', 'description', 'website', 'industry', 'company_size']
        for col in duplicate_cols:
            if check_column_exists(cursor, 'linkdeen_pages', col):
                errors.append(f"ستون تکراری {col} هنوز در جدول linkdeen_pages وجود دارد")
            else:
                bot_logger.info(f"✅ ستون تکراری {col} از linkdeen_pages حذف شده است")
    
    if errors:
        bot_logger.error("\n❌ خطاهای یافت شده:")
        for error in errors:
            bot_logger.error(f"  - {error}")
        return False
    else:
        bot_logger.info("\n✅ همه تغییرات با موفقیت اعمال شد!")
        return True

def run_migration():
    """اجرای کامل migration"""
    bot_logger.info("=" * 60)
    bot_logger.info("🚀 شروع Migration دیتابیس")
    bot_logger.info("=" * 60)
    
    conn = None
    cursor = None
    
    try:
        # اتصال به دیتابیس
        bot_logger.info("📡 در حال اتصال به دیتابیس...")
        conn = get_db_connection()
        cursor = conn.cursor()
        bot_logger.info("✅ اتصال به دیتابیس برقرار شد")
        
        # 1️⃣ ایجاد جدول hashtags_queue
        if not create_hashtags_queue_table(conn, cursor):
            raise Exception("خطا در ایجاد جدول hashtags_queue")
        
        # 2️⃣ ایجاد جدول keywords_queue
        if not create_keywords_queue_table(conn, cursor):
            raise Exception("خطا در ایجاد جدول keywords_queue")
        
        # 3️⃣ ایجاد جدول pages_queue
        if not create_pages_queue_table(conn, cursor):
            raise Exception("خطا در ایجاد جدول pages_queue")
            # 3.1️⃣ اطمینان از وجود ستون page_name در جدول pages_queue
            if check_table_exists(cursor, 'pages_queue') and not check_column_exists(cursor, 'pages_queue', 'page_name'):
                bot_logger.info("🔨 ستون page_name در جدول pages_queue وجود ندارد، در حال اضافه کردن...")
                add_column_if_not_exists(conn, cursor, 'pages_queue', 'page_name', 'page_name VARCHAR(255) NOT NULL')
        
        # 4️⃣ اضافه کردن user_id به hashtags_queue
        if not add_user_id_to_hashtags_queue(conn, cursor):
            bot_logger.warning("⚠️ خطا در اضافه کردن user_id به hashtags_queue")
        
        # 5️⃣ آپدیت جدول linkdeen_posts
        if not update_linkdeen_posts_table(conn, cursor):
            raise Exception("خطا در آپدیت جدول linkdeen_posts")
        
        # 6️⃣ آپدیت جدول linkdeen_pages
        if not update_linkdeen_pages_table(conn, cursor):
            bot_logger.warning("⚠️ خطا در آپدیت جدول linkdeen_pages")
        
        # 5.1️⃣ حذف ستون‌های تکراری از linkdeen_pages
        if not remove_duplicate_columns_from_linkdeen_pages(conn, cursor):
            bot_logger.warning("⚠️ خطا در حذف ستون‌های تکراری از linkdeen_pages")
        
        # 5.2️⃣ اطمینان از وجود ستون‌های ضروری linkdeen_pages
        if not ensure_linkdeen_pages_required_columns(conn, cursor):
            bot_logger.warning("⚠️ برخی از ستون‌های ضروری linkdeen_pages ممکن است اضافه نشده باشند")
        
        # 5.3️⃣ تغییر سایز ستون company_value
        if not fix_company_value_column_size(conn, cursor):
            bot_logger.warning("⚠️ خطا در تغییر سایز ستون company_value")
        
        # 5.4️⃣ اضافه کردن ستون post_created_at
        if not add_post_created_at_column(conn, cursor):
            bot_logger.warning("⚠️ خطا در اضافه کردن ستون post_created_at")
        
        # 5.5️⃣ اضافه کردن ستون‌های comments و comments_text
        if not add_comments_columns(conn, cursor):
            bot_logger.warning("⚠️ خطا در اضافه کردن ستون‌های comments")
        
        # 6️⃣ بررسی نتایج
        if not verify_migration(cursor):
            raise Exception("برخی تغییرات اعمال نشدند")
        
        bot_logger.info("\n" + "=" * 60)
        bot_logger.info("🎉 Migration با موفقیت کامل شد!")
        bot_logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        bot_logger.error(f"\n❌ Migration با خطا مواجه شد: {e}")
        if conn:
            conn.rollback()
        return False
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        bot_logger.info("🔌 اتصال به دیتابیس بسته شد")

def show_database_structure(cursor):
    """نمایش ساختار جداول"""
    bot_logger.info("\n" + "=" * 60)
    bot_logger.info("📊 ساختار جداول:")
    bot_logger.info("=" * 60)
    
    # ساختار جدول hashtags_queue
    if check_table_exists(cursor, 'hashtags_queue'):
        bot_logger.info("\n🔹 جدول: hashtags_queue")
        cursor.execute("DESCRIBE hashtags_queue")
        for row in cursor.fetchall():
            default_val = str(row.get('Default', ''))
            bot_logger.info(f"  {row['Field']:20} {row['Type']:30} {row['Null']:5} {row['Key']:5} {default_val}")
    
    # ساختار جدول pages_queue
    if check_table_exists(cursor, 'pages_queue'):
        bot_logger.info("\n🔹 جدول: pages_queue")
        cursor.execute("DESCRIBE pages_queue")
        for row in cursor.fetchall():
            default_val = str(row.get('Default', ''))
            bot_logger.info(f"  {row['Field']:20} {row['Type']:30} {row['Null']:5} {row['Key']:5} {default_val}")
    
    # ساختار جدول linkdeen_posts (فقط ستون‌های جدید)
    if check_table_exists(cursor, 'linkdeen_posts'):
        bot_logger.info("\n🔹 جدول: linkdeen_posts (ستون‌های جدید)")
        cursor.execute("DESCRIBE linkdeen_posts")
        new_columns = ['hashtag_id', 'analyzed', 'analysis_status', 'analysis_error']
        for row in cursor.fetchall():
            if row['Field'] in new_columns:
                default_val = str(row.get('Default', ''))
                bot_logger.info(f"  {row['Field']:20} {row['Type']:30} {row['Null']:5} {row['Key']:5} {default_val}")
    
    # ساختار جدول linkdeen_pages (ستون page_queue_id)
    if check_table_exists(cursor, 'linkdeen_pages'):
        bot_logger.info("\n🔹 جدول: linkdeen_pages (ستون‌های مهم)")
        cursor.execute("DESCRIBE linkdeen_pages")
        important_columns = ['page_title', 'company_industry', 'company_location', 'company_followers', 'company_employees', 'page_queue_id']
        for row in cursor.fetchall():
            if row['Field'] in important_columns:
                default_val = str(row.get('Default', ''))
                bot_logger.info(f"  {row['Field']:20} {row['Type']:30} {row['Null']:5} {row['Key']:5} {default_val}")

if __name__ == "__main__":
    try:
        # اجرای migration
        success = run_migration()
        
        if success:
            # نمایش ساختار جداول
            conn = get_db_connection()
            cursor = conn.cursor()
            show_database_structure(cursor)
            cursor.close()
            conn.close()
            
            print("\n" + "=" * 60)
            print("✅ دیتابیس با موفقیت تصحیح شد!")
            print("=" * 60)
            print("\n📌 مراحل بعدی:")
            print("   1. برنامه را اجرا کنید: python app/app.py")
            print("   2. از endpoint جدید استفاده کنید: POST /api/hashtag/queue")
            print("   3. وضعیت Worker را چک کنید: GET /api/worker/status")
            print("\n📖 برای اطلاعات بیشتر: docs/QUEUE_SYSTEM.md")
            sys.exit(0)
        else:
            print("\n❌ Migration ناموفق بود. لطفاً خطاها را بررسی کنید.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Migration توسط کاربر لغو شد")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ خطای غیرمنتظره: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
