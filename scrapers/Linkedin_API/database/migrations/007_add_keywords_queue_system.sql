-- Migration 007: Add Keywords Queue System
-- Add keywords_queue table for keyword search functionality

CREATE TABLE IF NOT EXISTS `keywords_queue` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `keyword` VARCHAR(500) NOT NULL COMMENT 'Search keyword or phrase',
    `max_posts` INT DEFAULT 5,
    `max_comments` INT DEFAULT 5,
    `user_id` INT DEFAULT NULL,
    `status` ENUM(
        'pending',
        'processing',
        'completed',
        'failed'
    ) DEFAULT 'pending',
    `error_message` TEXT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `started_at` TIMESTAMP NULL,
    `completed_at` TIMESTAMP NULL,
    PRIMARY KEY (`id`),
    KEY `idx_status` (`status`),
    KEY `idx_created_at` (`created_at`),
    KEY `idx_keyword` (`keyword`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- Add keyword_id field to linkdeen_posts table
ALTER TABLE `linkdeen_posts`
ADD COLUMN `keyword_id` INT DEFAULT NULL AFTER `hashtag_id`,
ADD KEY `idx_keyword_id` (`keyword_id`);