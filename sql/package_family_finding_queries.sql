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



--update datasource_event dse set status = 'PROCESSED' where dse.status = 'READY_FOR_PROCESSING';
--
--update datasource_event dse set job_id = 'd2c6c2f4-af25-4fdd-886f-79762847ffff' WHERE dse.status = 'PROCESSING_ERROR';
--
--SELECT get_n_months_of_dse_history(3, true);
--
--update datasource_event dse 
--	set oss_enriched = false, package_index_enriched = false, analyzed = false
--	where job_id = 'd2c6c2f4-af25-4fdd-886f-79762847ffff';
--
--update dataset de set latest_job_id = 'd2c6c2f4-af25-4fdd-886f-79762847ffff', status = 'READY_FOR_PROCESSING' where de.id = 1



--select count(*), dse.package_index_enriched, dse.oss_enriched, dse.analyzed from datasource_event dse group by dse.package_index_enriched, dse.oss_enriched, dse.analyzed;
--update datasource_event dse set package_index_enriched=TRUE where dse.oss_enriched=TRUE;



-- how many finding types are in multi-member families where another member of the family is patched
--WITH package_families AS (
--    SELECT
--        COALESCE(namespace, '') || '/' || name AS family_key,
--        COUNT(*) AS family_size
--    FROM public.package
--    GROUP BY COALESCE(namespace, '') || '/' || name
--    HAVING COUNT(*) > 1
--),
--packages_in_multi_member_families AS (
--    SELECT p.id, p.name, p.namespace, p.version,
--           COALESCE(p.namespace, '') || '/' || p.name AS family_key
--    FROM public.package p
--    JOIN package_families pf ON (COALESCE(p.namespace, '') || '/' || p.name) = pf.family_key
--),
---- Only look at actual finding-family combinations that exist
--existing_family_findings AS (
--    SELECT
--        pmf.family_key,
--        pf.finding_id,
--        COUNT(DISTINCT pmf.id) AS total_family_members,
--        COUNT(DISTINCT pf.package_id) AS members_with_finding
--    FROM packages_in_multi_member_families pmf
--    JOIN public.package_finding pf ON pmf.id = pf.package_id
--    GROUP BY pmf.family_key, pf.finding_id
--),
--findings_with_patched_versions AS (
--    SELECT DISTINCT eff.finding_id
--    FROM existing_family_findings eff
--    JOIN package_families pf ON eff.family_key = pf.family_key
--    WHERE eff.members_with_finding < pf.family_size
--)
--SELECT
--    COUNT(DISTINCT pf.finding_id) AS findings_in_multi_member_families,
--    COUNT(DISTINCT CASE WHEN fpv.finding_id IS NOT NULL THEN pf.finding_id END) AS findings_with_patched_versions_in_family
--FROM public.package_finding pf
--JOIN packages_in_multi_member_families pmf ON pf.package_id = pmf.id
--LEFT JOIN findings_with_patched_versions fpv ON pf.finding_id = fpv.finding_id;




-- how many finding instances are in multi-member families where another member of the family is patched
--WITH package_families AS (
--    SELECT
--        COALESCE(namespace, '') || '/' || name AS family_key,
--        COUNT(*) AS family_size
--    FROM public.package
--    GROUP BY COALESCE(namespace, '') || '/' || name
--    HAVING COUNT(*) > 1
--),
--packages_in_multi_member_families AS (
--    SELECT p.id, p.name, p.namespace, p.version,
--           COALESCE(p.namespace, '') || '/' || p.name AS family_key
--    FROM public.package p
--    JOIN package_families pf ON (COALESCE(p.namespace, '') || '/' || p.name) = pf.family_key
--),
---- Identify which unique findings have at least one patched version in their family
--findings_with_patched_versions AS (
--    SELECT DISTINCT pf.finding_id, pmf.family_key
--    FROM public.package_finding pf
--    JOIN packages_in_multi_member_families pmf ON pf.package_id = pmf.id
--    JOIN package_families fam ON pmf.family_key = fam.family_key
--    GROUP BY pf.finding_id, pmf.family_key, fam.family_size
--    -- A finding is "patchable" if the number of packages affected is less than the total family size
--    HAVING COUNT(DISTINCT pf.package_id) < fam.family_size
--)
--SELECT
--    -- Removed DISTINCT to count every instance (package-finding pair)
--    COUNT(pf.finding_id) AS total_finding_instances_in_families,
--    COUNT(fpv.finding_id) AS instances_with_patched_versions_in_family
--FROM public.package_finding pf
--JOIN packages_in_multi_member_families pmf ON pf.package_id = pmf.id
--LEFT JOIN findings_with_patched_versions fpv 
--    ON pf.finding_id = fpv.finding_id 
--    AND pmf.family_key = fpv.family_key;


