
from uuid import uuid4
from sqlalchemy.orm import Session
from utils.model import CreateScheduleConfig, Schedules, ScanConfigs, Executions, ExecutionJobs, ScanStatus, ScheduleResponse, ScanConfig
from utils.model import ScheduleEnum, ScheduleDetailsResponse, ExecutionResponseNew, ScheduleDetailsResponseNew, CreateScheduleConfigResponse
from temporalio.client import Client,Schedule, ScheduleActionStartWorkflow, ScheduleSpec,ScheduleState
from temporalio import workflow
import json

from utils.constants import TEMPORAL_HOST

with workflow.unsafe.imports_passed_through():
    from utils.temporal.workflow_dax import ProactWorkflow


async def create_new_schedule(config: CreateScheduleConfig, db: Session, schedule_id: str = None) -> tuple[ScheduleEnum, str]:
    #TODO: Make the db commits atomic, if any of the db commit fails then rollback all the db commits
    try:

        container_registry_url = config.container_registry_url
        schedules = config.model_dump()        
        scan_configs = schedules.pop("scan_configs")
        schedules.pop("container_registry_url")

        updated_scan_configs = []

        #Update docker_image_name by appending container_registry_url. Also ensure docker_image_name and  container_registry_url dont have any trailing or leading slashes
        if(container_registry_url[-1] == "/"):
            container_registry_url = container_registry_url[:-1]
        if(container_registry_url[0] == '/'):
            container_registry_url = container_registry_url[1:]
        for scan_config in scan_configs:
            if(scan_config['docker_image_name'][-1] == "/"):
                scan_config['docker_image_name'] = scan_config['docker_image_name'][:-1]
            if(scan_config['docker_image_name'][0] == '/'):
                scan_config['docker_image_name'] = scan_config['docker_image_name'][1:]
            scan_config['docker_image_name'] = container_registry_url + "/" + scan_config['docker_image_name']
            updated_scan_configs.append(scan_config)

        #During update schedule_id will be passed to keep the schedule id same even if we are creating a new schedule
        if(schedule_id):
            schedules["schedule_id"] = schedule_id

        #Create a schedule
        new_schedule = Schedules(**schedules)
        db.add(new_schedule)
        db.commit()
        db.refresh(new_schedule)
        #Get the schedule id
        schedule_id = new_schedule.schedule_id

        #Create executions
        new_execution = Executions(schedule_id=schedule_id, scan_images_count=len(updated_scan_configs))
        db.add(new_execution)
        db.commit()
        db.refresh(new_execution)
        execution_id = new_execution.execution_id

        #Add scan configs
        for scan_config in updated_scan_configs:
            job_id = str(uuid4())
            scan_config["schedule_id"] = schedule_id
            scan_config["job_id"] = job_id
            scan_config["schedule_status"] = "running"
            db.add(ScanConfigs(**scan_config))
            # db.commit()

            scan_config_without_none = {k: v for k, v in scan_config.items() if v is not None}

            # Add job to scheduler
            kwargs = {
                "job_id": job_id,
                "is_api": True,
                "execution_id": execution_id,
                **scan_config_without_none
            }

            #Create schedule in temporal
            client = await Client.connect(TEMPORAL_HOST)
            await client.create_schedule(
                job_id,
                Schedule(
                    action=ScheduleActionStartWorkflow(
                        ProactWorkflow,
                        kwargs,
                        id=str(uuid4()),
                        task_queue="proact-task-queue",
                    ),
                    spec=ScheduleSpec(
                        cron_expressions=[config.cron_schedule],
                    ),
                    state=ScheduleState(note="Proact Schedule Created"),
                )
            )


            #Add job to execution_jobs
            db.add(ExecutionJobs(execution_id=execution_id, job_id=job_id))
        db.commit()
        return ScheduleEnum.SCHEDULE_CREATED, schedule_id
    except Exception as e:
        print(e)
        return ScheduleEnum.SCHEDULE_CREATION_FAILED, schedule_id
    
