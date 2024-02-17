from temporalio import workflow
from datetime import timedelta
from utils.temporal.dataobject import Config

with workflow.unsafe.imports_passed_through():
    from utils.temporal.activity import proact_scan_activity


@workflow.defn(name="ProactWorkflow", sandboxed=False)
class ProactWorkflow:
    @workflow.run
    async def run(self, config: Config) -> str:
        return await workflow.execute_activity(
            proact_scan_activity,
            config,
            start_to_close_timeout=timedelta(seconds=60)
        )