---- 1. Grab the single most recent record from dataset_metrics
--WITH the_latest_metric AS (
--    SELECT package_indexes
--    FROM public.dataset_metrics
--    ORDER BY commit_date_time DESC
--    LIMIT 1
--),
---- 2. Get the packages that are listed in that record's index array
--latest_packages AS (
--    SELECT p.id, p.name, p.namespace, p.version,
--           COALESCE(p.namespace, '') || '/' || p.name AS family_key
--    FROM public.package p, the_latest_metric m
--    WHERE p.id = ANY(m.package_indexes)  -- Join based on the array contents
--),
---- 3. Figure out which of those packages have "family members" in the same list
--package_families AS (
--    SELECT family_key, COUNT(*) AS family_size
--    FROM latest_packages
--    GROUP BY family_key
--    HAVING COUNT(*) > 1
--),
--packages_in_multi_member_families AS (
--    SELECT lp.*
--    FROM latest_packages lp
--    JOIN package_families pf ON lp.family_key = pf.family_key
--),
---- 4. Find which findings have a "patched" version available in this snapshot
--findings_with_patched_versions AS (
--    SELECT pf.finding_id, pmf.family_key
--    FROM public.package_finding pf
--    JOIN packages_in_multi_member_families pmf ON pf.package_id = pmf.id
--    JOIN package_families fam ON pmf.family_key = fam.family_key
--    GROUP BY pf.finding_id, pmf.family_key, fam.family_size
--    HAVING COUNT(DISTINCT pf.package_id) < fam.family_size
--)
---- 5. Count the total instances
--SELECT
--    COUNT(pf.finding_id) AS total_finding_instances_in_families,
--    COUNT(fpv.finding_id) AS instances_with_patched_versions_in_family
--FROM public.package_finding pf
--JOIN packages_in_multi_member_families pmf ON pf.package_id = pmf.id
--LEFT JOIN findings_with_patched_versions fpv 
--    ON pf.finding_id = fpv.finding_id 
--    AND pmf.family_key = fpv.family_key;





-- 1. Setup the same dataset and family logic as the main query
--WITH the_latest_metric AS (
--    SELECT package_indexes
--    FROM public.dataset_metrics
--    ORDER BY commit_date_time DESC
--    LIMIT 1
--),
--latest_packages AS (
--    SELECT p.id, p.name, p.namespace,
--           COALESCE(p.namespace, '') || '/' || p.name AS family_key
--    FROM public.package p
--    INNER JOIN the_latest_metric m ON p.id = ANY(m.package_indexes)
--),
--package_families AS (
--    SELECT family_key, COUNT(*) AS family_size
--    FROM latest_packages
--    GROUP BY family_key
--    HAVING COUNT(*) > 1
--),
--packages_in_multi_member_families AS (
--    SELECT lp.*
--    FROM latest_packages lp
--    JOIN package_families pf ON lp.family_key = pf.family_key
--)
---- 2. Run the actual sanity check using the defined CTEs
--SELECT 
--    pmf.family_key, 
--    COUNT(pf.finding_id) AS total_finding_instances
--FROM packages_in_multi_member_families pmf
--JOIN public.package_finding pf ON pmf.id = pf.package_id
--GROUP BY pmf.family_key
--ORDER BY total_finding_instances DESC
--LIMIT 10;



-- 1. Setup the same dataset and family logic
--WITH the_latest_metric AS (
--    SELECT package_indexes
--    FROM public.dataset_metrics
--    ORDER BY commit_date_time DESC
--    LIMIT 1
--),
--latest_packages AS (
--    SELECT p.id, p.name, p.namespace,
--           COALESCE(p.namespace, '') || '/' || p.name AS family_key
--    FROM public.package p
--    INNER JOIN the_latest_metric m ON p.id = ANY(m.package_indexes)
--),
--package_families AS (
--    SELECT family_key, COUNT(*) AS family_size
--    FROM latest_packages
--    GROUP BY family_key
--    HAVING COUNT(*) > 1
--),
--packages_in_multi_member_families AS (
--    SELECT lp.*, pf.family_size
--    FROM latest_packages lp
--    JOIN package_families pf ON lp.family_key = pf.family_key
--),
---- 2. Identify which specific package IDs in this dataset have at least one finding
--packages_with_any_findings AS (
--    SELECT DISTINCT package_id
--    FROM public.package_finding
--    WHERE package_id IN (SELECT id FROM packages_in_multi_member_families)
--)
---- 3. Aggregate metrics by family
--SELECT 
--    pmf.family_key, 
--    -- Total count of all finding-to-package links (what you had before)
--    COUNT(pf.finding_id) AS total_finding_instances,
--    -- The total number of versions of this package in the dataset
--    MAX(pmf.family_size) AS total_family_members,
--    -- Count distinct package IDs in this family that appear in the finding table
--    COUNT(DISTINCT paf.package_id) AS family_members_with_findings,
--    -- Total members minus those with findings = those without findings
--    (MAX(pmf.family_size) - COUNT(DISTINCT paf.package_id)) AS family_members_without_findings
--FROM packages_in_multi_member_families pmf
--LEFT JOIN public.package_finding pf ON pmf.id = pf.package_id
--LEFT JOIN packages_with_any_findings paf ON pmf.id = paf.package_id
--GROUP BY pmf.family_key
--ORDER BY total_finding_instances DESC
--LIMIT 10;
