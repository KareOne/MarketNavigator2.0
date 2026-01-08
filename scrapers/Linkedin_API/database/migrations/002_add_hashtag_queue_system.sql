-- Migration: Add hashtag queue system
-- Date: 2025-10-22
-- Description: Add hashtags_queue table and update linkdeen_posts for queue processing

-- جدول صف هشتگ‌ها
CREATE TABLE IF NOT EXISTS hashtags_queue (
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
    INDEX idx_created_at (created_at),
    INDEX idx_hashtag (hashtag)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- آپدیت جدول پست‌ها
ALTER TABLE linkdeen_posts 
ADD COLUMN IF NOT EXISTS hashtag_id INT NULL AFTER username,
ADD COLUMN IF NOT EXISTS analyzed TINYINT(1) DEFAULT 0 AFTER hashtag_id,
ADD COLUMN IF NOT EXISTS analysis_status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending' AFTER analyzed,
ADD COLUMN IF NOT EXISTS analysis_error TEXT NULL AFTER analysis_status,
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP AFTER analysis_error,
ADD INDEX IF NOT EXISTS idx_analyzed (analyzed),
ADD INDEX IF NOT EXISTS idx_analysis_status (analysis_status),
ADD INDEX IF NOT EXISTS idx_hashtag_id (hashtag_id);

-- نمایش وضعیت جداول
SELECT 'Migration completed successfully!' as status;
