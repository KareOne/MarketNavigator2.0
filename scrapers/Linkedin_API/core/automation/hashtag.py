from config.config import get_db_connection, get_global_bot, socketio
import time
from core.bot.linkdeen_bot import LinkedinBot
import re
from selenium.webdriver.common.by import By
import random
import threading
from selenium.common.exceptions import NoSuchElementException
from utils.logger import bot_logger
import pyperclip
import os
from urllib.parse import quote_plus
from services.socket_handlers import SocketHandlers


def get_post(request):
    """
    این endpoint فقط هشتگ را در صف ذخیره می‌کند
    Worker خودش به صورت خودکار پردازش می‌کند
    """
    try:
        data = request.get_json()
        hashtag = data.get("hashtag")
        max_posts = data.get("max_posts", 5)
        max_comments = data.get("max_comments", 5)
        user_id = data.get("user_id")  # اختیاری - برای ارسال socket events
        
        if not hashtag:
            return {"status": "error", "message": "هشتگ الزامی است"}, 400
        
        # حذف # از ابتدای هشتگ
        hashtag = hashtag.strip()
        if hashtag.startswith('#'):
            hashtag = hashtag[1:]
        
        # ✅ حذف چک تکراری - اجازه به ایجاد هشتگ تکراری
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # ذخیره مستقیم در صف
        cursor.execute(
            "INSERT INTO hashtags_queue (hashtag, max_posts, max_comments, user_id, status) VALUES (%s, %s, %s, %s, 'pending')",
            (hashtag, max_posts, max_comments, user_id)
        )
        conn.commit()
        queue_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        bot_logger.info(f"✅ هشتگ '{hashtag}' با ID {queue_id} در صف قرار گرفت")
        
        return {
            "status": "success",
            "message": f"هشتگ '{hashtag}' در صف قرار گرفت و به زودی توسط Worker پردازش می‌شود",
            "queue_id": queue_id,
            "data": {
                "hashtag": hashtag,
                "max_posts": max_posts,
                "max_comments": max_comments
            }
        }
        
    except Exception as e:
        bot_logger.error(f"❌ خطا در افزودن هشتگ به صف: {e}")
        return {"status": "error", "message": str(e)}, 500

        return []
    # حذف finally - کروم باید باز بماند


def get_keyword(request):
    """
    این endpoint فقط کلمه کلیدی را در صف ذخیره می‌کند
    Worker خودش به صورت خودکار پردازش می‌کند
    """
    try:
        data = request.get_json()
        keyword = data.get("keyword")
        max_posts = data.get("max_posts", 5)
        max_comments = data.get("max_comments", 5)
        user_id = data.get("user_id")  # اختیاری - برای ارسال socket events
        
        if not keyword:
            return {"status": "error", "message": "کلمه کلیدی الزامی است"}, 400
        
        # تمیز کردن کلمه کلیدی
        keyword = keyword.strip()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # ذخیره مستقیم در صف
        cursor.execute(
            "INSERT INTO keywords_queue (keyword, max_posts, max_comments, user_id, status) VALUES (%s, %s, %s, %s, 'pending')",
            (keyword, max_posts, max_comments, user_id)
        )
        conn.commit()
        queue_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        bot_logger.info(f"✅ کلمه کلیدی '{keyword}' با ID {queue_id} در صف قرار گرفت")
        
        return {
            "status": "success",
            "message": f"کلمه کلیدی '{keyword}' در صف قرار گرفت و به زودی توسط Worker پردازش می‌شود",
            "queue_id": queue_id,
            "data": {
                "keyword": keyword,
                "max_posts": max_posts,
                "max_comments": max_comments
            }
        }
        
    except Exception as e:
        bot_logger.error(f"❌ خطا در افزودن کلمه کلیدی به صف: {e}")
        return {"status": "error", "message": str(e)}, 500


def get_page(request):
    data = request.get_json()
    page = data.get("page")
    
    # Read LinkedIn credentials from environment variables
    random_username = os.getenv("LINKEDIN_USERNAME", "pr1")
    random_password = os.getenv("LINKEDIN_PASSWORD", "")
    
    # استفاده از bot سراسری
    bot = get_global_bot(username=random_username, password=random_password, user_id=5, is_first=1)
    
    bot_logger.info("شروع به کار")
    url = f"https://www.linkedin.com/company/{page}/"
    bot_logger.info(f"url is {url}")
    bot.driver.get(url)

    time.sleep(10)

    # Initialize variables with default values
    page_title = ""
    page_description = ""
    page_overview = ""
    last_post_content = ""
    company_info = {"industry": "", "location": "", "followers": "", "employees": ""}
    company_link = ""
    company_phone = ""
    value = ""

    try:
        bot_logger.info(f"پیج تایتل")
        # Using a more stable XPath
        page_title = bot.driver.find_element(By.XPATH, '//h1[contains(@class, "org-top-card-summary__title")]').text
        bot_logger.info(f"پیج دسکریپشن")
        page_description = bot.driver.find_element(By.XPATH, '//p[@class="org-top-card-summary__tagline"]').text
        bot_logger.info(f"پیج فرست المنت")
        first_element = bot.driver.find_elements(By.XPATH, './/span[contains(@dir, "ltr")]')[1]
        last_post_content = first_element.text

        company_info_items = bot.driver.find_elements(By.XPATH, '//div[@class="org-top-card-summary-info-list__info-item"]')
        bot_logger.info(f"کمپانی اینفو")
        if len(company_info_items) > 0:
            company_info["industry"] = company_info_items[0].text
        if len(company_info_items) > 1:
            company_info["location"] = company_info_items[1].text
        if len(company_info_items) > 2:
            company_info["followers"] = company_info_items[2].text
    
        # Extract employees count with better error handling
        try:
            employees_element = bot.driver.find_element(By.XPATH, '//h3[contains(text(), "Company size")]/parent::dt/following-sibling::dd[1]')
            company_info["employees"] = employees_element.text.strip()
            bot_logger.info(f"Employees found: {company_info['employees']}")
        except Exception as e:
            bot_logger.warning(f"Employees element not found: {e}")
            company_info["employees"] = ""
        
        # Navigate to about page
        bot_logger.info(f"رفتن به صفحه about")
        about_url = f"https://www.linkedin.com/company/{page}/about"
        bot.driver.get(about_url)
        bot_logger.info(f"URL: {about_url}")
        time.sleep(10)
        
        # Check if we're redirected to login page
        current_url = bot.driver.current_url
        bot_logger.info(f"Current URL after navigation: {current_url}")
        
        if "login" in current_url.lower() or "signin" in current_url.lower():
            bot_logger.warning(f"Redirected to login page. Current URL: {current_url}")
            
            # Only try to login if credentials are provided
            if random_password:
                bot_logger.info(f"تلاش برای ورود مجدد")
                bot.login(username=random_username, password=random_password)
                time.sleep(5)
                # Try to navigate to about page again
                bot.driver.get(about_url)
                bot_logger.info(f"تلاش مجدد برای رفتن به صفحه About")
                time.sleep(10)
            else:
                bot_logger.warning("⚠️ No credentials - continuing with public data only")
        
        # Extract information from about page
        try:
            bot_logger.info(f"استخراج وب سایت")
            website_element = bot.driver.find_element(By.XPATH, '//dt[contains(., "Website")]/following-sibling::dd//a[@href]')
            company_link = website_element.get_attribute('href')
            bot_logger.info(f"Website found: {company_link}")
        except Exception as e:
            bot_logger.warning(f"Website not found: {e}")
        
        try:
            bot_logger.info(f"استخراج شماره تلفن")
            phone_element = bot.driver.find_element(By.XPATH, '//dt[contains(., "Phone")]/following-sibling::dd//a[@href]')
            company_phone = phone_element.get_attribute('href').replace('tel:', '')
            bot_logger.info(f"Phone found: {company_phone}")
        except Exception as e:
            bot_logger.warning(f"Phone not found: {e}")
        
        try:
            bot_logger.info(f"استخراج سال تاسیس")
            founded_element = bot.driver.find_element(By.XPATH, '//dt[contains(., "Founded")]/following-sibling::dd')
            value = founded_element.text.strip()
            bot_logger.info(f"Founded year found: {value}")
        except Exception as e:
            bot_logger.warning(f"Founded year not found: {e}")
            # Fallback for old method
            try:
                value_elements = bot.driver.find_elements(By.XPATH, '//dd[@class="mb4 t-black--light text-body-medium"]')
                if value_elements:
                    value = value_elements[-1].text
            except Exception as e2:
                bot_logger.warning(f"Value extraction failed: {e2}")
        try:
            bot_logger.info(f"پیج اور ویو")
            page_overview = bot.driver.find_element(By.XPATH, '//h2[contains(., "Overview")]/following-sibling::p').text
        except Exception as e:
            bot_logger.warning(f"Page overview not found: {e}")

    except Exception as e:
        bot_logger.error(f"Error while scraping page data: {e}")

    # حذف bot.cleanup() - کروم باید باز بماند
    
    if page_title: # Only save if we got the essential data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("insert into linkdeen_pages (page_title,page_description,page_overview,last_post_content" \
        ",company_industry,company_location,company_followers,company_employees,company_link,company_phone,company_value) values"
        " (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", 
                          (page_title, page_description,page_overview,last_post_content,company_info.get("industry"),
                           company_info.get("location"),company_info.get("followers"),company_info.get("employees"),company_link,company_phone,value))
        conn.commit()
        conn.close()
        
    return {
        'page_title': page_title,
        'page_description': page_description,
        'page_overview': page_overview,
        'last_post_content': last_post_content,
        'company_info': company_info,
        'company_link': company_link,
        'company_phone': company_phone,
        'members_count': "",
        'company_value': value
    }



