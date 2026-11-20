from typing import Annotated

from fastapi import Depends, Request

from app.core.database import Session
from app.services.workspace import WorkspaceService


def get_workspace_service(session: Session, request: Request) -> WorkspaceService:
    return WorkspaceService(session, request.app.state.task_cache)


WorkspaceServiceDep = Annotated[WorkspaceService, Depends(get_workspace_service)]