async def delete_schedule(schedule_id: str, db: Session) -> tuple[ScheduleEnum, str]:
    try:
        #Get execution_id
        #Check if schedule exists if not return error
        if(not db.query(Schedules).filter(Schedules.schedule_id == schedule_id).first()):
            return ScheduleEnum.SCHEDULE_NOT_FOUND, schedule_id
        execution_id = db.query(Executions).filter(Executions.schedule_id == schedule_id).first().execution_id
        execution_jobs = db.query(ExecutionJobs).filter(ExecutionJobs.execution_id == execution_id).all()
        job_ids = [job.job_id for job in execution_jobs]

        #Delete schedule from temporal
        client = await Client.connect(TEMPORAL_HOST)
        for job_id in job_ids:
            handle = client.get_schedule_handle(str(job_id))
            await handle.delete()
        db.query(ExecutionJobs).filter(ExecutionJobs.execution_id == execution_id).delete()

        #Delete scan configs
        db.query(ScanConfigs).filter(ScanConfigs.schedule_id == schedule_id).delete()


        #Delete scan status
        db.query(ScanStatus).filter(ScanStatus.execution_id == execution_id).delete()

        #Delete execution
        db.query(Executions).filter(Executions.schedule_id == schedule_id).delete()

        #Delete schedule
        db.query(Schedules).filter(Schedules.schedule_id == schedule_id).delete()
        db.commit()

        return ScheduleEnum.SCHEDULE_DELETED, schedule_id
    except Exception as e:
        print(e)
        return ScheduleEnum.SCHEDULE_DELETE_FAILED, schedule_id
    
async def list_schedules(db: Session) -> list[ScheduleResponse]:
    #Get schedule name and schedule id from Schedules
    schedules = db.query(Schedules.schedule_name, Schedules.schedule_id).all()

    if(schedules == None):
        return []
    else:
        #Get schedule_status from ScanConfigs
        updated_schedules = []
        for schedule in schedules:
            schedule_status = db.query(ScanConfigs.schedule_status).filter(ScanConfigs.schedule_id == schedule.schedule_id).first()
            if(schedule_status):
                schedule_status = schedule_status[0]
                schedule = schedule._asdict()
                schedule["schedule_status"] = schedule_status
                updated_schedules.append(schedule)
        #Convert to list of ScheduleResponse using ** expression
        schedules = [ScheduleResponse(**schedule) for schedule in updated_schedules]
        return schedules
    
async def get_schedule_configs(scheduleId: str, db: Session) -> CreateScheduleConfigResponse:
    """
    Get schedule details with the given schedule_id
    """
    #Get schedule details from Schedules
    try:
        schedule = db.query(Schedules.schedule_id,Schedules.schedule_name,Schedules.start_date,Schedules.end_date, Schedules.container_registry_id,Schedules.cron_schedule,Schedules.update_time).filter(Schedules.schedule_id == scheduleId).first()._asdict()

        #Get scan configs
        scan_configs = db.query(ScanConfigs.docker_image_name,ScanConfigs.pyroscope_url,ScanConfigs.pyroscope_app_name,ScanConfigs.falco_pod_name,ScanConfigs.falco_target_deployment_name, ScanConfigs.docker_file_folder_path, ScanConfigs.db_enabled, ScanConfigs.falco_enabled, ScanConfigs.renovate_enabled, ScanConfigs.renovate_repo_name, ScanConfigs.renovate_repo_token,ScanConfigs.dgraph_enabled, ScanConfigs.dgraph_db_host, ScanConfigs.dgraph_db_port, ScanConfigs.schedule_status, ScanConfigs.rebuild_image, ScanConfigs.pyroscope_enabled).filter(ScanConfigs.schedule_id == scheduleId).all()
        scan_configs = [ScanConfig(**scan_config._asdict()) for scan_config in scan_configs]
        schedule["scan_configs"] = scan_configs

        schedule_details = CreateScheduleConfigResponse(**schedule)
        return schedule_details.model_dump()
    except Exception as e:
        print(e)
        return CreateScheduleConfigResponse(schedule_name="/NA", container_registry_id="/NA", cron_schedule="/NA", scan_configs=[])
    