def get_data_page(request):
    # اتصال به دیتابیس
    conn = get_db_connection()
    cursor = conn.cursor()

    # اجرای کوئری
    cursor.execute("SELECT * FROM linkdeen_pages")
    pages = cursor.fetchall()

    # نتایج را به مدل API تبدیل کنید
    data = []
    for page in pages:
        page_data = {
            'page_title': page['page_title'],  # فرض شده که صفحه عنوان در اولین ستون است
            'page_description': page['page_description'],  # فرض شده که توضیحات در دومین ستون است
            'page_overview': page['page_overview'],  # فرض شده که بررسی کلی در ستون سوم است
            'last_post_content': page['last_post_content'],  # فرض شده که محتوای آخرین پست در ستون چهارم است
            'company_info': {
                'industry': page['company_industry'],  # صنعت شرکت
                'location': page['company_location'],  # موقعیت شرکت
                'followers': page['company_followers'],  # تعداد فالوورها
                'employees': page['company_employees']   # تعداد اعضای شرکت
            },
            'company_link': page['company_link'],  # لینک شرکت
            'company_phone': page['company_phone'],  # شماره تلفن شرکت
            'members_count': "",  # تعداد اعضای شرکت
            'company_value': page["company_value"]  # مقدار خاصی از اطلاعات شرکت
        }
        data.append(page_data)

    return {"status":"success","message":"success",'data': data}


def get_data_post(request):
    conn = get_db_connection()
    cursor = conn.cursor()

    # اجرای کوئری با FULL JOIN برای اتصال به پست‌ها و کامنت‌ها
    cursor.execute("""
    SELECT 
        p.id as post_id, 
        p.post_link, 
        p.caption, 
        p.reactions, 
        p.comments as post_comments, 
        p.username, 
        c.commenter, 
        c.comment_text
    FROM linkdeen_posts p
    LEFT JOIN linkdeen_comments c ON p.id = c.linkdeen_post_id
    """)
    
    posts = cursor.fetchall()
    
    posts_data = []
    current_post = None
    comments_data = []
    
    # پردازش پست‌ها و کامنت‌ها
    for post in posts:
        if current_post != post['post_id']:
            if current_post is not None:  # ذخیره پست قبلی
                posts_data.append({
                    'link': current_post_data['post_link'],
                    'caption': current_post_data['caption'],
                    'reactions': current_post_data['reactions'],
                    'comments': current_post_data['post_comments'],
                    'username': current_post_data['username'],
                    'comments_detail': comments_data if comments_data else []
                })
            
            # شروع پست جدید
            current_post = post['post_id']
            current_post_data = {
                'post_link': post['post_link'],
                'caption': post['caption'],
                'reactions': post['reactions'],
                'post_comments': post['post_comments'],
                'username': post['username']
            }
            comments_data = []  # شروع مجدد برای کامنت‌ها
            if post['commenter']:  # اگر کامنت وجود دارد
                comments_data.append({
                    'commenter': post['commenter'],
                    'comment_text': post['comment_text']
                })
            else:
                comments_data.append({
                    'commenter': 'No commenter',
                    'comment_text': 'No comment'
                })

        else:
            # اضافه کردن کامنت‌ها به پست موجود
            if post['commenter']:  # اگر کامنت وجود دارد
                comments_data.append({
                    'commenter': post['commenter'],
                    'comment_text': post['comment_text']
                })
            else:
                comments_data.append({
                    'commenter': 'No commenter',
                    'comment_text': 'No comment'
                })
    
    # اضافه کردن آخرین پست
    if current_post is not None:
        posts_data.append({
            'link': current_post_data['post_link'],
            'caption': current_post_data['caption'],
            'reactions': current_post_data['reactions'],
            'comments': current_post_data['post_comments'],
            'username': current_post_data['username'],
            'comments_detail': comments_data
        })
    
    return {
        'status': 'success',
        'message': 'Data retrieved successfully',
        'data': posts_data
    }



