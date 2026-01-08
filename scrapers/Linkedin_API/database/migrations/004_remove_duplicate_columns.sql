-- =====================================
-- Migration: حذف ستون‌های تکراری از جدول linkdeen_pages
-- =====================================
-- این ستون‌ها تکراری هستند و اطلاعات آن‌ها در ستون‌های دیگر موجود است:
-- - page_name: اطلاعات در pages_queue است
-- - company_name: از page_title استفاده می‌شود
-- - followers: company_followers موجود است
-- - description: page_description موجود است
-- - website: company_link موجود است
-- - industry: company_industry موجود است
-- - company_size: company_employees موجود است

-- ابتدا بررسی می‌کنیم که ستون‌ها وجود دارند یا نه
SET @exist_page_name = (
    SELECT COUNT(*) 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = DATABASE() 
      AND TABLE_NAME = 'linkdeen_pages' 
      AND COLUMN_NAME = 'page_name'
);

SET @exist_company_name = (
    SELECT COUNT(*) 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = DATABASE() 
      AND TABLE_NAME = 'linkdeen_pages' 
      AND COLUMN_NAME = 'company_name'
);

SET @exist_followers = (
    SELECT COUNT(*) 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = DATABASE() 
      AND TABLE_NAME = 'linkdeen_pages' 
      AND COLUMN_NAME = 'followers'
);

SET @exist_description = (
    SELECT COUNT(*) 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = DATABASE() 
      AND TABLE_NAME = 'linkdeen_pages' 
      AND COLUMN_NAME = 'description'
);

SET @exist_website = (
    SELECT COUNT(*) 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = DATABASE() 
      AND TABLE_NAME = 'linkdeen_pages' 
      AND COLUMN_NAME = 'website'
);

SET @exist_industry = (
    SELECT COUNT(*) 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = DATABASE() 
      AND TABLE_NAME = 'linkdeen_pages' 
      AND COLUMN_NAME = 'industry'
);

SET @exist_company_size = (
    SELECT COUNT(*) 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = DATABASE() 
      AND TABLE_NAME = 'linkdeen_pages' 
      AND COLUMN_NAME = 'company_size'
);

-- حذف ستون page_name
SET @sql_drop_page_name = IF(
    @exist_page_name > 0,
    'ALTER TABLE linkdeen_pages DROP COLUMN page_name',
    'SELECT "Column page_name does not exist" AS message'
);
PREPARE stmt FROM @sql_drop_page_name;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- حذف ستون company_name
SET @sql_drop_company_name = IF(
    @exist_company_name > 0,
    'ALTER TABLE linkdeen_pages DROP COLUMN company_name',
    'SELECT "Column company_name does not exist" AS message'
);
PREPARE stmt FROM @sql_drop_company_name;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- حذف ستون followers
SET @sql_drop_followers = IF(
    @exist_followers > 0,
    'ALTER TABLE linkdeen_pages DROP COLUMN followers',
    'SELECT "Column followers does not exist" AS message'
);
PREPARE stmt FROM @sql_drop_followers;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- حذف ستون description
SET @sql_drop_description = IF(
    @exist_description > 0,
    'ALTER TABLE linkdeen_pages DROP COLUMN description',
    'SELECT "Column description does not exist" AS message'
);
PREPARE stmt FROM @sql_drop_description;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- حذف ستون website
SET @sql_drop_website = IF(
    @exist_website > 0,
    'ALTER TABLE linkdeen_pages DROP COLUMN website',
    'SELECT "Column website does not exist" AS message'
);
PREPARE stmt FROM @sql_drop_website;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- حذف ستون industry
SET @sql_drop_industry = IF(
    @exist_industry > 0,
    'ALTER TABLE linkdeen_pages DROP COLUMN industry',
    'SELECT "Column industry does not exist" AS message'
);
PREPARE stmt FROM @sql_drop_industry;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- حذف ستون company_size
SET @sql_drop_company_size = IF(
    @exist_company_size > 0,
    'ALTER TABLE linkdeen_pages DROP COLUMN company_size',
    'SELECT "Column company_size does not exist" AS message'
);
PREPARE stmt FROM @sql_drop_company_size;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- اطمینان از اینکه page_queue_id نمی‌تواند NULL باشد
ALTER TABLE linkdeen_pages 
MODIFY COLUMN page_queue_id INT NULL;

SELECT '✅ ستون‌های تکراری با موفقیت حذف شدند' AS message;
