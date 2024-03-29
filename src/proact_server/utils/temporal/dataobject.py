from dataclasses import dataclass
@dataclass
class Config:
    schedule_id: str = None
    job_id: str = None
    docker_image_name: str = None
    pyroscope_enabled: bool = False
    pyroscope_url: str = None
    pyroscope_app_name: str = None
    falco_pod_name: str = None
    falco_target_deployment_name: str = None
    docker_file_folder_path: str = None
    db_enabled: bool = False
    falco_enabled: bool = False
    renovate_enabled: bool = False
    renovate_repo_name: str = None
    renovate_repo_token: str = None
    dgraph_enabled: bool = False
    dgraph_db_host: str = None
    dgraph_db_port: str = None
    is_api: bool = False
    execution_id: str = None
    rebuild_image: bool = False