def get_page2(page):
    # Read LinkedIn credentials from environment variables
    random_username = os.getenv("LINKEDIN_USERNAME", "pr1")
    random_password = os.getenv("LINKEDIN_PASSWORD", "")
    
    # استفاده از bot سراسری
    bot = get_global_bot(username=random_username, password=random_password, user_id=5, is_first=1)
    
    bot_logger.info("شروع به کار")
    url = f"https://www.linkedin.com/company/{page}/"
    bot_logger.info(f"url is {url}")
    bot.driver.get(url)

    time.sleep(10)

    # Initialize variables with default values
    page_title = ""
    page_description = ""
    page_overview = ""
    last_post_content = ""
    company_info = {"industry": "", "location": "", "followers": "", "employees": ""}
    company_link = ""
    company_phone = ""
    value = ""

    try:
        bot_logger.info(f"پیج تایتل")
        # Using a more stable XPath
        page_title = bot.driver.find_element(By.XPATH, '//h1[contains(@class, "org-top-card-summary__title")]').text
        bot_logger.info(f"پیج دسکریپشن")
        page_description = bot.driver.find_element(By.XPATH, '//p[@class="org-top-card-summary__tagline"]').text
        bot_logger.info(f"پیج فرست المنت")
        first_element = bot.driver.find_elements(By.XPATH, './/span[contains(@dir, "ltr")]')[1]
        last_post_content = first_element.text

        company_info_items = bot.driver.find_elements(By.XPATH, '//div[@class="org-top-card-summary-info-list__info-item"]')
        bot_logger.info(f"کمپانی اینفو")
        if len(company_info_items) > 0:
            company_info["industry"] = company_info_items[0].text
        if len(company_info_items) > 1:
            company_info["location"] = company_info_items[1].text
        if len(company_info_items) > 2:
            company_info["followers"] = company_info_items[2].text
    
        # Extract employees count with better error handling
        try:
            employees_element = bot.driver.find_element(By.XPATH, '//h3[contains(text(), "Company size")]/parent::dt/following-sibling::dd[1]')
            company_info["employees"] = employees_element.text.strip()
            bot_logger.info(f"Employees found: {company_info['employees']}")
        except Exception as e:
            bot_logger.warning(f"Employees element not found: {e}")
            company_info["employees"] = ""
        
        # Navigate to about page
        bot_logger.info(f"رفتن به صفحه about")
        about_url = f"https://www.linkedin.com/company/{page}/about"
        bot.driver.get(about_url)
        bot_logger.info(f"URL: {about_url}")
        time.sleep(10)
        
        # Check if we're redirected to login page
        current_url = bot.driver.current_url
        bot_logger.info(f"Current URL after navigation: {current_url}")
        
        if "login" in current_url.lower() or "signin" in current_url.lower():
            bot_logger.warning(f"Redirected to login page. Current URL: {current_url}")
            
            # Only try to login if credentials are provided
            if random_password:
                bot_logger.info(f"تلاش برای ورود مجدد")
                bot.login(username=random_username, password=random_password)
                time.sleep(5)
                # Try to navigate to about page again
                bot.driver.get(about_url)
                bot_logger.info(f"تلاش مجدد برای رفتن به صفحه About")
                time.sleep(10)
            else:
                bot_logger.warning("⚠️ No credentials - continuing with public data only")
        
        # Extract information from about page
        try:
            bot_logger.info(f"استخراج وب سایت")
            website_element = bot.driver.find_element(By.XPATH, '//dt[contains(., "Website")]/following-sibling::dd//a[@href]')
            company_link = website_element.get_attribute('href')
            bot_logger.info(f"Website found: {company_link}")
        except Exception as e:
            bot_logger.warning(f"Website not found: {e}")
        
        try:
            bot_logger.info(f"استخراج شماره تلفن")
            phone_element = bot.driver.find_element(By.XPATH, '//dt[contains(., "Phone")]/following-sibling::dd//a[@href]')
            company_phone = phone_element.get_attribute('href').replace('tel:', '')
            bot_logger.info(f"Phone found: {company_phone}")
        except Exception as e:
            bot_logger.warning(f"Phone not found: {e}")
        
        try:
            bot_logger.info(f"استخراج سال تاسیس")
            founded_element = bot.driver.find_element(By.XPATH, '//dt[contains(., "Founded")]/following-sibling::dd')
            value = founded_element.text.strip()
            bot_logger.info(f"Founded year found: {value}")
        except Exception as e:
            bot_logger.warning(f"Founded year not found: {e}")
            # Fallback for old method
            try:
                value_elements = bot.driver.find_elements(By.XPATH, '//dd[@class="mb4 t-black--light text-body-medium"]')
                if value_elements:
                    value = value_elements[-1].text
            except Exception as e2:
                bot_logger.warning(f"Value extraction failed: {e2}")
        try:
            bot_logger.info(f"پیج اور ویو")
            page_overview = bot.driver.find_element(By.XPATH, '//h2[contains(., "Overview")]/following-sibling::p').text
        except Exception as e:
            bot_logger.warning(f"Page overview not found: {e}")
            
    except Exception as e:
        bot_logger.error(f"Error while scraping page data: {e}")

    # حذف bot.cleanup() - کروم باید باز بماند
    
    if page_title: # Only save if we got the essential data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("insert into linkdeen_pages (page_title,page_description,page_overview,last_post_content" \
        ",company_industry,company_location,company_followers,company_employees,company_link,company_phone,company_value) values"
        " (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", 
                          (page_title, page_description,page_overview,last_post_content,company_info.get("industry"),
                           company_info.get("location"),company_info.get("followers"),company_info.get("employees"),company_link,company_phone,value))
        conn.commit()
        conn.close()
        
    return {
        'page_title': page_title,
        'page_description': page_description,
        'page_overview': page_overview,
        'last_post_content': last_post_content,
        'company_info': company_info,
        'company_link': company_link,
        'company_phone': company_phone,
        'members_count': "",
        'company_value': value
    }

