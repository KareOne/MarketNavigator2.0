from config.config import get_db_connection, get_global_bot
from utils.logger import bot_logger
import time
from core.bot.linkdeen_bot import LinkedinBot
import random
import pymysql
import os
from utils.exceptions import LoginError
import base64
from services.socket_handlers import get_socket_handlers
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException


def get_page(request):
    """
    این endpoint فقط نام Page را در صف ذخیره می‌کند
    Worker خودش به صورت خودکار پردازش می‌کند
    """
    try:
        data = request.get_json()
        page_name = data.get("page_name")
        user_id = data.get("user_id")  # اختیاری - برای ارسال socket events
        
        if not page_name:
            return {"status": "error", "message": "نام Page الزامی است"}, 400
        
        # حذف فضاهای خالی اضافی
        page_name = page_name.strip()
        
        # چک کردن تکراری بودن
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, status FROM pages_queue WHERE page_name = %s AND status IN ('pending', 'processing') LIMIT 1",
            (page_name,)
        )
        existing = cursor.fetchone()
        
        if existing:
            cursor.close()
            conn.close()
            bot_logger.info(f"⚠️ Page '{page_name}' قبلاً در صف وجود دارد (ID: {existing['id']}, Status: {existing['status']})")
            return {
                "status": "info",
                "message": f"Page '{page_name}' قبلاً در صف قرار دارد",
                "queue_id": existing['id'],
                "queue_status": existing['status']
            }
        
        # ذخیره در صف با status = pending
        cursor.execute(
            "INSERT INTO pages_queue (page_name, user_id, status) VALUES (%s, %s, 'pending')",
            (page_name, user_id)
        )
        conn.commit()
        queue_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        bot_logger.info(f"✅ Page '{page_name}' با ID {queue_id} در صف قرار گرفت - Worker به زودی پردازش می‌کند")
        
        return {
            "status": "success",
            "message": f"Page '{page_name}' در صف قرار گرفت و به زودی توسط Worker پردازش می‌شود",
            "queue_id": queue_id,
            "data": {
                "page_name": page_name,
                "user_id": user_id
            }
        }
        
    except Exception as e:
        bot_logger.error(f"❌ خطا در افزودن Page به صف: {e}")
        return {"status": "error", "message": str(e)}, 500


