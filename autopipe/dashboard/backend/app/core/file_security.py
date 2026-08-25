"""File upload security utilities."""

import logging
import os
import re
from pathlib import Path
from typing import Optional, Set, Tuple

from app.core.config import settings
from fastapi import HTTPException, UploadFile, status

logger = logging.getLogger(__name__)

# Whitelist of allowed file extensions by category
ALLOWED_EXTENSIONS: dict[str, Set[str]] = {
    "image": {"png", "jpg", "jpeg", "gif", "svg", "webp"},
    "document": {"pdf", "md", "txt", "csv", "json"},
    "data": {"parquet", "csv", "json", "jsonl", "pkl", "joblib"},
    "archive": {"tar", "gz", "zip", "bz2"},
}

# Flatten for general validation
ALL_ALLOWED_EXTENSIONS = set().union(*ALLOWED_EXTENSIONS.values())

# Dangerous extensions that should never be allowed
DANGEROUS_EXTENSIONS = {
    "exe",
    "dll",
    "bat",
    "sh",
    "py",
    "rb",
    "pl",
    "php",
    "jsp",
    "asp",
    "aspx",
    "jar",
    "war",
    "ear",
    "cmd",
    "ps1",
    "vbs",
    "js",
    "htm",
    "html",
    "xhtml",
}

# Dangerous MIME types
DANGEROUS_MIME_TYPES = {
    "application/x-msdownload",
    "application/x-msdos-program",
    "application/x-msdos-windows",
    "application/x-dosexec",
    "application/javascript",
    "text/javascript",
    "application/ecmascript",
    "text/ecmascript",
    "text/html",
    "application/xhtml+xml",
    "text/vbscript",
}


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and other attacks.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename safe for filesystem use
    """
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename cannot be empty",
        )

    # Remove path components
    filename = os.path.basename(filename)

    # Remove null bytes
    filename = filename.replace("\x00", "")

    # Replace dangerous characters
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)

    # Remove leading dots (hidden files)
    filename = filename.lstrip(".")

    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[: 255 - len(ext)] + ext

    return filename


def validate_file_extension(
    filename: str,
    allowed_extensions: Optional[Set[str]] = None,
) -> Tuple[str, str]:
    """
    Validate and extract file extension.

    Args:
        filename: Filename to validate
        allowed_extensions: Set of allowed extensions (defaults to ALL_ALLOWED_EXTENSIONS)

    Returns:
        Tuple of (sanitized_filename, extension)

    Raises:
        HTTPException: If extension is not allowed or dangerous
    """
    if allowed_extensions is None:
        allowed_extensions = ALL_ALLOWED_EXTENSIONS

    filename = sanitize_filename(filename)

    # Extract extension
    ext_match = re.search(r"\.([a-zA-Z0-9]+)$", filename)
    if not ext_match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must have an extension",
        )

    extension = ext_match.group(1).lower()

    # Check for dangerous extensions
    if extension in DANGEROUS_EXTENSIONS:
        logger.warning(f"Dangerous file extension attempted: {extension}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File type not allowed",
        )

    # Check allowed extensions
    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File extension '.{extension}' not allowed. Allowed: {', '.join(sorted(allowed_extensions))}",
        )

    return filename, extension


def validate_file_size(
    file_size: int,
    max_size: int = settings.MAX_UPLOAD_SIZE,
) -> None:
    """
    Validate file size.

    Args:
        file_size: Size of file in bytes
        max_size: Maximum allowed size in bytes

    Raises:
        HTTPException: If file exceeds max size
    """
    if file_size > max_size:
        size_mb = file_size / (1024 * 1024)
        max_mb = max_size / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({size_mb:.1f}MB) exceeds maximum allowed ({max_mb:.0f}MB)",
        )


def validate_mime_type(
    content_type: str,
    extension: str,
) -> None:
    """
    Validate MIME type against extension.

    Args:
        content_type: Content-Type header value
        extension: File extension

    Raises:
        HTTPException: If MIME type is dangerous or doesn't match extension
    """
    # Check for dangerous MIME types
    if content_type.lower() in DANGEROUS_MIME_TYPES:
        logger.warning(f"Dangerous MIME type attempted: {content_type}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File type not allowed",
        )

    # Expected MIME types by extension
    expected_types = {
        "png": ["image/png"],
        "jpg": ["image/jpeg"],
        "jpeg": ["image/jpeg"],
        "gif": ["image/gif"],
        "svg": ["image/svg+xml"],
        "webp": ["image/webp"],
        "pdf": ["application/pdf"],
        "csv": ["text/csv", "application/csv"],
        "json": ["application/json", "text/json"],
        "jsonl": ["application/jsonlines", "text/jsonl"],
        "txt": ["text/plain"],
        "md": ["text/markdown", "text/x-markdown"],
        "parquet": ["application/octet-stream", "application/parquet"],
        "pkl": ["application/octet-stream", "application/python-pickle"],
        "joblib": ["application/octet-stream"],
        "zip": ["application/zip", "application/x-zip-compressed"],
        "tar": ["application/x-tar"],
        "gz": ["application/gzip"],
        "bz2": ["application/x-bzip2"],
    }

    expected = expected_types.get(extension.lower())
    if expected and content_type not in expected:
        logger.warning(f"MIME type mismatch: expected {expected}, got {content_type}")
        # Note: This is a warning but not blocking - MIME sniffing can be unreliable


async def validate_upload_file(
    file: UploadFile,
    allowed_extensions: Optional[Set[str]] = None,
    max_size: int = settings.MAX_UPLOAD_SIZE,
) -> Tuple[str, int]:
    """
    Comprehensive validation of uploaded file.

    Args:
        file: FastAPI UploadFile
        allowed_extensions: Optional set of allowed extensions
        max_size: Maximum file size in bytes

    Returns:
        Tuple of (sanitized_filename, file_size)

    Raises:
        HTTPException: If any validation fails
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File name is required",
        )

    # Validate extension
    sanitized_name, extension = validate_file_extension(file.filename, allowed_extensions)

    # Validate MIME type (best effort)
    if file.content_type:
        validate_mime_type(file.content_type, extension)

    # Get file size (read content if unknown)
    file_size = 0
    if hasattr(file, "file"):
        # Try to get position after reading
        content = await file.read()
        file_size = len(content)
        await file.seek(0)  # Reset position

        validate_file_size(file_size, max_size)

    return sanitized_name, file_size


def get_secure_upload_path(
    filename: str,
    upload_dir: str = settings.UPLOAD_DIR,
) -> Path:
    """
    Get a secure path for file upload.

    Args:
        filename: Sanitized filename
        upload_dir: Base upload directory

    Returns:
        Secure Path object
    """
    upload_path = Path(upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)

    # Ensure filename is within upload directory
    target_path = upload_path / filename
    resolved = target_path.resolve()
    upload_resolved = upload_path.resolve()

    # Check for path traversal
    if not str(resolved).startswith(str(upload_resolved)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path",
        )

    return resolved
