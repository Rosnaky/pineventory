-- database/migrations/002_add_subteam_enum.sql

-- Create the enum type
CREATE TYPE subteam_type AS ENUM ('mechanical', 'electrical', 'efs', 'autonomy', 'operations');

-- Alter the items table to use the enum
ALTER TABLE items 
ALTER COLUMN subteam TYPE subteam_type USING subteam::subteam_type;