def get_page2(page_name, page_queue_id=None, user_id=None):
    """
    جمع‌آوری کامل اطلاعات LinkedIn Company Page
    - مرحله 1: جمع‌آوری از صفحه اصلی
    - مرحله 2: جمع‌آوری از صفحه /about
    این تابع فقط توسط Worker صدا زده می‌شود
    
    Args:
        page_name: نام صفحه شرکت در LinkedIn
        page_queue_id: ID صفحه در pages_queue
        user_id: ID کاربر برای ارسال پیشرفت (اختیاری)
        
    Returns:
        dict: اطلاعات جمع‌آوری شده صفحه
    """
    try:
        # Read LinkedIn credentials from environment variables
        random_username = os.getenv("LINKEDIN_USERNAME", "pr1")
        random_password = os.getenv("LINKEDIN_PASSWORD", "")
        
        bot_logger.info(f"🏢 شروع جمع‌آوری اطلاعات صفحه '{page_name}' (Queue ID: {page_queue_id})")
        bot_logger.info(f"🔐 Using LinkedIn account: {random_username}")
        
        # تنظیم Socket Handler برای ارسال پیشرفت
        socket_handler = get_socket_handlers()
        
        # استفاده از bot سراسری
        bot = get_global_bot(username=random_username, password=random_password, user_id=5, is_first=1)
        
        # ===== مرحله 1: جمع‌آوری از صفحه اصلی =====
        url = f"https://www.linkedin.com/company/{page_name}/"
        bot_logger.info(f"🌐 بازدید از صفحه اصلی: {url}")
        
        if user_id:
            socket_handler.emit_progress(
                event='page_scraping_started',
                data={"message": f"شروع جمع‌آوری صفحه {page_name}", "url": url},
                user_id=user_id
            )
        
        bot.driver.get(url)
        bot_logger.info("✅ Page loaded, sleeping...")
        time.sleep(10)
        bot_logger.info("✅ Sleep done, starting scroll...")
        
        # Scroll down to load content
        try:
            bot.driver.execute_script("window.scrollTo(0, 800);")
            time.sleep(3)
            bot.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
        except:
            pass
        
        # Debug: Log page source and check for authwall
        bot_logger.info("🔍 Starting page source check...")
        try:
            page_source = bot.driver.page_source
            page_source_len = len(page_source)
            bot_logger.info(f"📄 طول HTML صفحه: {page_source_len} کاراکتر")
            
            # Check if redirected to login or authwall
            current_url = bot.driver.current_url
            bot_logger.info(f"🌐 Current URL: {current_url}")
            if 'login' in current_url.lower() or 'authwall' in current_url.lower():
                bot_logger.warning(f"⚠️ Redirect به صفحه login! URL: {current_url}")
            
            # Check for authwall in page source
            if 'authwall' in page_source.lower() or 'join now' in page_source.lower():
                bot_logger.warning("⚠️ LinkedIn authwall detected! Trying to login...")
                try:
                    bot.login(username=random_username, password="")
                    time.sleep(5)
                    bot.driver.get(url)
                    time.sleep(10)
                    bot_logger.info("✅ Re-loaded page after login attempt")
                except Exception as login_error:
                    bot_logger.error(f"❌ Login failed: {login_error}")
            
            # Log some page indicators
            if 'org-top-card' in page_source:
                bot_logger.info("✅ org-top-card detected in page")
            else:
                bot_logger.warning("⚠️ org-top-card NOT found in page!")
                
        except Exception as e:
            bot_logger.error(f"❌ خطا در بررسی صفحه: {e}", exc_info=True)
        
        # متغیرها با مقادیر پیش‌فرض
        page_title = page_name
        page_description = ""
        page_overview = ""
        last_post_content = ""
        company_industry = ""
        company_location = ""
        company_followers = ""
        company_employees = ""
        company_link = ""
        company_phone = ""
        company_value = ""
        
        # استخراج نام شرکت (page_title) - با چندین روش fallback
        try:
            # روش 1: XPath قدیمی
            try:
                page_title = bot.driver.find_element(By.XPATH, '//h1[contains(@class, "org-top-card-summary__title")]').text
            except:
                # روش 2: هر h1 در top card
                try:
                    page_title = bot.driver.find_element(By.XPATH, '//div[contains(@class, "org-top-card")]//h1').text
                except:
                    # روش 3: h1 با کلاس org-
                    try:
                        page_title = bot.driver.find_element(By.XPATH, '//h1[contains(@class, "org-")]').text
                    except:
                        # روش 4: اولین h1 در صفحه
                        page_title = bot.driver.find_element(By.TAG_NAME, 'h1').text
            
            page_title = page_title.strip()
            bot_logger.info(f"✅ نام شرکت: {page_title}")
            
            if user_id:
                socket_handler.emit_progress(
                    event='company_name',
                    data={"message": "نام شرکت", "company_name": page_title},
                    user_id=user_id
                )
        except Exception as e:
            bot_logger.warning(f"⚠️ نام شرکت یافت نشد: {e}")
        
        # استخراج توضیحات (page_description)
        try:
            try:
                page_description = bot.driver.find_element(By.XPATH, '//p[@class="org-top-card-summary__tagline"]').text
            except:
                page_description = bot.driver.find_element(By.XPATH, '//div[contains(@class, "org-top-card")]//p[contains(@class, "tagline")]').text
            bot_logger.info(f"✅ توضیحات: {page_description}")
        except Exception as e:
            bot_logger.warning(f"⚠️ توضیحات یافت نشد: {e}")
        
        # ===== استخراج آخرین پست از صفحه Posts =====
        # به جای featured post از main page، به /posts می‌رویم
        posts_url = f"https://www.linkedin.com/company/{page_name}/posts"
        bot_logger.info(f"🌐 رفتن به صفحه Posts: {posts_url}")
        bot.driver.get(posts_url)
        time.sleep(10)
        
        last_post_time = None
        try:
            post_found = False
            
            # روش 1: feed-shared-update-v2 (structure جدید) - اولین پست = جدیدترین
            try:
                posts = bot.driver.find_elements(By.XPATH, '//div[contains(@class, "feed-shared-update-v2")]')
                bot_logger.info(f"📊 تعداد پست‌های یافت شده: {len(posts)}")
                if posts and len(posts) > 0:
                    # اولین پست = جدیدترین پست به صورت زمانی
                    post = posts[0]
                    try:
                        # Try feed-shared-text__text-view
                        text_elem = post.find_element(By.XPATH, './/div[contains(@class, "feed-shared-text")]//span[@dir="ltr"]')
                        last_post_content = text_elem.text.strip()
                        post_found = True
                    except:
                        try:
                            # Try update-components-text
                            text_elem = post.find_element(By.XPATH, './/div[contains(@class, "update-components-text")]')
                            last_post_content = text_elem.text.strip()
                            post_found = True
                        except:
                            pass
            except:
                pass
            
            # روش 2: Any span with dir=ltr in posts section
            if not post_found:
                try:
                    all_spans = bot.driver.find_elements(By.XPATH, '//div[contains(@class, "scaffold-finite-scroll")]//span[@dir="ltr"]')
                    if len(all_spans) > 0:
                        for span in all_spans:
                            text = span.text.strip()
                            if len(text) > 20:  # At least 20 chars to be meaningful
                                last_post_content = text
                                post_found = True
                                break
                except:
                    pass
            
            # روش 3: feed-shared-inline-show-more-text
            if not post_found:
                try:
                    text_elem = bot.driver.find_element(By.XPATH, '//div[contains(@class, "feed-shared-inline-show-more-text")]')
                    last_post_content = text_elem.text.strip()
                    post_found = True
                except:
                    pass
            
            # استخراج تعداد و محتوای کامنت‌ها
            comments_count = 0
            comments_text = ""
            if post_found:
                try:
                    # Try to find comment count
                    comment_count_elements = bot.driver.find_elements(By.XPATH, '//button[contains(@aria-label, "comment")]//span[contains(@class, "social-details-social-counts__reactions-count")]')
                    if not comment_count_elements:
                        comment_count_elements = bot.driver.find_elements(By.XPATH, '//button[contains(., "comment")]//span[@aria-hidden="true"]')
                    
                    for elem in comment_count_elements:
                        text = elem.text.strip()
                        if text and any(char.isdigit() for char in text):
                            # Extract number from text like "23 comments" or "5"
                            import re
                            match = re.search(r'(\d+)', text)
                            if match:
                                comments_count = int(match.group(1))
                                bot_logger.info(f"💬 تعداد کامنت‌ها: {comments_count}")
                                break
                    
                    # Extract comment texts
                    if comments_count > 0:
                        # Scroll to load comments
                        try:
                            bot.driver.execute_script("window.scrollTo(0, 600);")
                            time.sleep(2)
                        except:
                            pass
                        
                        comment_elements = bot.driver.find_elements(By.XPATH, '//div[contains(@class, "comments-comment-item")]//span[@dir="ltr"]')
                        if not comment_elements:
                            comment_elements = bot.driver.find_elements(By.XPATH, '//article[contains(@class, "comments-comment")]//span[@dir="ltr"]')
                        
                        comments_list = []
                        for comment_elem in comment_elements[:10]:  # Get first 10 comments
                            comment_text = comment_elem.text.strip()
                            if comment_text and len(comment_text) > 5:
                                comments_list.append(comment_text)
                        
                        if comments_list:
                            comments_text = " | ".join(comments_list)
                            bot_logger.info(f"✅ {len(comments_list)} کامنت استخراج شد")
                        else:
                            bot_logger.info("⚠️ متن کامنت‌ها یافت نشد")
                except Exception as e:
                    bot_logger.warning(f"⚠️ خطا در استخراج کامنت‌ها: {e}")
            
            if post_found and last_post_content:
                bot_logger.info(f"✅ آخرین پست ({len(last_post_content)} کاراکتر): {last_post_content[:60]}...")
                
                # استخراج زمان انتشار پست - از اولین پست در /posts
                try:
                    from dateutil import parser
                    time_extracted = False
                    
                    # روش 1: time with datetime attribute anywhere in page
                    try:
                        time_elements = bot.driver.find_elements(By.XPATH, '//time[@datetime]')
                        bot_logger.info(f"📊 تعداد time elements با datetime: {len(time_elements)}")
                        if time_elements:
                            datetime_str = time_elements[0].get_attribute('datetime')
                            bot_logger.info(f"🕐 datetime string: {datetime_str}")
                            dt = parser.parse(datetime_str)
                            last_post_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                            bot_logger.info(f"✅ زمان انتشار پست (روش 1): {last_post_time}")
                            time_extracted = True
                    except Exception as e1:
                        bot_logger.info(f"روش 1 ناموفق: {e1}")
                    
                    # روش 2: any time tag
                    if not time_extracted:
                        try:
                            time_elements = bot.driver.find_elements(By.TAG_NAME, 'time')
                            bot_logger.info(f"📊 تعداد کل time elements: {len(time_elements)}")
                            if time_elements:
                                # Try each time element
                                for i, time_elem in enumerate(time_elements[:5]):
                                    datetime_str = time_elem.get_attribute('datetime')
                                    if datetime_str:
                                        dt = parser.parse(datetime_str)
                                        last_post_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                                        bot_logger.info(f"✅ زمان انتشار پست (روش 2, element {i}): {last_post_time}")
                                        time_extracted = True
                                        break
                        except Exception as e2:
                            bot_logger.info(f"روش 2 ناموفق: {e2}")
                    
                    # روش 3: text like "1d", "2w", etc - relative time
                    if not time_extracted:
                        try:
                            time_texts = bot.driver.find_elements(By.XPATH, '//*[contains(@class, "update-components-actor__sub-description")]//span')
                            bot_logger.info(f"📊 تعداد time text elements: {len(time_texts)}")
                            if time_texts:
                                time_text = time_texts[0].text.strip()
                                bot_logger.info(f"⏰ زمان نسبی: {time_text}")
                                
                                # Parse relative time (4d, 2w, 3mo, etc)
                                import datetime
                                import re
                                now = datetime.datetime.now()
                                
                                # Extract number and unit
                                match = re.search(r'(\d+)([a-z]+)', time_text.lower())
                                if match:
                                    value = int(match.group(1))
                                    unit = match.group(2)
                                    
                                    if unit in ['d', 'day', 'days']:
                                        post_time = now - datetime.timedelta(days=value)
                                    elif unit in ['w', 'wk', 'week', 'weeks']:
                                        post_time = now - datetime.timedelta(weeks=value)
                                    elif unit in ['h', 'hr', 'hour', 'hours']:
                                        post_time = now - datetime.timedelta(hours=value)
                                    elif unit in ['m', 'min', 'minute', 'minutes']:
                                        post_time = now - datetime.timedelta(minutes=value)
                                    elif unit in ['mo', 'month', 'months']:
                                        post_time = now - datetime.timedelta(days=value*30)
                                    elif unit in ['y', 'yr', 'year', 'years']:
                                        post_time = now - datetime.timedelta(days=value*365)
                                    else:
                                        post_time = now
                                    
                                    last_post_time = post_time.strftime('%Y-%m-%d %H:%M:%S')
                                    bot_logger.info(f"✅ زمان محاسبه شده از '{time_text}': {last_post_time}")
                                    time_extracted = True
                                else:
                                    bot_logger.warning(f"⚠️ نتوانستم '{time_text}' را parse کنم")
                        except Exception as e3:
                            bot_logger.info(f"روش 3 ناموفق: {e3}")
                    
                    if not time_extracted:
                        bot_logger.warning("⚠️ زمان انتشار پست یافت نشد - از همه روش‌ها")
                except Exception as time_error:
                    bot_logger.warning(f"⚠️ خطای کلی در استخراج زمان: {time_error}")
                    import traceback
                    bot_logger.warning(traceback.format_exc())
            else:
                bot_logger.warning("⚠️ محتوای پست یافت نشد یا خالی است")
        except Exception as e:
            bot_logger.warning(f"⚠️ خطا در استخراج پست: {e}")
        
        # استخراج اطلاعات شرکت - بر اساس ساختار دقیق HTML LinkedIn
        bot_logger.info("📊 شروع استخراج اطلاعات شرکت...")
        try:
            # Industry (صنعت) - با روش‌های مختلف
            try:
                industry_found = False
                # روش 1: org-top-card-summary-info-list structure
                try:
                    industry_elem = bot.driver.find_element(By.XPATH, '//div[contains(@class, "org-top-card-summary-info-list")]//div[contains(@class, "org-page-details__definition-text")]')
                    company_industry = industry_elem.text.strip()
                    industry_found = True
                except:
                    pass
                
                # روش 2: Find by "Industry" text
                if not industry_found:
                    try:
                        dt_elements = bot.driver.find_elements(By.XPATH, '//dt[contains(., "Industry")]/following-sibling::dd')
                        if dt_elements:
                            company_industry = dt_elements[0].text.strip()
                            industry_found = True
                    except:
                        pass
                
                # روش 3: Any text in org-top-card that looks like industry
                if not industry_found:
                    try:
                        all_text_elements = bot.driver.find_elements(By.XPATH, '//div[contains(@class, "org-top-card")]//div[contains(@class, "t-black--light")]')
                        for elem in all_text_elements:
                            text = elem.text.strip()
                            # Industry text usually doesn't contain numbers or commas
                            if text and not any(char in text for char in [',', 'follower', 'employee']) and len(text) > 5:
                                company_industry = text
                                industry_found = True
                                break
                    except:
                        pass
                
                if industry_found:
                    bot_logger.info(f"✅ صنعت (Industry): '{company_industry}'")
                else:
                    bot_logger.warning("⚠️ صنعت یافت نشد")
            except Exception as e:
                bot_logger.warning(f"⚠️ خطا در استخراج صنعت: {e}")
            
            # Location, Followers, Employees - استخراج با روش‌های متنوع
            try:
                # جمع‌آوری تمام آیتم‌های اطلاعاتی از top card
                all_info_texts = []
                
                # روش 1: org-top-card-summary-info-list__info-item
                try:
                    items = bot.driver.find_elements(By.XPATH, '//div[contains(@class, "org-top-card-summary-info-list__info-item")]')
                    all_info_texts.extend([item.text.strip() for item in items if item.text.strip()])
                except:
                    pass
                
                # روش 2: org-top-card-summary__info-item
                try:
                    items = bot.driver.find_elements(By.XPATH, '//div[contains(@class, "org-top-card-summary__info-item")]')
                    all_info_texts.extend([item.text.strip() for item in items if item.text.strip()])
                except:
                    pass
                
                # روش 3: Any div with company stats in org-top-card
                try:
                    items = bot.driver.find_elements(By.XPATH, '//div[contains(@class, "org-top-card")]//div[contains(@class, "t-black--light") or contains(@class, "org-top-card-summary-info-list")]')
                    all_info_texts.extend([item.text.strip() for item in items if item.text.strip() and len(item.text.strip()) > 3])
                except:
                    pass
                
                # Remove duplicates while preserving order
                seen = set()
                unique_texts = []
                for text in all_info_texts:
                    if text and text not in seen:
                        seen.add(text)
                        unique_texts.append(text)
                
                bot_logger.info(f"✅ پیدا شد {len(unique_texts)} آیتم اطلاعاتی منحصر به فرد")
                
                # تحلیل و تشخیص نوع هر آیتم
                for text in unique_texts:
                    text_lower = text.lower()
                    
                    # تشخیص Location (معمولاً شامل ویرگول و نام شهر/کشور)
                    if not company_location:
                        if ',' in text and not any(keyword in text_lower for keyword in ['follower', 'employee', 'on linkedin']):
                            company_location = text
                            bot_logger.info(f"✅ موقعیت (Location): '{company_location}'")
                    
                    # تشخیص Followers (شامل کلمه follower)
                    if not company_followers:
                        if 'follower' in text_lower:
                            company_followers = text
                            bot_logger.info(f"✅ فالوئرها (Followers): '{company_followers}'")
                            if user_id:
                                socket_handler.emit_progress(
                                    event='followers_count',
                                    data={"message": "تعداد فالوئر", "followers": company_followers},
                                    user_id=user_id
                                )
                            continue
                    
                    # تشخیص Employees (شامل employee یا on LinkedIn)
                    if not company_employees:
                        if 'employee' in text_lower or 'on linkedin' in text_lower:
                            company_employees = text
                            bot_logger.info(f"✅ کارمندان (Employees): '{company_employees}'")
                            continue
                    
            except Exception as e:
                bot_logger.warning(f"⚠️ خطا در استخراج اطلاعات شرکت: {e}")
                
                # روش جایگزین: استفاده از تمام info-items
                try:
                    all_items = bot.driver.find_elements(
                        By.XPATH,
                        '//div[@class="org-top-card-summary-info-list"]//div[@class="org-top-card-summary-info-list__info-item"]'
                    )
                    
                    bot_logger.info(f"📊 تعداد کل info-items: {len(all_items)}")
                    
                    # Industry = اولین، Location = دومین، Followers = سومین
                    if len(all_items) >= 2:
                        company_location = all_items[1].text.strip()
                        bot_logger.info(f"✅ موقعیت (جایگزین): '{company_location}'")
                    
                    if len(all_items) >= 3:
                        followers_text = all_items[2].text.strip()
                        company_followers = ' '.join(followers_text.split())
                        bot_logger.info(f"✅ فالوئرها (جایگزین): '{company_followers}'")
                        
                except Exception as e:
                    bot_logger.error(f"⚠️ روش جایگزین ناموفق: {e}")
                
                # Employees از لینک
                try:
                    employees_elem = bot.driver.find_element(
                        By.XPATH,
                        '//div[@class="org-top-card-summary-info-list"]//a[contains(@href, "/search/results/people/")]//span'
                    )
                    employees_text = employees_elem.text.strip()
                    company_employees = ' '.join(employees_text.split())
                    bot_logger.info(f"✅ تعداد کارمندان (جایگزین): '{company_employees}'")
                except Exception as e:
                    bot_logger.warning(f"⚠️ تعداد کارمندان با روش جایگزین یافت نشد: {e}")
                
        except Exception as e:
            bot_logger.error(f"❌ خطای کلی در استخراج اطلاعات شرکت: {e}")
            import traceback
            bot_logger.error(traceback.format_exc())
        
        # ===== مرحله 2: جمع‌آوری از صفحه About =====
        about_url = f"https://www.linkedin.com/company/{page_name}/about"
        bot_logger.info(f"🌐 رفتن به صفحه About: {about_url}")
        bot.driver.get(about_url)
        time.sleep(10)
        
        # بررسی اینکه به صفحه login redirect نشده باشیم
        current_url = bot.driver.current_url
        if "login" in current_url.lower() or "signin" in current_url.lower():
            bot_logger.warning(f"⚠️ Redirect به login - تلاش مجدد...")
            bot.login(username=random_username, password="")
            time.sleep(5)
            bot.driver.get(about_url)
            time.sleep(10)
        
        # استخراج صنعت (company_industry) از About page - بهتر از main page
        try:
            industry_found = False
            
            # Debug: log all dt elements
            try:
                all_dts = bot.driver.find_elements(By.XPATH, '//dt')
                bot_logger.info(f"📋 تعداد dt elements: {len(all_dts)}")
                for i, dt in enumerate(all_dts[:10]):  # First 10
                    bot_logger.info(f"  dt[{i}]: {dt.text[:50] if dt.text else 'empty'}")
            except:
                pass
            
            # روش 1: dt with "Industry" text
            try:
                industry_element = bot.driver.find_element(By.XPATH, '//dt[contains(text(), "Industry")]/following-sibling::dd')
                company_industry = industry_element.text.strip()
                if company_industry:
                    industry_found = True
                    bot_logger.info(f"✅ صنعت (روش 1): {company_industry}")
            except Exception as e:
                bot_logger.info(f"روش 1 صنعت ناموفق: {e}")
            
            # روش 2: case-insensitive search
            if not industry_found:
                try:
                    dts = bot.driver.find_elements(By.XPATH, '//dt')
                    bot_logger.info(f"🔍 جستجو در {len(dts)} dt element...")
                    for i, dt in enumerate(dts):
                        dt_text = dt.text.strip().lower()
                        bot_logger.info(f"  بررسی dt[{i}]: '{dt_text}'")
                        if 'industry' in dt_text:
                            dd = dt.find_element(By.XPATH, './following-sibling::dd[1]')
                            company_industry = dd.text.strip()
                            if company_industry:
                                industry_found = True
                                bot_logger.info(f"✅ صنعت (روش 2): {company_industry}")
                                break
                except Exception as e2:
                    bot_logger.info(f"روش 2 صنعت ناموفق: {e2}")
            
            # روش 3: xpath with normalize-space
            if not industry_found:
                try:
                    industry_element = bot.driver.find_element(By.XPATH, '//dt[normalize-space(translate(., "INDUSTRY", "industry"))="industry"]/following-sibling::dd')
                    company_industry = industry_element.text.strip()
                    if company_industry:
                        industry_found = True
                        bot_logger.info(f"✅ صنعت (روش 3): {company_industry}")
                except Exception as e3:
                    bot_logger.info(f"روش 3 صنعت ناموفق: {e3}")
            
            if not industry_found:
                bot_logger.warning("⚠️ صنعت در About page یافت نشد")
        except Exception as e:
            bot_logger.warning(f"⚠️ خطا در استخراج صنعت از About: {e}")
        
        # استخراج وبسایت (company_link) - با روش‌های مختلف
        try:
            website_found = False
            # روش 1: dt/dd structure
            try:
                website_element = bot.driver.find_element(By.XPATH, '//dt[contains(., "Website")]/following-sibling::dd//a[@href]')
                company_link = website_element.get_attribute('href')
                website_found = True
            except:
                # روش 2: Search for any external link in about section
                try:
                    links = bot.driver.find_elements(By.XPATH, '//section[contains(@class, "about")]//a[@href]')
                    for link in links:
                        href = link.get_attribute('href')
                        if href and 'linkedin.com' not in href and href.startswith('http'):
                            company_link = href
                            website_found = True
                            break
                except:
                    pass
            
            if website_found:
                bot_logger.info(f"✅ وبسایت: {company_link}")
            
            if user_id:
                socket_handler.emit_progress(
                    event='company_website',
                    data={"message": "وبسایت شرکت", "website": company_link},
                    user_id=user_id
                )
        except Exception:
            bot_logger.warning("⚠️ وبسایت یافت نشد")
        
        # استخراج شماره تلفن (company_phone)
        try:
            phone_element = bot.driver.find_element(By.XPATH, '//dt[contains(., "Phone")]/following-sibling::dd//a[@href]')
            company_phone = phone_element.get_attribute('href').replace('tel:', '')
            bot_logger.info(f"✅ تلفن: {company_phone}")
        except Exception:
            bot_logger.warning("⚠️ تلفن یافت نشد")
        
        # استخراج سال تاسیس (company_value)
        try:
            founded_element = bot.driver.find_element(By.XPATH, '//dt[contains(., "Founded")]/following-sibling::dd')
            company_value = founded_element.text.strip()
            bot_logger.info(f"✅ سال تاسیس: {company_value}")
        except Exception:
            bot_logger.warning("⚠️ سال تاسیس یافت نشد")
            # Fallback
            try:
                value_elements = bot.driver.find_elements(By.XPATH, '//dd[@class="mb4 t-black--light text-body-medium"]')
                if value_elements:
                    company_value = value_elements[-1].text
            except Exception:
                pass
        
        # استخراج Overview (page_overview) - با روش‌های مختلف
        try:
            overview_found = False
            # روش 1: h2 + sibling p
            try:
                page_overview = bot.driver.find_element(By.XPATH, '//h2[contains(., "Overview")]/following-sibling::p').text
                overview_found = True
            except:
                # روش 2: div with overview class
                try:
                    page_overview = bot.driver.find_element(By.XPATH, '//div[contains(@class, "overview")]//p').text
                    overview_found = True
                except:
                    # روش 3: section about with first paragraph
                    try:
                        page_overview = bot.driver.find_element(By.XPATH, '//section[contains(@class, "about")]//p').text
                        overview_found = True
                    except:
                        pass
            
            if overview_found:
                bot_logger.info(f"✅ Overview: {page_overview[:50]}...")
        except Exception:
            bot_logger.warning("⚠️ Overview یافت نشد")
        
        # ===== ذخیره در دیتابیس =====
        if page_title:  # فقط اگر حداقل نام شرکت داشتیم
            conn = get_db_connection()
            cursor = conn.cursor()
            
            bot_logger.info("💾 ذخیره در دیتابیس...")
            cursor.execute(
                """
                INSERT INTO linkdeen_pages (
                    page_title,
                    page_description,
                    page_overview,
                    last_post_content,
                    post_created_at,
                    company_industry,
                    company_location,
                    company_followers,
                    company_employees,
                    company_link,
                    company_phone,
                    company_value,
                    comments,
                    comments_text,
                    page_queue_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    page_title,
                    page_description,
                    page_overview,
                    last_post_content,
                    last_post_time,
                    company_industry,
                    company_location,
                    company_followers,
                    company_employees,
                    company_link,
                    company_phone,
                    company_value,
                    comments_count,
                    comments_text,
                    page_queue_id,
                ),
            )
            conn.commit()
            page_id = cursor.lastrowid
            cursor.close()
            conn.close()
            
            bot_logger.info(f"✅ صفحه '{page_name}' با ID {page_id} ذخیره شد")
            
            if user_id:
                socket_handler.emit_progress(
                    event='page_saved',
                    data={"message": "صفحه با موفقیت ذخیره شد", "page_id": page_id},
                    user_id=user_id
                )
        
        # بازگشت داده‌ها
        return {
            'page_title': page_title,
            'page_description': page_description,
            'page_overview': page_overview,
            'last_post_content': last_post_content,
            'post_created_at': last_post_time,
            'company_info': {
                'industry': company_industry,
                'location': company_location,
                'followers': company_followers,
                'employees': company_employees
            },
            'company_link': company_link,
            'company_phone': company_phone,
            'company_value': company_value,
            'members_count': ""
        }
        
    except Exception as e:
        bot_logger.error(f"❌ Error in get_page2: {str(e)}")
        raise  # مهم: خطا رو بالا بفرست تا Worker بگیرتش


def add_account(request):
    user = request.user
    data = request.get_json()
    user_id = user.id
    username = data.get("username")
    password = data.get("password")
    bot = None
    if not username or not password:
        return {"status": "error", "message": "نام کاربری و رمز عبور الزامی هستند"}, 400

    try:
        
        conn = get_db_connection()
        cursor = conn.cursor()
        # بررسی وجود پیج
        cursor.execute("SELECT username FROM pages WHERE username = %s AND user_id = %s", 
                      (username, user.id))
        existing_page = cursor.fetchone()
        
        if existing_page:
            
            page_id = existing_page['id']
            bot_logger.info(f"پیج {username} قبلاً وجود دارد، هیچ اقدامی انجام نمی‌شود")
            time.sleep(20)
            if bot:
                bot.cleanup()
            conn.close()
            return {
                "status": "success",
                "message": f"پیج '{username}' قبلاً وجود دارد"
            }, 200
        else:
            
            cursor.execute("SELECT username FROM pages WHERE username = %s", (username,))
            exist_page = cursor.fetchone()
            if exist_page:
                bot_logger.info("پیج قبلا با اکانت کس دیگری وارد شده است")
                conn.close()
                return {
                    "status": "error",
                    "message": f"پیج {username} برای کس دیگری است"
                }, 403

            bot = LinkedinBot(username, is_first=1)
            
            #bot.login(username, password, user_id)

            bot_logger.info("پیج شما تازه وارد شده است باید صبر کنید تا فالوئرها را اضافه کنیم")
            # درج پیج جدید
            
            cursor.execute("""
                INSERT INTO pages (username, user_id)
                VALUES (%s, %s)
            """, (username, user.id))
            page_id = cursor.lastrowid
            
            conn.commit()

        

            
            if bot:
                pass
                #bot.cleanup()

            conn.close()
            return {
                "status": "success",
                "message": f"کاربر '{username}' با موفقیت اضافه شد و فالوئرها ذخیره شدند",
                "data": {"page_id": page_id, "username": username}
            }, 201

    except LoginError as e:
        bot_logger.error(f"خطای ورود برای {username}: {str(e)}")
        if bot:
            pass
            #bot.cleanup()
        return {"status": "error", "message": f"خطای ورود: {str(e)}"}, 401
    except pymysql.MySQLError as e:
        bot_logger.error(f"خطای دیتابیس برای {username}: {str(e)}")
        if bot:
            pass
            #bot.cleanup()
        return {"status": "error", "message": f"خطای دیتابیس: {str(e)}"}, 500
    except Exception as e:
        bot_logger.error(f"خطای غیرمنتظره برای {username}: {str(e)}")
        if bot:
            pass
            #bot.cleanup()
        return {"status": "error", "message": f"خطا: {str(e)}"}, 500

def list_pages(request):
    user = request.user
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, followers, following, caption, number_of_posts, profile_picture_path
            FROM pages 
            WHERE user_id = %s
        """, (user.id,))
        pages = cursor.fetchall()
        conn.close()
        print(pages)

        if not pages:
            return {"status": "success", "message": "هیچ پیجی برای این کاربر یافت نشد", "data": []}, 200
        
        page_list = []
        for page in pages:
            profile_picture_base64 = None
            if page['profile_picture_path']:
                try:
                    with open(page['profile_picture_path'], 'rb') as image_file:
                        profile_picture_base64 = base64.b64encode(image_file.read()).decode('utf-8')
                except Exception as e:
                    bot_logger.error(f"خطا در تبدیل تصویر پروفایل به Base64 برای {page['username']}: {str(e)}")

            page_list.append({
                "id": page['id'],
                "username": page['username'],
                "followers": page['followers'],
                "following": page['following'],
                "caption": page['caption'],
                "number_of_posts": page['number_of_posts'],
                "profile_picture_base64": profile_picture_base64
            })

        bot_logger.info(f"{len(page_list)} پیج برای کاربر {user.phone_number} بازیابی شد")
        return {"status": "success", "message": "پیج‌ها با موفقیت بازیابی شدند", "data": page_list}, 200

    except pymysql.MySQLError as e:
        bot_logger.error(f"خطای دیتابیس برای {user.phone_number}: {str(e)}")
        return {"status": "error", "message": f"خطای دیتابیس: {str(e)}"}, 500
    except Exception as e:
        bot_logger.error(f"خطای غیرمنتظره برای {user.phone_number}: {str(e)}")
        return {"status": "error", "message": f"خطا در بازیابی پیج‌ها: {str(e)}"}, 500
