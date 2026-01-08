-- --------------------------------------------------------
-- Host:                         127.0.0.1
-- Server version:               8.0.31 - MySQL Community Server - GPL
-- Server OS:                    Win64
-- HeidiSQL Version:             12.12.0.7122
-- --------------------------------------------------------

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8 */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;


-- Dumping database structure for linkdeen_bot
CREATE DATABASE IF NOT EXISTS `linkdeen_bot` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;
USE `linkdeen_bot`;

-- Dumping structure for table linkdeen_bot.hashtags_queue
CREATE TABLE IF NOT EXISTS `hashtags_queue` (
  `id` int NOT NULL AUTO_INCREMENT,
  `hashtag` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `max_posts` int DEFAULT '5',
  `max_comments` int DEFAULT '5',
  `user_id` int DEFAULT NULL,
  `status` enum('pending','processing','completed','failed') COLLATE utf8mb4_unicode_ci DEFAULT 'pending',
  `error_message` text COLLATE utf8mb4_unicode_ci,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `started_at` timestamp NULL DEFAULT NULL,
  `completed_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Data exporting was unselected.

-- Dumping structure for table linkdeen_bot.linkdeen_comments
CREATE TABLE IF NOT EXISTS `linkdeen_comments` (
  `id` int NOT NULL AUTO_INCREMENT,
  `linkdeen_post_id` int DEFAULT NULL,
  `commenter` varchar(255) DEFAULT NULL,
  `comment_text` text,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `linkdeen_post_id` (`linkdeen_post_id`),
  CONSTRAINT `linkdeen_comments_ibfk_1` FOREIGN KEY (`linkdeen_post_id`) REFERENCES `linkdeen_posts` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=806 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Data exporting was unselected.

-- Dumping structure for table linkdeen_bot.linkdeen_pages
CREATE TABLE IF NOT EXISTS `linkdeen_pages` (
  `id` int NOT NULL AUTO_INCREMENT,
  `page_title` varchar(255) NOT NULL,
  `page_description` text,
  `page_overview` text,
  `last_post_content` text,
  `company_industry` varchar(255) DEFAULT NULL,
  `company_location` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `company_followers` varchar(255) DEFAULT NULL,
  `company_employees` varchar(255) DEFAULT NULL,
  `company_link` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `company_phone` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `company_value` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `page_queue_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_page_queue_id` (`page_queue_id`)
) ENGINE=InnoDB AUTO_INCREMENT=30 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Data exporting was unselected.

-- Dumping structure for table linkdeen_bot.linkdeen_posts
CREATE TABLE IF NOT EXISTS `linkdeen_posts` (
  `id` int NOT NULL AUTO_INCREMENT,
  `post_link` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci,
  `caption` text,
  `reactions` int DEFAULT '0',
  `comments` int DEFAULT '0',
  `username` varchar(255) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `hashtag_id` int DEFAULT NULL,
  `analyzed` tinyint(1) DEFAULT '0',
  `analysis_status` enum('pending','processing','completed','failed') DEFAULT 'pending',
  `analysis_error` text,
  PRIMARY KEY (`id`),
  KEY `idx_analyzed` (`analyzed`),
  KEY `idx_analysis_status` (`analysis_status`),
  KEY `idx_hashtag_id` (`hashtag_id`)
) ENGINE=InnoDB AUTO_INCREMENT=351 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Data exporting was unselected.

-- Dumping structure for table linkdeen_bot.pages
CREATE TABLE IF NOT EXISTS `pages` (
  `username` varchar(50) NOT NULL,
  `user_id` int NOT NULL,
  PRIMARY KEY (`username`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `pages_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Data exporting was unselected.

-- Dumping structure for table linkdeen_bot.pages_queue
CREATE TABLE IF NOT EXISTS `pages_queue` (
  `id` int NOT NULL AUTO_INCREMENT,
  `page_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `user_id` int DEFAULT NULL,
  `status` enum('pending','processing','completed','failed') COLLATE utf8mb4_unicode_ci DEFAULT 'pending',
  `error_message` text COLLATE utf8mb4_unicode_ci,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `started_at` timestamp NULL DEFAULT NULL,
  `completed_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_page_name` (`page_name`)
) ENGINE=InnoDB AUTO_INCREMENT=20 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Data exporting was unselected.

-- Dumping structure for table linkdeen_bot.users
CREATE TABLE IF NOT EXISTS `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `phone_number` varchar(20) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Data exporting was unselected.

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
