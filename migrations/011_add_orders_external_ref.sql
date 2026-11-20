-- Safe nullable metadata-only column addition; exercises unwaived Squawk + lint gates.
ALTER TABLE orders ADD COLUMN external_ref text;
