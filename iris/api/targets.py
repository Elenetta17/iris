"""Targets operations."""

import ipaddress
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)

from iris.api.dependencies import get_storage, settings
from iris.api.pagination import ListPagination
from iris.api.security import get_current_active_user
from iris.commons.schemas import public
from iris.commons.storage import Storage

router = APIRouter()


@router.get(
    "/",
    response_model=public.Paginated[public.TargetSummary],
    summary="Get all target lists.",
)
async def get_targets(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=0, le=200),
    user: public.Profile = Depends(get_current_active_user),
    storage: Storage = Depends(get_storage),
):
    """Get all target lists."""
    try:
        targets = await storage.get_all_files_no_retry(
            settings.AWS_S3_TARGETS_BUCKET_PREFIX + user.username
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Bucket not found"
        )
    summaries = [
        public.TargetSummary(
            key=target["key"],
            last_modified=datetime.fromisoformat(target["last_modified"]),
        )
        for target in targets
    ]
    querier = ListPagination(summaries, request, offset, limit)
    return await querier.query()


@router.get(
    "/{key}",
    response_model=public.Target,
    responses={404: {"model": public.GenericException}},
    summary="Get target list specified by key.",
)
async def get_target_by_key(
    request: Request,
    key: str,
    user: public.Profile = Depends(get_current_active_user),
    storage: Storage = Depends(get_storage),
):
    """Get a target list information by key."""
    try:
        target_file = await storage.get_file_no_retry(
            settings.AWS_S3_TARGETS_BUCKET_PREFIX + user.username, key
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File object not found"
        )

    return public.Target(
        key=target_file["key"],
        size=target_file["size"],
        content=[c.strip() for c in target_file["content"].split()],
        last_modified=datetime.fromisoformat(target_file["last_modified"]),
    )


async def verify_target_file(target_file):
    """Verify that a target file have a good structure."""
    # Check if file is empty
    target_file.file.seek(0, 2)
    if target_file.file.tell() == 0:
        return False
    target_file.file.seek(0)

    # Check if all lines of the file is valid
    for line in target_file.file.readlines():
        try:
            line_split = line.decode("utf-8").strip().split(",")

            # Check if the prefix is valid
            ipaddress.ip_network(line_split[0])

            # Check if the protocol is supported
            if line_split[1] not in ["icmp", "icmp6", "udp"]:
                return False

            # Check the min TTL
            if not (0 < int(line_split[2]) <= 255):
                return False

            # Check the max TTL
            if not (0 < int(line_split[3]) <= 255):
                return False

        except Exception:
            return False

    target_file.file.seek(0)
    return True


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=public.TargetPostResponse,
    summary="Upload a target list.",
    description="""
    Each line of the file must be like `target,protocol,min_ttl,max_ttl`
    where the target is a IPv4/IPv6 prefix or IPv4/IPv6 address.
    The prococol can be `icmp`, `icmp6` or `udp`.
    """,
)
async def post_target(
    request: Request,
    target_file: UploadFile = File(...),
    user: public.Profile = Depends(get_current_active_user),
    storage: Storage = Depends(get_storage),
):
    """Upload a target list to object storage."""
    if not target_file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Bad target file extension (.csv required)",
        )

    is_correct = await verify_target_file(target_file)
    if not is_correct:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Bad target file structure",
        )

    await storage.upload_file_no_retry(
        storage.targets_bucket(user.username), target_file.filename, target_file.file
    )
    return {"key": target_file.filename, "action": "upload"}


@router.delete(
    "/{key}",
    response_model=public.TargetDeleteResponse,
    responses={
        404: {"model": public.GenericException},
        500: {"model": public.GenericException},
    },
    summary="Delete a target list.",
)
async def delete_target_by_key(
    request: Request,
    key: str,
    user: public.Profile = Depends(get_current_active_user),
    storage: Storage = Depends(get_storage),
):
    """Delete a target list from object storage."""
    try:
        response = await storage.delete_file_check_no_retry(
            settings.AWS_S3_TARGETS_BUCKET_PREFIX + user.username, key
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File object not found"
        )

    if response["ResponseMetadata"]["HTTPStatusCode"] != 204:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error while removing file object",
        )
    return {"key": key, "action": "delete"}