def get_post2(hashtag, max_posts=5, max_comments=5, hashtag_id=None, user_id=None):
    """
    جمع‌آوری واقعی پست‌های LinkedIn برای یک هشتگ
    این تابع فقط توسط Worker صدا زده می‌شود
    
    Args:
        hashtag: هشتگ مورد نظر
        max_posts: حداکثر تعداد پست
        max_comments: حداکثر تعداد کامنت در هر پست
        hashtag_id: ID هشتگ در hashtags_queue
        user_id: ID کاربر برای ارسال پیشرفت (اختیاری)
    """
    bot_logger.info(f"🚀 get_post2() CALLED with hashtag={hashtag}, max_posts={max_posts}, max_comments={max_comments}, hashtag_id={hashtag_id}")
    try:
        # Read LinkedIn credentials from environment variables
        random_username = os.getenv("LINKEDIN_USERNAME", "pr1")
        random_password = os.getenv("LINKEDIN_PASSWORD", "")
        
        """جمع آوری پست‌ها از لینکدین"""
        bot_logger.info(f"شروع جمع آوری پست‌ها از لینکدین برای {random_username} و هشتگ {hashtag} (Queue ID: {hashtag_id})")
        
        # تنظیم Socket Handler برای ارسال پیشرفت
        socket_handler = SocketHandlers(socketio)
        
        # استفاده از bot سراسری
        bot_logger.info(f"🔄 About to call get_global_bot() with username={random_username}")
        import sys
        sys.stdout.flush()
        sys.stderr.flush()
        
        bot = get_global_bot(username=random_username, password=random_password, user_id=5, is_first=1)
        bot_logger.info("✅ get_global_bot() returned successfully")
        
        # Check if we are logged in before searching
        current_url = bot.driver.current_url
        bot_logger.info(f"📍 Current URL before search: {current_url}")
        
        is_logged_in = bot.verify_login_status()
        bot_logger.info(f"🔐 Login status verified: {is_logged_in}")
        
        if not is_logged_in:
            bot_logger.warning("⚠️ Not logged in - attempting login...")
            if random_password:
                try:
                    bot.login(random_username, random_password, user_id or 5)
                    time.sleep(5)
                    is_logged_in = bot.verify_login_status()
                    bot_logger.info(f"🔐 Login status after attempt: {is_logged_in}")
                except Exception as login_err:
                    bot_logger.error(f"❌ Login failed: {login_err}")
            else:
                bot_logger.warning("⚠️ No password provided - scraping as guest")
        
        # استفاده از جستجوی LinkedIn با URL encoding و content filter
        encoded_hashtag = quote_plus(hashtag)
        url = f"https://www.linkedin.com/search/results/content/?keywords={encoded_hashtag}&sortBy=date_posted"
        
        bot_logger.info(f"🔍 Searching LinkedIn with URL: {url}")
        bot.driver.get(url)
        time.sleep(10)
        
        # Log the actual URL after navigation (detect redirects)
        actual_url = bot.driver.current_url
        bot_logger.info(f"📍 Actual URL after navigation: {actual_url}")
        
        if 'login' in actual_url.lower() or 'signin' in actual_url.lower():
            bot_logger.error("❌ Redirected to login page - not authenticated!")
        
        bot_logger.info("✅ Using date_posted sort to reduce personalization")

        posts_data = []  # لیستی برای ذخیره اطلاعات هر پست
        last_posts_count = 0

        while len(posts_data) < max_posts:
            bot_logger.info("شروع ها یافت شدند ")
            posts = bot.driver.find_elements(By.XPATH,'//div[contains(@class, "fie-impression-container")]')
            bot_logger.info(f"پست ها یافت شدند: {len(posts)} posts found on page")
            
            # If no posts found, try alternate selectors
            if len(posts) == 0:
                bot_logger.warning("⚠️ No posts with fie-impression-container, trying alternate selectors...")
                # Try other common LinkedIn post container classes
                alternate_selectors = [
                    '//div[contains(@class, "feed-shared-update-v2")]',
                    '//div[contains(@class, "occludable-update")]',
                    '//article[contains(@class, "relative")]',
                    '//div[@data-urn]',
                ]
                for sel in alternate_selectors:
                    posts = bot.driver.find_elements(By.XPATH, sel)
                    if len(posts) > 0:
                        bot_logger.info(f"✅ Found {len(posts)} posts with selector: {sel}")
                        break
                
                if len(posts) == 0:
                    # Log page source snippet for debugging
                    try:
                        page_title = bot.driver.title
                        bot_logger.error(f"❌ No posts found. Page title: {page_title}")
                        # Check if there's a "no results" message
                        no_results = bot.driver.find_elements(By.XPATH, '//*[contains(text(), "No results") or contains(text(), "no results")]')
                        if no_results:
                            bot_logger.info("ℹ️ LinkedIn says 'No results' for this search")
                    except Exception as e:
                        bot_logger.error(f"Debug error: {e}")

            if len(posts) == last_posts_count:
                bot_logger.info("پست جدیدی یافت نشد. پایان عملیات.")
                break
            
            new_posts = posts[last_posts_count:]
            last_posts_count = len(posts)

            for post in new_posts:
                if len(posts_data) >= max_posts:
                    break
                try:
                    post_info = {}  
                    
                    # Comprehensive post link detection with multiple strategies
                    post_link = "No link found"
                    all_links = []
                    
                    try:
                        all_links = post.find_elements(By.TAG_NAME, 'a')
                    except:
                        pass
                    
                    # Strategy 1: Look for data-urn attribute on the post container itself or parents
                    try:
                        urn = None
                        # Check the post element itself
                        urn = post.get_attribute('data-urn') or post.get_attribute('data-id') or post.get_attribute('data-entity-urn')
                        
                        # If not found, check parent elements
                        if not urn:
                            try:
                                parent = post.find_element(By.XPATH, './ancestor::div[@data-urn]')
                                urn = parent.get_attribute('data-urn')
                            except:
                                pass
                        
                        # Also check for data-activity-urn
                        if not urn:
                            try:
                                urn = post.get_attribute('data-activity-urn')
                            except:
                                pass
                        
                        if urn:
                            # Extract activity ID from URN
                            if 'activity' in urn:
                                activity_id = urn.split(':')[-1]
                                post_link = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/"
                                bot_logger.info(f"✅ Post link from data-urn: {post_link}")
                            elif 'ugcPost' in urn:
                                ugc_id = urn.split(':')[-1]
                                post_link = f"https://www.linkedin.com/feed/update/urn:li:ugcPost:{ugc_id}/"
                                bot_logger.info(f"✅ Post link from ugcPost URN: {post_link}")
                            elif 'share' in urn:
                                share_id = urn.split(':')[-1]
                                post_link = f"https://www.linkedin.com/feed/update/urn:li:share:{share_id}/"
                                bot_logger.info(f"✅ Post link from share URN: {post_link}")
                    except Exception as e:
                        bot_logger.debug(f"URN extraction failed: {e}")

                    # Strategy 2: Find timestamp anchor (most reliable for feed posts)
                    if post_link == "No link found":
                        try:
                            time_el = post.find_element(By.TAG_NAME, 'time')
                            time_anchor = time_el.find_element(By.XPATH, './ancestor::a[1]')
                            href = time_anchor.get_attribute('href')
                            if href and 'linkedin.com' in href:
                                post_link = href.split('?')[0]
                                bot_logger.info(f"✅ Post link from time anchor: {post_link}")
                        except Exception:
                            pass

                    # Strategy 3: Look for activity/update links in anchors
                    if post_link == "No link found":
                        bot_logger.info(f"🔍 Scanning {len(all_links)} anchors for post link...")
                        for link in all_links:
                            try:
                                href = link.get_attribute('href') or ''
                                if 'linkedin.com' in href:
                                    # Priority patterns for post URLs
                                    if '/feed/update/' in href:
                                        post_link = href.split('?')[0]
                                        bot_logger.info(f"✅ Post link (feed/update): {post_link}")
                                        break
                                    elif '/posts/' in href:
                                        post_link = href.split('?')[0]
                                        bot_logger.info(f"✅ Post link (posts): {post_link}")
                                        break
                                    elif '/pulse/' in href:
                                        post_link = href.split('?')[0]
                                        bot_logger.info(f"✅ Post link (pulse): {post_link}")
                                        break
                                    elif 'activity-' in href:
                                        post_link = href.split('?')[0]
                                        bot_logger.info(f"✅ Post link (activity): {post_link}")
                                        break
                                    elif '/ugcPost' in href:
                                        post_link = href.split('?')[0]
                                        bot_logger.info(f"✅ Post link (ugcPost): {post_link}")
                                        break
                            except:
                                continue

                    # Strategy 4: Extract from outer HTML using regex
                    if post_link == "No link found":
                        try:
                            outer_html = post.get_attribute('outerHTML')
                            # Look for activity URN in the HTML
                            import re
                            
                            # Pattern for activity URN
                            activity_match = re.search(r'urn:li:activity:(\d+)', outer_html)
                            if activity_match:
                                activity_id = activity_match.group(1)
                                post_link = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/"
                                bot_logger.info(f"✅ Post link from HTML regex (activity): {post_link}")
                            
                            # Pattern for ugcPost URN
                            if post_link == "No link found":
                                ugc_match = re.search(r'urn:li:ugcPost:(\d+)', outer_html)
                                if ugc_match:
                                    ugc_id = ugc_match.group(1)
                                    post_link = f"https://www.linkedin.com/feed/update/urn:li:ugcPost:{ugc_id}/"
                                    bot_logger.info(f"✅ Post link from HTML regex (ugcPost): {post_link}")
                            
                            # Pattern for share URN
                            if post_link == "No link found":
                                share_match = re.search(r'urn:li:share:(\d+)', outer_html)
                                if share_match:
                                    share_id = share_match.group(1)
                                    post_link = f"https://www.linkedin.com/feed/update/urn:li:share:{share_id}/"
                                    bot_logger.info(f"✅ Post link from HTML regex (share): {post_link}")
                            
                            # Pattern for fsd_update URN (newer LinkedIn format)
                            if post_link == "No link found":
                                fsd_match = re.search(r'urn:li:fsd_update:\(urn:li:activity:(\d+)', outer_html)
                                if fsd_match:
                                    activity_id = fsd_match.group(1)
                                    post_link = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/"
                                    bot_logger.info(f"✅ Post link from HTML regex (fsd_update): {post_link}")
                                    
                        except Exception as e:
                            bot_logger.debug(f"HTML regex extraction failed: {e}")

                    # Strategy 5: Look for any href containing feed/update pattern in outer HTML
                    if post_link == "No link found":
                        try:
                            href_match = re.search(r'href="(https://www\.linkedin\.com/feed/update/[^"]+)"', outer_html)
                            if href_match:
                                post_link = href_match.group(1).split('?')[0]
                                bot_logger.info(f"✅ Post link from href regex: {post_link}")
                        except Exception:
                            pass

                    # Strategy 6: Click on "more" menu to find copy link option (last resort, slower)
                    if post_link == "No link found":
                        try:
                            # Find the 3-dot menu button
                            menu_button = post.find_element(By.XPATH, './/button[contains(@aria-label, "Open control menu") or contains(@aria-label, "More actions")]')
                            bot.driver.execute_script("arguments[0].click();", menu_button)
                            time.sleep(1)
                            
                            # Look for "Copy link to post" option
                            copy_link = bot.driver.find_element(By.XPATH, '//span[contains(text(), "Copy link")]')
                            copy_link.click()
                            time.sleep(0.5)
                            
                            # Get from clipboard (may not work in headless)
                            try:
                                import pyperclip
                                post_link = pyperclip.paste()
                                if post_link and 'linkedin.com' in post_link:
                                    post_link = post_link.split('?')[0]
                                    bot_logger.info(f"✅ Post link from clipboard: {post_link}")
                            except:
                                pass
                            
                            # Close the menu
                            bot.driver.find_element(By.TAG_NAME, 'body').click()
                            time.sleep(0.3)
                        except Exception:
                            pass

                    if post_link == "No link found":
                        bot_logger.warning('⚠️ No post link found after all strategies')
                    
                    post_info['link'] = post_link
                    
                    # ارسال پیشرفت فقط اگر user_id وجود داشته باشد
                    if user_id:
                        socket_handler.emit_progress(
                            event='post_link',
                            data={
                                "message": "پست زیر جمع آوری شده است",
                                "post": post_link
                            },
                            user_id=user_id
                        )
                    
                    
                    try:
                        see_more_button = post.find_element(By.XPATH,'.//button[contains(@aria-label, "see more")]')
                        bot.driver.execute_script("arguments[0].click();", see_more_button)
                        time.sleep(2)  
                    except NoSuchElementException:
                        pass  

                    bot_logger.info("مور ها یافت شدند ")
                    
                    # استخراج متن کپشن پس از نمایش کامل
                    try:
                        caption = post.find_element(By.XPATH,'.//div[contains(@class, "update-components-text")]').text
                        post_info["caption"] = caption
                        if user_id:
                            socket_handler.emit_progress(
                                event='caption',
                                data={
                                    "message": "کپشن جمع آوری شد",
                                    "caption": caption
                                },
                                user_id=user_id
                            )
                    except NoSuchElementException:
                        post_info["caption"] = "No caption found"
                        caption = "No caption found"

                    bot_logger.info("کپشن ها یافت شدند ")
                    
                    
                    try:
                        reactions = post.find_element(By.XPATH,'.//span[@aria-hidden="true" and contains(@class, "social-details-social-counts__reactions-count")]').text
                        post_info["reactions"] = reactions
                        if user_id:
                            socket_handler.emit_progress(
                                event='reactions',
                                data={
                                    "message": "ری‌اکشن‌ها شمرده شد",
                                    "reactions": reactions
                                },
                                user_id=user_id
                            )
                    except NoSuchElementException:
                        post_info["reactions"] = "0"
                        reactions = "0"

                    bot_logger.info("ری اکشن ها یافت شدند ")
                    
                    # Extract comment count with multiple strategies
                    comments_count = "0"
                    try:
                        # Strategy 1: Button with aria-label containing "comment"
                        try:
                            comments_button = post.find_element(By.XPATH, './/button[contains(@aria-label, "comment")]')
                            comments_text = comments_button.text
                            found_count = "".join(re.findall(r'\d+', comments_text))
                            if found_count:
                                comments_count = found_count
                                bot_logger.info(f"📝 Comment count from button aria-label: {comments_count}")
                        except:
                            pass
                        
                        # Strategy 2: Look for comment count in social counts area
                        if comments_count == "0":
                            try:
                                comment_count_el = post.find_element(By.XPATH, './/button[contains(@class, "social-details-social-counts__comments")]')
                                comments_text = comment_count_el.text
                                found_count = "".join(re.findall(r'\d+', comments_text))
                                if found_count:
                                    comments_count = found_count
                                    bot_logger.info(f"📝 Comment count from social-counts: {comments_count}")
                            except:
                                pass
                        
                        # Strategy 3: Look for span with comment count
                        if comments_count == "0":
                            try:
                                comment_spans = post.find_elements(By.XPATH, './/span[contains(text(), "comment") or contains(text(), "Comment")]')
                                for span in comment_spans:
                                    text = span.text
                                    found_count = "".join(re.findall(r'\d+', text))
                                    if found_count:
                                        comments_count = found_count
                                        bot_logger.info(f"📝 Comment count from span: {comments_count}")
                                        break
                            except:
                                pass
                        
                        # Strategy 4: Extract from outer HTML using regex
                        if comments_count == "0":
                            try:
                                outer_html = post.get_attribute('outerHTML')
                                # Look for patterns like "5 comments" or "5 Comments"
                                count_match = re.search(r'(\d+)\s*[Cc]omment', outer_html)
                                if count_match:
                                    comments_count = count_match.group(1)
                                    bot_logger.info(f"📝 Comment count from HTML regex: {comments_count}")
                            except:
                                pass
                        
                        post_info["comments"] = comments_count
                        if user_id:
                            socket_handler.emit_progress(
                                event='comment_count',
                                data={
                                    "message": "تعداد کامنت‌ها",
                                    "comment_count": comments_count
                                },
                                user_id=user_id
                            )
                    except Exception as e:
                        bot_logger.warning(f"⚠️ Error extracting comment count: {e}")
                        post_info["comments"] = "0"
                        comments_count = "0"
                    
                    bot_logger.info(f"📊 Final comment count: {comments_count}")
                    
                    # استخراج نام کاربری
                    try:
                        username_element = post.find_element(By.XPATH, './/span[@aria-hidden="true"]')
                        username = username_element.text.strip()
                        post_info["username"] = username
                    except NoSuchElementException:
                        post_info["username"] = "No username"
                        username = "No username"
                    bot_logger.info("یوزرنیم ها یافت شدند ")
                    
                    
                    
                    posts_data.append(post_info)
                    bot_logger.info("کامنت دیتا ها یافت شدند ")

                    # ✅ ذخیره با hashtag_id
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO linkdeen_posts (post_link,caption,reactions,comments,username,hashtag_id,analyzed) VALUES"
                    " (%s,%s,%s,%s,%s,%s,%s)", 
                                    (post_link,caption,reactions,comments_count,username,hashtag_id,0))
                    conn.commit()

                    last_inserted_id = cursor.lastrowid
                    post_info["post_id"] = last_inserted_id  # ✅ ذخیره post_id برای استفاده بعدی
                    cursor.close()
                    conn.close()
                    bot_logger.info(f"✅ پست با ID {last_inserted_id} ذخیره شد")
                    
                except Exception as e:
                    bot_logger.error(f"خطا در استخراج اطلاعات پست: {e}")
                    
            # اسکرول صفحه
            bot.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # صبر برای بارگذاری پست‌های بیشتر

            try:
                load_more_button = bot.driver.find_element(By.XPATH, "//button[span[text()='See more results']]")
                load_more_button.click()
                time.sleep(5)
            except NoSuchElementException:
                pass

        # ✅ جمع‌آوری کامنت‌ها برای هر پست
        if max_comments > 0:
            bot_logger.info(f"🔄 شروع جمع‌آوری کامنت‌ها (حداکثر {max_comments} کامنت برای هر پست)...")
        else:
            bot_logger.info("⏭️ جمع‌آوری کامنت غیرفعال است (max_comments=0)")

        conn = get_db_connection()
        cursor = conn.cursor()
        for data in posts_data:
            comments_data = []
            post_id = data.get('post_id')

            # Always try to collect comments if we have a valid link (don't rely on comment count detection)
            if data.get('link') and data.get('link') != "No link found" and post_id and max_comments > 0:
                try:
                    bot_logger.info(f"🔍 Collecting comments for post {post_id} (reported count: {data.get('comments', '0')})...")
                    try:
                        bot.driver.get(data['link'])
                        time.sleep(4)
                        # ensure comments area loads
                        bot.driver.execute_script('window.scrollTo(0, document.body.scrollHeight/2);')
                        time.sleep(2)
                    except Exception as e_nav:
                        bot_logger.warning(f"Could not navigate to post link: {e_nav}")

                    # try several selectors to find comments
                    comment_selectors = [
                        './/article[contains(@class, "comments-comment-entity")]',
                        './/div[contains(@class, "comments-comments-list__comment-item")]',
                        './/div[contains(@class, "feed-shared-comment")]',
                        './/li[contains(@class, "comments-comment-item")]'
                    ]

                    comments = []
                    for sel in comment_selectors:
                        try:
                            comments = bot.driver.find_elements(By.XPATH, sel)
                            if comments and len(comments) > 0:
                                bot_logger.info(f"📝 Comments found with selector {sel}: {len(comments)}")
                                break
                        except Exception:
                            continue

                    for comment in comments[:max_comments]:
                        try:
                            commenter = None
                            comment_text = None

                            # try a list of potential commenter selectors
                            commenter_selectors = [
                                './/a[contains(@class,"feed-shared-actor__name")]',
                                './/span[contains(@class,"comments-post-meta__name")]',
                                './/span[contains(@class,"comments-comment-meta__name")]',
                                './/span[contains(@class,"comments-comment-meta__description-title")]',
                                './/a[@data-control-name]'
                            ]
                            for cs in commenter_selectors:
                                try:
                                    el = comment.find_element(By.XPATH, cs)
                                    txt = el.text.strip()
                                    if txt:
                                        commenter = txt
                                        break
                                except Exception:
                                    continue

                            # try to find comment text using a few strategies
                            try:
                                # common: span with dir attribute
                                comment_text = comment.find_element(By.XPATH, './/div[contains(@class, "comments-comment-item__main-content")]/span').text
                            except Exception:
                                try:
                                    comment_text = comment.find_element(By.XPATH, './/span[@dir="ltr" or @dir="rtl" and normalize-space(.)!=""]').text
                                except Exception:
                                    try:
                                        comment_text = comment.find_element(By.XPATH, './/p').text
                                    except Exception:
                                        comment_text = ''

                            if not commenter:
                                commenter = 'Unknown'
                            if not comment_text:
                                comment_text = ''

                            comment_data = {'commenter': commenter, 'comment_text': comment_text}
                            comments_data.append(comment_data)

                            try:
                                cursor.execute("INSERT INTO linkdeen_comments (linkdeen_post_id,commenter,comment_text) VALUES (%s,%s,%s)",
                                                (post_id, commenter, comment_text))
                                conn.commit()
                                bot_logger.info(f"✅ Saved comment from {commenter}")
                            except Exception as e_ins:
                                bot_logger.warning(f"Could not save comment: {e_ins}")

                            if user_id:
                                socket_handler.emit_progress(
                                    event='comment',
                                    data={'message': 'کامنت جمع آوری شد', 'commenter': commenter, 'comment_text': comment_text},
                                    user_id=user_id
                                )

                        except Exception as e:
                            bot_logger.warning(f"⚠️ Error extracting individual comment: {e}")
                            continue

                except Exception as e:
                    bot_logger.error(f"❌ خطا در جمع‌آوری کامنت‌های پست {post_id}: {e}")

            data['comments_detail'] = comments_data

            
        bot_logger.info(f"✅ تعداد پست‌ها جمع آوری شده: {len(posts_data)}")
        return posts_data
    except Exception as e:
        bot_logger.error(f"❌ Error in get_post2: {str(e)}")
        raise  # مهم: خطا رو بالا بفرست تا Worker بگیرتش


