-- HelpChain Database Initialization Script
-- This script runs when the PostgreSQL container starts for the first time

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create indexes for better performance
-- These will be created by Alembic migrations, but we can add them here as well

-- Note: The actual table creation is handled by Flask-Migrate/Alembic
-- This file is mainly for any additional database setup
