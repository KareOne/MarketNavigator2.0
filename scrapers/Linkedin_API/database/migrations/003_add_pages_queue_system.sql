-- Migration: Add pages queue system
-- Date: 2025-10-23
-- Description: Add pages_queue table and update linkdeen_pages and hashtags_queue

-- 1️⃣ جدول صف Page ها
CREATE TABLE IF NOT EXISTS pages_queue (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2️⃣ آپدیت جدول linkdeen_pages
-- بررسی و اضافه کردن ستون page_queue_id
SET @dbname = DATABASE();
SET @tablename = 'linkdeen_pages';

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
                   WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename 
                   AND COLUMN_NAME = 'page_queue_id');

SET @sql = IF(@col_exists = 0, 
              'ALTER TABLE linkdeen_pages ADD COLUMN page_queue_id INT NULL, ADD INDEX idx_page_queue_id (page_queue_id)',
              'SELECT "Column page_queue_id already exists" AS message');

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 3️⃣ آپدیت جدول hashtags_queue
-- اضافه کردن user_id (اختیاری)
SET @tablename2 = 'hashtags_queue';

SET @col_exists2 = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename2 
                    AND COLUMN_NAME = 'user_id');

SET @sql2 = IF(@col_exists2 = 0, 
               'ALTER TABLE hashtags_queue ADD COLUMN user_id INT NULL AFTER max_comments',
               'SELECT "Column user_id already exists in hashtags_queue" AS message');

PREPARE stmt2 FROM @sql2;
EXECUTE stmt2;
DEALLOCATE PREPARE stmt2;

-- نمایش وضعیت
SELECT 'Migration 003 completed successfully!' as status;
SELECT COUNT(*) as pages_queue_exists FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'pages_queue';
