-- packages with findings with finding count by severity 
--SELECT 
--    d.name AS datasource_name,
--    COUNT(DISTINCT p.id) AS packages_with_findings_count,
--    fd.severity,
--    COUNT(pf.finding_id) AS finding_count
--FROM public.datasource d
--JOIN public.package p ON p.id = ANY(d.package_indexes)
--JOIN public.package_finding pf ON p.id = pf.package_id
--JOIN public.finding f ON pf.finding_id = f.id
--JOIN public.finding_data fd ON f.id = fd.finding_id
--GROUP BY d.name, d.purl, fd.severity
--ORDER BY d.name, fd.severity;


-- packages with findings by datasource
--SELECT 
--    d.name AS datasource_name,
--    COUNT(DISTINCT p.id) AS total_packages_with_findings
--FROM public.datasource d
--JOIN public.package p ON p.id = ANY(d.package_indexes)
--JOIN public.package_finding pf ON p.id = pf.package_id
--GROUP BY d.name, d.purl
--ORDER BY total_packages_with_findings DESC;


-- how many packages have findings that are in package families with more than one member
--WITH package_families AS (
--    SELECT 
--        COALESCE(namespace, '') || '/' || name AS family_key,
--        COUNT(*) AS family_size
--    FROM public.package
--    GROUP BY COALESCE(namespace, '') || '/' || name
--    HAVING COUNT(*) > 1
--),
--packages_in_multi_member_families AS (
--    SELECT p.id
--    FROM public.package p
--    JOIN package_families pf ON (COALESCE(p.namespace, '') || '/' || p.name) = pf.family_key
--)
--SELECT COUNT(DISTINCT pf.finding_id) AS findings_in_multi_member_families
--FROM public.package_finding pf
--JOIN packages_in_multi_member_families pmf ON pf.package_id = pmf.id;



-- how many findings are in multi-member families where another member of the family is patched 
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



-- how many findings are in multi-member families where another member of the family is patched with best-guess check to see if other memeber is uplevel or not 
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
--existing_family_findings AS (
--    SELECT 
--        pmf.family_key,
--        pf.finding_id,
--        array_agg(DISTINCT pmf.version ORDER BY pmf.version) FILTER (WHERE pf.package_id IS NOT NULL) AS vulnerable_versions,
--        array_agg(DISTINCT other_pmf.version ORDER BY other_pmf.version) AS safe_versions
--    FROM packages_in_multi_member_families pmf
--    JOIN public.package_finding pf ON pmf.id = pf.package_id
--    JOIN packages_in_multi_member_families other_pmf ON pmf.family_key = other_pmf.family_key
--    LEFT JOIN public.package_finding other_pf ON other_pmf.id = other_pf.package_id AND other_pf.finding_id = pf.finding_id
--    WHERE other_pf.package_id IS NULL  -- other family member doesn't have this finding
--    GROUP BY pmf.family_key, pf.finding_id
--),
--findings_with_likely_newer_patches AS (
--    SELECT DISTINCT finding_id
--    FROM existing_family_findings
--    WHERE array_length(safe_versions, 1) > 0
--      AND safe_versions[array_length(safe_versions, 1)] > vulnerable_versions[array_length(vulnerable_versions, 1)]
--)
--SELECT 
--    COUNT(DISTINCT pf.finding_id) AS findings_in_multi_member_families,
--    COUNT(DISTINCT CASE WHEN fwlnp.finding_id IS NOT NULL THEN pf.finding_id END) AS findings_with_likely_newer_patches
--FROM public.package_finding pf
--JOIN packages_in_multi_member_families pmf ON pf.package_id = pmf.id
--LEFT JOIN findings_with_likely_newer_patches fwlnp ON pf.finding_id = fwlnp.finding_id;






-- how many findings are in datasources that have not been updated in [n] months? 
--WITH latest_commits AS (
--    SELECT 
--        de.datasource_id,
--        MAX(de.commit_date_time) AS latest_commit_date
--    FROM public.datasource_event de
--    WHERE de.commit_date_time IS NOT NULL
--    GROUP BY de.datasource_id
--)
--SELECT COUNT(DISTINCT pf.finding_id) AS findings_in_recent_datasources
--FROM public.datasource d
--JOIN latest_commits lc ON d.id = lc.datasource_id
--JOIN public.package p ON p.id = ANY(d.package_indexes)
--JOIN public.package_finding pf ON p.id = pf.package_id
--WHERE lc.latest_commit_date >= NOW() - INTERVAL '12 month';

