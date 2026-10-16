"""Private, per-file atomic persistence for a single writer."""

from __future__ import annotations

import errno
import os
import stat
import tempfile
from contextlib import suppress
from pathlib import Path


def check_destination(path: str | Path, *, overwrite: bool) -> os.stat_result | None:
    """Reject unsupported targets and require real write access without truncation."""
    path = Path(path)
    try:
        original = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(original.st_mode):
        raise OSError(errno.EINVAL, "Destination must be a regular file, not a symbolic link", str(path))
    if not overwrite:
        raise FileExistsError(errno.EEXIST, "Use an explicit overwrite option or a new path", str(path))
    if not original.st_mode & 0o222:
        raise PermissionError(errno.EACCES, "Destination is read-only", str(path))
    fd = os.open(path, os.O_WRONLY)
    os.close(fd)
    return original


def _preserve_permissions(source: Path, staged: Path, original: os.stat_result) -> None:
    """Preserve ownership, mode and access ACL when supported; fail on access errors."""
    if hasattr(os, "chown"):
        staged_stat = staged.stat()
        if (staged_stat.st_uid, staged_stat.st_gid) != (original.st_uid, original.st_gid):
            os.chown(staged, original.st_uid, original.st_gid)
    os.chmod(staged, stat.S_IMODE(original.st_mode))
    if hasattr(os, "getxattr"):
        acl_name = "system.posix_acl_access"
        absent = {errno.ENODATA, errno.ENOTSUP}
        try:
            acl = os.getxattr(source, acl_name)
        except OSError as exc:
            if exc.errno not in absent:
                raise
            try:
                os.removexattr(staged, acl_name)
            except OSError as removal:
                if removal.errno not in absent:
                    raise
        else:
            os.setxattr(staged, acl_name, acl)


def atomic_write_text(path: str | Path, content: str, *, overwrite: bool) -> None:
    """Prepare and flush same-directory staging, then replace without truncating."""
    path = Path(path)
    original = check_destination(path, overwrite=overwrite)
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            staged = Path(stream.name)
            if original is not None:
                _preserve_permissions(path, staged, original)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        # Recheck authorization immediately before commit; concurrent writers remain unsupported.
        check_destination(path, overwrite=overwrite)
        os.replace(staged, path)
        staged = None
    finally:
        if staged is not None:
            # Preserve the original failure if cleanup itself is denied.
            with suppress(OSError):
                staged.unlink(missing_ok=True)
