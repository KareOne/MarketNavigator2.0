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
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- آپدیت جدول پست‌ها
ALTER TABLE linkdeen_posts 
ADD COLUMN hashtag_id INT NULL,
ADD COLUMN analyzed TINYINT(1) DEFAULT 0,
ADD COLUMN analysis_status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending',
ADD COLUMN analysis_error TEXT NULL,
ADD INDEX idx_analyzed (analyzed),
ADD INDEX idx_analysis_status (analysis_status),
ADD INDEX idx_hashtag_id (hashtag_id);
