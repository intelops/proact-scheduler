from fastapi import APIRouter, Depends
from fastapi import Request
from utils.database import get_db
from utils.model import CreateScheduleConfig, CreateDeleteUpdateScheduleResponse, ScheduleResponse, ScheduleDetailsResponseNew
from sqlalchemy.orm import Session
from routes.schedule.service import create_new_schedule, delete_schedule, list_schedules, get_schedule_configs, get_schedule_details, pause_schedule, resume_schedule
from datetime import datetime

router = APIRouter(prefix="/api/v1/schedule", tags=["scsctl"])


@router.post("/")
async def createSchedule(request: Request, config: CreateScheduleConfig, db: Session = Depends(get_db)) -> CreateDeleteUpdateScheduleResponse:
    """
    Create a new schedule
    """

    status, schedule_id = await create_new_schedule(config, db)
    return CreateDeleteUpdateScheduleResponse(message=status.value, schedule_id=schedule_id)

@router.delete("/{scheduleId}")
async def deleteSchedule(request: Request,scheduleId: str, db: Session = Depends(get_db)) -> CreateDeleteUpdateScheduleResponse:
    """
    Delete a schedule with the given schedule_id
    """
    status,scheduleId = await delete_schedule(scheduleId, db)
    return CreateDeleteUpdateScheduleResponse(message=status.value, schedule_id=scheduleId)

@router.get("/")
async def listSchedules(request: Request, db: Session = Depends(get_db)) -> list[ScheduleResponse]:
    """
    List all schedules
    """
    schedules = await list_schedules(db)
    return schedules
    
@router.get("/{scheduleId}", response_model_exclude_none=True)
async def getScheduleConfigs(request: Request, scheduleId: str, db: Session = Depends(get_db)) -> CreateScheduleConfig:
    """
    Get schedule configs with the given schedule_id
    """
    #Get schedule details from Schedules
    configs = await get_schedule_configs(scheduleId, db)
    return configs
    
@router.get("/{scheduleId}/details")
async def getScheduleDetails(request: Request, scheduleId: str, db: Session = Depends(get_db)) -> ScheduleDetailsResponseNew:
    """
    Get schedule details with the given schedule_id
    """

    schedule_details_response = await get_schedule_details(scheduleId, db)
    return schedule_details_response


@router.put("/{scheduleId}/pause")
async def pauseSchedule(request: Request, scheduleId: str, db: Session = Depends(get_db)) -> CreateDeleteUpdateScheduleResponse:
    """
    Pause a schedule with the given schedule_id
    """

    status, schedule_id = await pause_schedule(scheduleId, db)
    return CreateDeleteUpdateScheduleResponse(message=status.value, schedule_id=schedule_id)


@router.put("/{scheduleId}/resume")
async def resumeSchedule(request: Request, scheduleId: str, db: Session = Depends(get_db)) -> CreateDeleteUpdateScheduleResponse:
    """
    Resume a schedule with the given schedule_id
    """

    status, schedule_id = await resume_schedule(scheduleId, db)
    return CreateDeleteUpdateScheduleResponse(message=status.value, schedule_id=schedule_id)
