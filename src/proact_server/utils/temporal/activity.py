from temporalio import activity
from scsctl.helper.scan import run_scan
from utils.database import get_db
from utils.model import ScanStatus, ExecutionJobs, Executions
import json

@activity.defn(name="proact_scan_activity")
async def proact_scan_activity(config: dict) -> str:

    result = run_scan(**config)
    generator = get_db()
    db = next(generator)
    execution_id = config.get("execution_id")
    scan_report = {
        "sbom_report": json.loads(result.get("sbom_report")),
        "profiler_data": result.get("pyroscope_data"),
        "profiler_found_extra_packages": result.get("pyroscope_found_extra_packages"),
        "runtime_security_tool_found_extra_packages": result.get("falco_found_extra_packages"),
        "dependency_manager_status": result.get("renovate_status"),
        "final_report": result.get("final_report")
    }
    #Convert scan_report to json string
    scan_report = json.dumps(scan_report)

    scan = ScanStatus(
            job_id=config.get("job_id"),
            execution_id=execution_id,
            batch_id=result.get("batch_id"),
            run_type="api",
            status=result.get("scan_status"),
            scan_report=scan_report,
            rebuilded_image_name = result.get("rebuild_image_name") if result.get("rebuild_image_status", '') == 'success' else None,
            **result.get("stats")
        )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    #Get scan status for all jobs for execution_id and check if job has vulnerable_packages_count greater than 0. If yes count that. This count is the count of vulnerable_images_count in executions table.
    #get job ids for execution_id
    job_ids = db.query(ExecutionJobs.job_id).filter(ExecutionJobs.execution_id == execution_id).all()
    # Get vulnerable_packages_count for all each job_id with latest datetime
    vulnerable_images_count = 0
    vulnerabilities_count = 0
    scan_status_temp = True
    for job_id in job_ids:
        counts = db.query(ScanStatus.vulnerablitites_count,ScanStatus.status).filter(ScanStatus.job_id == job_id[0]).order_by(ScanStatus.datetime.desc()).first()
        if(counts and counts[0] > 0):
            vulnerable_images_count += 1
        if(counts):
            vulnerabilities_count += counts[0]
        if(counts and counts[1] == False):
            scan_status_temp = False

    #Update the vulnerabilities_count in executions table
    db.query(Executions).filter(Executions.execution_id == execution_id).update({"vulnerablities_count": vulnerabilities_count, "vulnerable_images_count": vulnerable_images_count, "status": scan_status_temp})

    db.commit()
    db.close()

    return "success"