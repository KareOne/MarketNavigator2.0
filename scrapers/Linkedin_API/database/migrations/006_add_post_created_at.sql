-- Add post_created_at column to linkdeen_pages table
-- This stores when the LinkedIn post was actually created, not when we scraped it

ALTER TABLE linkdeen_pages
ADD COLUMN IF NOT EXISTS post_created_at DATETIME NULL COMMENT 'Timestamp when the LinkedIn post was actually created' AFTER last_post_content;