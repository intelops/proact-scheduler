import uvicorn
from fastapi import FastAPI
from utils.database import Base,engine
import os
from routes.schedule import schedule
from temporalio import workflow
import asyncio
from utils.constants import TEMPORAL_HOST, SERVER_PORT

from temporalio.client import Client
from temporalio.worker import Worker

with workflow.unsafe.imports_passed_through():
    from utils.temporal.activity import proact_scan_activity
    from utils.temporal.workflow_dax import ProactWorkflow


app = FastAPI(
    title="Proact Server",
    version="0.0.1"
)

app.include_router(schedule.router)

Base.metadata.create_all(bind=engine)


# TODO: Need to update this probes later
@app.get("/ready", include_in_schema=False)
async def readinessProbe():
    return {"status": "ok"}


@app.get("/healthz", include_in_schema=False)
async def livenessProbe():
    # check if postgres
    return {"status": "ok"}



async def main():
    print(f"Connecting to Temporal at {TEMPORAL_HOST}")
    client = await Client.connect(TEMPORAL_HOST)

    #Create a worker
    worker = Worker(
        client,
        task_queue="proact-task-queue",
        workflows=[ProactWorkflow],
        activities=[proact_scan_activity],
    )
    await worker.run()

    
if __name__ == "__main__":
    # #check environment and run uvicorn accordingly
    try:
        loop = asyncio.get_event_loop()
        asyncio.set_event_loop(loop)
        loop.create_task(main())
        if os.getenv("PROACT_ENVIRONMENT","dev") == "prod":
            config = uvicorn.Config("app:app", loop=loop,host="0.0.0.0",port=int(SERVER_PORT), log_level="debug", workers=1)
        else:
            config = uvicorn.Config("app:app", loop=loop,host="0.0.0.0",port=int(SERVER_PORT), log_level="debug", reload=True)
        server = uvicorn.Server(config)
        loop.run_until_complete(server.serve())
    except Exception as e:
        print("Error in main", e)
        loop.close()

