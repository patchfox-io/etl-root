update datasource_event dse set status = 'PROCESSED' where dse.status = 'READY_FOR_NEXT_PROCESSING';

update datasource_event dse set job_id = 'd2c6c2f4-af25-4fdd-886f-79762847ffff' WHERE dse.status = 'PROCESSING_ERROR';

SELECT get_n_months_of_dse_history(6, true);

update datasource_event dse 
	set oss_enriched = true, package_index_enriched = true, analyzed = false
	where job_id = 'd2c6c2f4-af25-4fdd-886f-79762847ffff';

update dataset de set latest_job_id = 'd2c6c2f4-af25-4fdd-886f-79762847ffff', status = 'PROCESSING' where de.id = 1
