CREATE OR REPLACE FUNCTION get_n_months_of_dse_history(n int, one_per_day boolean DEFAULT false)
RETURNS bigint[] AS $$
DECLARE
  n_months_ago timestamptz;
  ds_ids bigint[];
  dse_ids bigint[] := '{}'; -- Initialize as empty array
  temp_ids bigint[];        -- Temporary array for each iteration
BEGIN
  SELECT NOW() - (n || ' MONTHS')::INTERVAL INTO n_months_ago;
  
  SELECT array_agg(ds.id) FROM datasource ds INTO ds_ids;
  
  FOR i IN 1..array_length(ds_ids, 1) LOOP
    IF one_per_day THEN
      -- Get last event per day for current datasource
      WITH daily_events AS (
        SELECT 
          dse.id,
          dse.datasource_id,
          dse.commit_date_time,
          DATE(dse.commit_date_time) AS event_date,
          ROW_NUMBER() OVER (
            PARTITION BY DATE(dse.commit_date_time) 
            ORDER BY dse.commit_date_time DESC
          ) AS rn
        FROM datasource_event dse
        WHERE dse.datasource_id = ds_ids[i]
        AND (
          dse.commit_date_time >= n_months_ago
          OR
          dse.commit_date_time = (
            SELECT MAX(dse_inner.commit_date_time)
            FROM datasource_event dse_inner
            WHERE dse_inner.datasource_id = ds_ids[i]
            AND dse_inner.commit_date_time < n_months_ago
          )
        )
      )
      SELECT array_agg(id)
      FROM daily_events
      WHERE rn = 1 -- Only select the last event of each day
      INTO temp_ids;
    ELSE
      -- Get all events for current datasource (original behavior)
      SELECT array_agg(dse.id)
      FROM datasource_event dse
      INNER JOIN datasource ds
      ON ds.id = dse.datasource_id
      WHERE
        ds.id = ds_ids[i]
        AND
        (
          dse.commit_date_time >= n_months_ago
          OR
          dse.id = (
            SELECT dse_inner.id
            FROM datasource_event dse_inner
            WHERE dse_inner.datasource_id = ds.id
            AND NOT EXISTS (
              SELECT 1
              FROM datasource_event newer
              WHERE newer.datasource_id = ds.id
              AND newer.commit_date_time >= n_months_ago
            )
            ORDER BY dse_inner.commit_date_time DESC
            LIMIT 1
          )
        )
      INTO temp_ids;
    END IF;
    
    -- Append the results to our main array
    IF temp_ids IS NOT NULL THEN
      dse_ids := dse_ids || temp_ids;
    END IF;
  END LOOP;
  
  RETURN dse_ids;
END;
$$ LANGUAGE PLPGSQL;

-- Example calls:
-- Get all events (original behavior)
-- SELECT get_n_months_of_dse_history(12, false);

-- OR simply:
-- SELECT get_n_months_of_dse_history(12);

-- Get only one event per day (new behavior)
-- SELECT get_n_months_of_dse_history(12, true);


