"""Export of a group's expenses (FR-24, FR-25): ``?format=csv`` or ``json``."""

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.dependencies import CurrentUser, ExportServiceDep
from app.exporters.factory import UnknownExportFormatError
from app.services.group_service import GroupNotFoundError, GroupPermissionError

router = APIRouter(prefix="/api/groups/{group_id}", tags=["export"])


@router.get("/export")
def export_expenses(
    group_id: int,
    user: CurrentUser,
    exports: ExportServiceDep,
    format: str = Query("csv", description="csv yoki json"),
) -> Response:
    try:
        file = exports.export(user, group_id, format)
    except UnknownExportFormatError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except GroupPermissionError as error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except GroupNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return Response(
        content=file.content,
        media_type=file.content_type,
        headers={"Content-Disposition": f'attachment; filename="{file.filename}"'},
    )