async def get_schedule_details(scheduleId: str, db: Session):
    #Get execution details from Executions
    try:
        # Get schedule name from Schedules
        sschedule_name = db.query(Schedules.schedule_name).filter(Schedules.schedule_id == scheduleId).first()
        schedule_name = sschedule_name.schedule_name
        execution = db.query(Executions).filter(Executions.schedule_id == scheduleId).first()
        execution_id = execution.execution_id
        #Get job ids from ExecutionJobs
        job_ids = db.query(ExecutionJobs.job_id).filter(ExecutionJobs.execution_id == execution_id).all()
        job_ids = [job_id.job_id for job_id in job_ids]

        execution_details = []
        for job_id in job_ids:
            #Get only latest scan status for each job_id based on the datetime field
            scan_status = db.query(ScanStatus.execution_id, ScanStatus.job_id, ScanStatus.vulnerable_packages_count, ScanStatus.vulnerablitites_count, ScanStatus.severity_critical_count, ScanStatus.severity_high_count, ScanStatus.severity_low_count, ScanStatus.severity_medium_count, ScanStatus.severity_unknown_count, ScanStatus.datetime, ScanStatus.scan_report, ScanStatus.rebuilded_image_name).filter(ScanStatus.job_id == job_id).order_by(ScanStatus.datetime.desc()).first()
            if(scan_status):
                #convert to dictionary
                scan_status_dict = scan_status._asdict()
                scan_status_dict["execution_id"] = str(scan_status_dict["execution_id"])
                scan_status_dict["job_id"] = str(scan_status_dict["job_id"])
                scan_status_dict["scan_report"] = json.loads(scan_status_dict["scan_report"])
                scan_status_dict["rebuilded_image_name"] = scan_status_dict["rebuilded_image_name"] if scan_status_dict["rebuilded_image_name"] else ""
                execution_details.append(ExecutionResponseNew(**scan_status_dict))
        return ScheduleDetailsResponseNew(schedule_id=scheduleId, schedule_name=schedule_name,total_scan_images_count=execution.scan_images_count, total_vulnerable_images_count= execution.vulnerable_images_count, total_vulnerablities_count=execution.vulnerablities_count, executions=execution_details)
    except Exception as e:
        print(e)
        return ScheduleDetailsResponseNew(schedule_id="", schedule_name="",total_scan_images_count=0, total_vulnerable_images_count= 0, total_vulnerablities_count=0, executions=[])
    
async def pause_schedule(scheduleId: str, db: Session) -> tuple[ScheduleEnum, str]:
    try:
        #Get execution_id
        execution_id = db.query(Executions).filter(Executions.schedule_id == scheduleId).first().execution_id
        execution_jobs = db.query(ExecutionJobs).filter(ExecutionJobs.execution_id == execution_id).all()
        job_ids = [job.job_id for job in execution_jobs]


        #Pause schedule from temporal
        client = await Client.connect(TEMPORAL_HOST)
        for job_id in job_ids:
            handle = client.get_schedule_handle(str(job_id))
            await handle.pause()
        #Update schedule status in ScanConfigs
        db.query(ScanConfigs).filter(ScanConfigs.schedule_id == scheduleId).update({"schedule_status": "paused"})
        db.commit()
        return ScheduleEnum.SCHEDULE_PAUSED, scheduleId
    except Exception as e:
        print(e)
        return ScheduleEnum.SCHEDULE_PAUSE_FAILED, scheduleId
    
async def resume_schedule(scheduleId: str, db: Session) -> tuple[ScheduleEnum, str]:
    try:
        #Get execution_id
        execution_id = db.query(Executions).filter(Executions.schedule_id == scheduleId).first().execution_id
        execution_jobs = db.query(ExecutionJobs).filter(ExecutionJobs.execution_id == execution_id).all()
        job_ids = [job.job_id for job in execution_jobs]

        #Resume schedule from temporal
        client = await Client.connect(TEMPORAL_HOST)
        for job_id in job_ids:
            handle = client.get_schedule_handle(str(job_id))
            await handle.unpause()
        #Update schedule status in ScanConfigs
        db.query(ScanConfigs).filter(ScanConfigs.schedule_id == scheduleId).update({"schedule_status": "running"})
        db.commit()
        return ScheduleEnum.SCHEDULE_RESUMED, scheduleId
    except Exception as e:
        print(e)
        return ScheduleEnum.SCHEDULE_RESUME_FAILED, scheduleId