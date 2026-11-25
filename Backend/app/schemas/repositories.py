from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class GitHubImportRequest(BaseModel):
    url: HttpUrl


class ImportAccepted(BaseModel):
    repository_id: str
    job_id: str
    status: str
    message: str


class JobResponse(BaseModel):
    id: str
    repository_id: str
    status: str
    progress: int
    stage: str
    error_message: str | None = None
    files_discovered: int = 0
    files_processed: int = 0
    files_skipped: int = 0
    skip_reasons: dict[str, int] = Field(default_factory=dict)
    created_at: Any = None
    started_at: Any = None
    finished_at: Any = None
    model_config = ConfigDict(from_attributes=True)


class RepositorySummary(BaseModel):
    id: str
    name: str
    source_url: str | None
    source_type: str
    status: str
    progress: int
    stats: dict = Field(default_factory=dict)
    created_at: str


class RepositoryFileResponse(BaseModel):
    id: str
    path: str
    size: int
    language: str | None
    analysis: dict[str, Any] | None
    is_entry_point: bool


class GraphNodeResponse(BaseModel):
    id: str
    label: str
    directory: str
    language: str | None
    in_degree: int
    out_degree: int


class GraphEdgeResponse(BaseModel):
    source: str
    target: str
    import_name: str
    line: int
    verified: bool


class GraphResponse(BaseModel):
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]


class AnalysisReportResponse(BaseModel):
    summary: str
    metrics: dict[str, Any]
    findings: list[dict[str, Any]]


class RepositoryDetailResponse(RepositorySummary):
    metadata: dict[str, Any]
    files: list[RepositoryFileResponse]
    analysis: dict[str, dict[str, Any]]
    graph: GraphResponse
    report: AnalysisReportResponse | None


class SaveGraphRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    graph_data: dict

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Graph name cannot be blank")
        return value


class WorkerInfoResponse(BaseModel):
    name: str
    hostname: str
    pid: int
    state: str
    queues: list[str]
    version: str | None = None
    last_heartbeat: str | None = None
    registration_ttl_seconds: int


class WorkerStatusResponse(BaseModel):
    queue: str
    available: bool
    worker_count: int
    workers: list[WorkerInfoResponse]
    reason: str | None = None