def get_keyword_posts(keyword, max_posts=5, max_comments=5, keyword_id=None, user_id=None):
    """
    جمع‌آوری واقعی پست‌های LinkedIn برای یک کلمه کلیدی
    این تابع فقط توسط Worker صدا زده می‌شود
    
    Args:
        keyword: کلمه کلیدی مورد نظر برای جستجو
        max_posts: حداکثر تعداد پست
        max_comments: حداکثر تعداد کامنت در هر پست
        keyword_id: ID کلمه کلیدی در keywords_queue
        user_id: ID کاربر برای ارسال پیشرفت (اختیاری)
    """
    bot_logger.info(f"🚀 get_keyword_posts() CALLED with keyword={keyword}, max_posts={max_posts}, max_comments={max_comments}, keyword_id={keyword_id}")
    try:
        # Read LinkedIn credentials from environment variables
        random_username = os.getenv("LINKEDIN_USERNAME", "pr1")
        random_password = os.getenv("LINKEDIN_PASSWORD", "")
        
        """جمع آوری پست‌ها از لینکدین"""
        bot_logger.info(f"شروع جمع آوری پست‌ها از لینکدین برای {random_username} و کلمه کلیدی {keyword} (Queue ID: {keyword_id})")
        
        # تنظیم Socket Handler برای ارسال پیشرفت
        socket_handler = SocketHandlers(socketio)
        
        # استفاده از bot سراسری
        bot = get_global_bot(username=random_username, password=random_password, user_id=5, is_first=1)
        
        # استفاده از جستجوی LinkedIn برای کلمه کلیدی - با URL encoding و content filter
        encoded_keyword = quote_plus(keyword)
        url = f"https://www.linkedin.com/search/results/content/?keywords={encoded_keyword}&sortBy=date_posted"
        
        bot_logger.info(f"🔍 Searching LinkedIn with URL: {url}")
        bot.driver.get(url)
        time.sleep(10)
        
        #TODO:
        try:
            user_account = bot.driver.find_element(By.XPATH,'//div[contains(@class, "member-profile-container")]')
            user_account.click()
            time.sleep(5)
        except NoSuchElementException:
            pass
        
        bot_logger.info("✅ Using date_posted sort to reduce personalization")

        posts_data = []  # لیستی برای ذخیره اطلاعات هر پست
        last_posts_count = 0

        while len(posts_data) < max_posts:
            bot_logger.info("شروع جستجوی پست‌ها")
            posts = bot.driver.find_elements(By.XPATH,'//div[contains(@class, "fie-impression-container")]')
            bot_logger.info(f"پست ها یافت شدند: {len(posts)} پست")
            
            # Debug: Log page source snippet to verify what LinkedIn is serving
            if len(posts) > 0 and len(posts_data) == 0:
                try:
                    page_text = bot.driver.find_element(By.TAG_NAME, "body").text[:500]
                    bot_logger.info(f"📄 Page preview: {page_text[:200]}...")
                except:
                    pass

            if len(posts) == last_posts_count:
                bot_logger.info("پست جدیدی یافت نشد. پایان عملیات.")
                break
            
            new_posts = posts[last_posts_count:]
            last_posts_count = len(posts)

            for post in new_posts:
                if len(posts_data) >= max_posts:
                    break
                try:
                    post_info = {}  
                    
                    # Improved: robust post link detection (time anchor, anchors inspection, URN construction)
                    post_link = "No link found"
                    try:
                        try:
                            time_el = post.find_element(By.TAG_NAME, 'time')
                            time_anchor = time_el.find_element(By.XPATH, './ancestor::a[1]')
                            href = time_anchor.get_attribute('href')
                            if href:
                                post_link = href.split('?')[0]
                                bot_logger.info(f"✅ Post link from time anchor: {post_link}")
                        except Exception:
                            pass

                        all_links = post.find_elements(By.TAG_NAME, 'a')
                        bot_logger.info(f"🔍 anchors in post: {len(all_links)}")
                        for link in all_links:
                            href = link.get_attribute('href') or ''
                            if 'linkedin.com' in href and any(p in href for p in ['/posts/', '/feed/update/', '/activity-', '/ugcPost', '/pulse/']):
                                post_link = href.split('?')[0]
                                bot_logger.info(f"✅ Post link found in anchors: {post_link}")
                                break

                        if post_link == "No link found":
                            urn = post.get_attribute('data-urn') or post.get_attribute('data-id') or post.get_attribute('data-entity-urn')
                            if urn and 'activity' in urn:
                                try:
                                    activity_id = urn.split(':')[-1]
                                    post_link = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/"
                                    bot_logger.info(f"✅ Constructed from URN: {post_link}")
                                except Exception:
                                    pass

                        if post_link == "No link found":
                            for link in all_links:
                                href = link.get_attribute('href') or ''
                                if 'linkedin.com' in href and ('feed' in href or 'detail' in href):
                                    post_link = href.split('?')[0]
                                    bot_logger.info(f"✅ Fallback link: {post_link}")
                                    break

                        if post_link == "No link found":
                            bot_logger.warning('⚠️ No post link found after all strategies')
                        post_info['link'] = post_link
                    except Exception as e:
                        bot_logger.error(f"❌ Error extracting post link: {e}")

                    # کلیک روی دکمه "see more" برای نمایش کامل متن کپشن
                    try:
                        see_more_button = post.find_element(By.XPATH, './/button[contains(@class, "see-more") or @aria-label="see more"]')
                        see_more_button.click()
                        time.sleep(2)  
                    except NoSuchElementException:
                        pass  

                    bot_logger.info("متن کامل نمایش داده شد")
                    
                    # استخراج متن کپشن پس از نمایش کامل
                    try:
                        caption = post.find_element(By.XPATH,'.//div[contains(@class, "update-components-text")]').text
                        post_info["caption"] = caption
                        if user_id:
                            socket_handler.emit_progress(
                                event='caption',
                                data={
                                    "message": "کپشن جمع آوری شد",
                                    "caption": caption
                                },
                                user_id=user_id
                            )
                    except NoSuchElementException:
                        post_info["caption"] = "No caption found"
                        caption = "No caption found"

                    bot_logger.info("کپشن یافت شد")
                    
                    # استخراج ری‌اکشن‌ها
                    try:
                        reactions = post.find_element(By.XPATH,'.//span[@aria-hidden="true" and contains(@class, "social-details-social-counts__reactions-count")]').text
                        post_info["reactions"] = reactions
                        if user_id:
                            socket_handler.emit_progress(
                                event='reactions',
                                data={
                                    "message": "ری‌اکشن‌ها شمرده شد",
                                    "reactions": reactions
                                },
                                user_id=user_id
                            )
                    except NoSuchElementException:
                        post_info["reactions"] = "0"
                        reactions = "0"

                    bot_logger.info("ری اکشن ها یافت شدند")
                    
                    # استخراج تعداد کامنت‌ها
                    comments_count = 0
                    try:
                        comments_button = post.find_element(By.XPATH, './/button[contains(@aria-label, "comment")]')
                        comments_text = comments_button.text
                        
                        # استخراج عدد از متن کامنت
                        comments_count = "".join(re.findall(r'\d+', comments_text))
                        if not comments_count:
                            comments_count = "0"
                        
                        post_info["comments"] = comments_count
                        if user_id:
                            socket_handler.emit_progress(
                                event='comment_count',
                                data={
                                    "message": "تعداد کامنت‌ها",
                                    "comment_count": comments_count
                                },
                                user_id=user_id
                            )
                    except NoSuchElementException:
                        post_info["comments"] = "0"
                        comments_count = "0"
                    bot_logger.info("تعداد کامنت‌ها یافت شد")
                    
                    # استخراج نام کاربری
                    try:
                        username_element = post.find_element(By.XPATH, './/span[@aria-hidden="true"]')
                        username = username_element.text.strip()
                        post_info["username"] = username
                    except NoSuchElementException:
                        post_info["username"] = "No username"
                        username = "No username"
                    bot_logger.info("یوزرنیم یافت شد")
                    
                    posts_data.append(post_info)
                    
                    # Debug: Log username and caption preview to compare with manual search
                    caption_preview = caption[:80] if caption else "No caption"
                    bot_logger.info(f"📝 Post extracted - User: {username[:50]} | Caption: {caption_preview}...")
                    bot_logger.info("اطلاعات پست ذخیره شد")

                    # ✅ ذخیره با keyword_id
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO linkdeen_posts (post_link,caption,reactions,comments,username,keyword_id,analyzed) VALUES"
                    " (%s,%s,%s,%s,%s,%s,%s)", 
                                    (post_info.get("link", "No link found"),caption,reactions,comments_count,username,keyword_id,0))
                    conn.commit()

                    last_inserted_id = cursor.lastrowid
                    post_info["post_id"] = last_inserted_id  # ✅ ذخیره post_id برای استفاده بعدی
                    cursor.close()
                    conn.close()
                    bot_logger.info(f"✅ پست با ID {last_inserted_id} ذخیره شد")
                    
                except Exception as e:
                    bot_logger.error(f"خطا در استخراج اطلاعات پست: {e}")
                    
            # اسکرول صفحه
            bot.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # صبر برای بارگذاری پست‌های بیشتر

            try:
                load_more_button = bot.driver.find_element(By.XPATH, "//button[span[text()='See more results']]")
                load_more_button.click()
                time.sleep(5)
            except NoSuchElementException:
                pass

        # ✅ جمع‌آوری کامنت‌ها برای هر پست
        if max_comments > 0:
            bot_logger.info(f"🔄 شروع جمع‌آوری کامنت‌ها (حداکثر {max_comments} کامنت برای هر پست)...")
        else:
            bot_logger.info("⏭️ جمع‌آوری کامنت غیرفعال است (max_comments=0)")

        conn = get_db_connection()
        cursor = conn.cursor()
        for data in posts_data:
            comments_data = []
            post_id = data.get('post_id')

            if data.get('link') and data.get('link') != "No link found" and post_id and max_comments > 0:
                try:
                    bot_logger.info(f"🔍 جمع‌آوری کامنت‌ها برای پست {post_id} via {data.get('link')}...")
                    try:
                        bot.driver.get(data['link'])
                        time.sleep(4)
                        bot.driver.execute_script('window.scrollTo(0, document.body.scrollHeight/2);')
                        time.sleep(2)
                    except Exception as e_nav:
                        bot_logger.warning(f"Could not navigate to post link: {e_nav}")

                    comment_selectors = [
                        './/article[contains(@class, "comments-comment-entity")]',
                        './/div[contains(@class, "comments-comments-list__comment-item")]',
                        './/div[contains(@class, "feed-shared-comment")]',
                        './/li[contains(@class, "comments-comment-item")]'
                    ]

                    comments = []
                    for sel in comment_selectors:
                        try:
                            comments = bot.driver.find_elements(By.XPATH, sel)
                            if comments and len(comments) > 0:
                                bot_logger.info(f"📝 Comments found with selector {sel}: {len(comments)}")
                                break
                        except Exception:
                            continue

                    for comment in comments[:max_comments]:
                        try:
                            commenter = None
                            comment_text = None

                            commenter_selectors = [
                                './/a[contains(@class,"feed-shared-actor__name")]',
                                './/span[contains(@class,"comments-post-meta__name")]',
                                './/span[contains(@class,"comments-comment-meta__name")]',
                                './/span[contains(@class,"comments-comment-meta__description-title")]',
                                './/a[@data-control-name]'
                            ]
                            for cs in commenter_selectors:
                                try:
                                    el = comment.find_element(By.XPATH, cs)
                                    txt = el.text.strip()
                                    if txt:
                                        commenter = txt
                                        break
                                except Exception:
                                    continue

                            try:
                                comment_text = comment.find_element(By.XPATH, './/div[contains(@class, "comments-comment-item__main-content")]/span').text
                            except Exception:
                                try:
                                    comment_text = comment.find_element(By.XPATH, './/span[@dir="ltr" or @dir="rtl" and normalize-space(.)!=""]').text
                                except Exception:
                                    try:
                                        comment_text = comment.find_element(By.XPATH, './/p').text
                                    except Exception:
                                        comment_text = ''

                            if not commenter:
                                commenter = 'Unknown'
                            if not comment_text:
                                comment_text = ''

                            comment_data = {'commenter': commenter, 'comment_text': comment_text}
                            comments_data.append(comment_data)

                            try:
                                cursor.execute("INSERT INTO linkdeen_comments (linkdeen_post_id,commenter,comment_text) VALUES (%s,%s,%s)",
                                                (post_id, commenter, comment_text))
                                conn.commit()
                                bot_logger.info(f"✅ Saved comment from {commenter}")
                            except Exception as e_ins:
                                bot_logger.warning(f"Could not save comment: {e_ins}")

                            if user_id:
                                socket_handler.emit_progress(
                                    event='comment',
                                    data={'message': 'کامنت جمع آوری شد', 'commenter': commenter, 'comment_text': comment_text},
                                    user_id=user_id
                                )

                        except Exception as e:
                            bot_logger.warning(f"⚠️ Error extracting individual comment: {e}")
                            continue

                except Exception as e:
                    bot_logger.error(f"❌ خطا در جمع‌آوری کامنت‌های پست {post_id}: {e}")

            data['comments_detail'] = comments_data

        cursor.close()
        conn.close()
            
        bot_logger.info(f"✅ تعداد پست‌ها جمع آوری شده: {len(posts_data)}")
        return posts_data
    except Exception as e:
        bot_logger.error(f"❌ Error in get_keyword_posts: {str(e)}")
        raise  # مهم: خطا رو بالا بفرست تا Worker بگیرتش
