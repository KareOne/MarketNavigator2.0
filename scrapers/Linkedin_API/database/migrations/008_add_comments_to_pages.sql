-- Add comments count and text fields to linkdeen_pages table
ALTER TABLE `linkdeen_pages`
ADD COLUMN `comments` INT DEFAULT 0 AFTER `company_value`,
ADD COLUMN `comments_text` TEXT DEFAULT NULL AFTER `comments`;