-- Fix company_value column size in linkdeen_pages table
-- Change from VARCHAR(50) to TEXT to handle longer values

USE `linkdeen_bot`;

ALTER TABLE `linkdeen_pages`
MODIFY COLUMN `company_value` TEXT DEFAULT NULL;