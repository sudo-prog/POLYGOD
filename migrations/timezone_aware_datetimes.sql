-- Migrate datetime columns to timezone-aware (TIMESTAMPTZ)
-- This fixes: "timezone-aware vs naive datetime error during price history insert"

-- Markets table
ALTER TABLE markets
  ALTER COLUMN end_date TYPE TIMESTAMP WITH TIME ZONE USING end_date AT TIME ZONE 'UTC',
  ALTER COLUMN last_updated TYPE TIMESTAMP WITH TIME ZONE USING last_updated AT TIME ZONE 'UTC',
  ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE USING created_at AT TIME ZONE 'UTC';

-- Price history table
ALTER TABLE price_history
  ALTER COLUMN timestamp TYPE TIMESTAMP WITH TIME ZONE USING timestamp AT TIME ZONE 'UTC';

-- News articles table
ALTER TABLE news_articles
  ALTER COLUMN published_at TYPE TIMESTAMP WITH TIME ZONE USING published_at AT TIME ZONE 'UTC',
  ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE USING created_at AT TIME ZONE 'UTC';

-- App state table
ALTER TABLE app_state
  ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE USING updated_at AT TIME ZONE 'UTC';

-- Trades table
ALTER TABLE trades
  ALTER COLUMN timestamp TYPE TIMESTAMP WITH TIME ZONE USING timestamp AT TIME ZONE 'UTC';

-- Note: The USING clause interprets existing naive timestamps as UTC and converts them
-- to timezone-aware timestamps with UTC timezone. This is safe for data that was
-- already stored as UTC (which it should have been).
