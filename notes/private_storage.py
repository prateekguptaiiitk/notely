"""Private object storage with a local filesystem fallback."""

from functools import lru_cache
from pathlib import Path, PurePosixPath

from django.conf import settings


def _safe_key(key):
    path = PurePosixPath(str(key).replace("\\", "/"))
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Invalid private storage key")
    return path.as_posix()


@lru_cache(maxsize=1)
def _s3_client():
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.PRIVATE_S3_ENDPOINT_URL,
        region_name=settings.PRIVATE_S3_REGION,
        aws_access_key_id=settings.PRIVATE_S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.PRIVATE_S3_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def using_object_storage():
    return settings.PRIVATE_STORAGE_BACKEND == "s3"


def _local_path(key):
    root = settings.PRIVATE_STORAGE_DIR.resolve()
    path = (root / _safe_key(key)).resolve()
    if root not in path.parents:
        raise ValueError("Private storage key escaped its root")
    return path


def save_private(key, data, content_type="application/octet-stream"):
    key = _safe_key(key)
    if using_object_storage():
        _s3_client().put_object(
            Bucket=settings.PRIVATE_S3_BUCKET,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return key

    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)


def read_private(location):
    if using_object_storage():
        response = _s3_client().get_object(
            Bucket=settings.PRIVATE_S3_BUCKET,
            Key=_safe_key(location),
        )
        return response["Body"].read()
    path = Path(location).resolve()
    root = settings.PRIVATE_STORAGE_DIR.resolve()
    if root not in path.parents:
        raise ValueError("Private storage path escaped its root")
    return path.read_bytes()


def delete_private(location):
    if not location:
        return
    if using_object_storage():
        _s3_client().delete_object(
            Bucket=settings.PRIVATE_S3_BUCKET,
            Key=_safe_key(location),
        )
    else:
        path = Path(location).resolve()
        root = settings.PRIVATE_STORAGE_DIR.resolve()
        if root not in path.parents:
            raise ValueError("Private storage path escaped its root")
        path.unlink(missing_ok=True)


def delete_private_prefix(prefix):
    prefix = _safe_key(prefix.rstrip("/")) + "/"
    if using_object_storage():
        client = _s3_client()
        paginator = client.get_paginator("list_objects_v2")
        for result in paginator.paginate(Bucket=settings.PRIVATE_S3_BUCKET, Prefix=prefix):
            objects = [{"Key": item["Key"]} for item in result.get("Contents", [])]
            if objects:
                client.delete_objects(
                    Bucket=settings.PRIVATE_S3_BUCKET,
                    Delete={"Objects": objects, "Quiet": True},
                )
        return

    path = _local_path(prefix.rstrip("/"))
    if path.is_dir():
        import shutil

        shutil.rmtree(path, ignore_errors=True)
    elif path.exists():
        path.unlink(missing_ok=True)
