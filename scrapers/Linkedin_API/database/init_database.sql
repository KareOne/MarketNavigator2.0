-- Initial database setup for linkdeen_bot (MySQL)
-- Safe to run multiple times (idempotent)

CREATE DATABASE IF NOT EXISTS `linkdeen_bot` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE `linkdeen_bot`;

-- Users table (simple user registry)
CREATE TABLE IF NOT EXISTS `users` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `phone_number` VARCHAR(20) NOT NULL,
    PRIMARY KEY (`id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- Pages (user to page mapping) – kept minimal
CREATE TABLE IF NOT EXISTS `pages` (
    `username` VARCHAR(50) NOT NULL,
    `user_id` INT NOT NULL,
    PRIMARY KEY (`username`),
    KEY `user_id` (`user_id`),
    CONSTRAINT `pages_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- Linkdeen posts collected from hashtags
CREATE TABLE IF NOT EXISTS `linkdeen_posts` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `post_link` LONGTEXT,
    `caption` TEXT,
    `reactions` INT DEFAULT 0,
    `comments` INT DEFAULT 0,
    `username` VARCHAR(255) DEFAULT NULL,
    `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    `hashtag_id` INT DEFAULT NULL,
    `keyword_id` INT DEFAULT NULL,
    `analyzed` TINYINT(1) DEFAULT 0,
    `analysis_status` ENUM(
        'pending',
        'processing',
        'completed',
        'failed'
    ) DEFAULT 'pending',
    `analysis_error` TEXT,
    PRIMARY KEY (`id`),
    KEY `idx_analyzed` (`analyzed`),
    KEY `idx_analysis_status` (`analysis_status`),
    KEY `idx_hashtag_id` (`hashtag_id`),
    KEY `idx_keyword_id` (`keyword_id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- Comments for collected posts
CREATE TABLE IF NOT EXISTS `linkdeen_comments` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `linkdeen_post_id` INT DEFAULT NULL,
    `commenter` VARCHAR(255) DEFAULT NULL,
    `comment_text` TEXT,
    `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `linkdeen_post_id` (`linkdeen_post_id`),
    CONSTRAINT `linkdeen_comments_ibfk_1` FOREIGN KEY (`linkdeen_post_id`) REFERENCES `linkdeen_posts` (`id`) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- Company pages data
CREATE TABLE IF NOT EXISTS `linkdeen_pages` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `page_title` VARCHAR(255) NOT NULL,
    `page_description` TEXT,
    `page_overview` TEXT,
    `last_post_content` TEXT,
    `post_created_at` DATETIME NULL COMMENT 'Timestamp when the LinkedIn post was actually created',
    `company_industry` VARCHAR(255) DEFAULT NULL,
    `company_location` VARCHAR(255) DEFAULT NULL,
    `company_followers` VARCHAR(255) DEFAULT NULL,
    `company_employees` VARCHAR(255) DEFAULT NULL,
    `company_link` VARCHAR(255) DEFAULT NULL,
    `company_phone` VARCHAR(20) DEFAULT NULL,
    `company_value` TEXT DEFAULT NULL,
    `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp when the data was scraped',
    `page_queue_id` INT DEFAULT NULL,
    PRIMARY KEY (`id`),
    KEY `idx_page_queue_id` (`page_queue_id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- Hashtag processing queue
CREATE TABLE IF NOT EXISTS `hashtags_queue` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `hashtag` VARCHAR(255) NOT NULL,
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
    KEY `idx_hashtag` (`hashtag`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- Pages processing queue
CREATE TABLE IF NOT EXISTS `pages_queue` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `page_name` VARCHAR(255) NOT NULL,
    `user_id` INT NULL,
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
    KEY `idx_created_at` (`created_at`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- Keywords processing queue
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

) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;