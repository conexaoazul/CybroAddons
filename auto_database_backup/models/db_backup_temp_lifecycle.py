# -*- coding: utf-8 -*-
"""Hardening for backup temporary-file lifecycle.

Only files created under a service-owned namespace are eligible for stale
cleanup. Generic operating-system temporary files are never swept.
"""

import logging
import os
import tempfile
import time

import boto3

from odoo import fields, models

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None

_logger = logging.getLogger(__name__)

_OWNED_TMP_DIRNAME = "odoo-auto-database-backup"
_STALE_AFTER_SECONDS = 2 * 60 * 60


class DbBackupConfigureTempLifecycle(models.Model):
    _inherit = "db.backup.configure"

    def _owned_backup_tmp_dir(self):
        """Return a temp namespace isolated by the current OS user.

        Multiple Odoo services may share ``/tmp`` while running under distinct
        Unix users. Including the effective uid prevents one service from
        creating a mode-0700 directory that blocks another service.
        """
        uid = getattr(os, "geteuid", lambda: 0)()
        root = os.path.join(
            tempfile.gettempdir(),
            f"{_OWNED_TMP_DIRNAME}-{uid}",
        )
        os.makedirs(root, mode=0o700, exist_ok=True)
        try:
            os.chmod(root, 0o700)
        except OSError:
            pass
        return root

    def _try_lock(self, lock_stream):
        """Acquire an exclusive non-blocking lock when supported.

        On non-POSIX platforms stale sweeping is disabled rather than risking
        removal of an in-flight backup. Normal ``finally`` cleanup still runs.
        """
        if fcntl is None:
            return False
        try:
            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def _cleanup_stale_owned_backup_temps(self):
        """Remove stale payloads only when their lock is not held.

        Age alone is insufficient because a large multipart upload may remain
        active long after the dump file's mtime stops changing. Every payload
        therefore has a sidecar ``.lock`` file held for the whole dump/upload
        lifecycle. Cleanup skips any lock that another process still holds.
        """
        if fcntl is None:
            return
        root = self._owned_backup_tmp_dir()
        cutoff = time.time() - _STALE_AFTER_SECONDS
        try:
            entries = list(os.scandir(root))
        except OSError as error:
            _logger.warning("Unable to scan backup temp namespace: %s", error)
            return

        for entry in entries:
            if (
                not entry.name.startswith("backup-")
                or entry.name.endswith(".lock")
                or not entry.is_file()
            ):
                continue
            lock_path = entry.path + ".lock"
            try:
                if entry.stat().st_mtime >= cutoff:
                    continue
                with open(lock_path, "a+b") as lock_stream:
                    if not self._try_lock(lock_stream):
                        continue
                    os.remove(entry.path)
                    try:
                        os.remove(lock_path)
                    except FileNotFoundError:
                        pass
            except OSError as error:
                _logger.info(
                    "Unable to remove stale backup temp %s: %s",
                    entry.path,
                    error,
                )

    def _run_backup(self, manual=False):
        """Clean abandoned owned payloads before each backup run."""
        self._cleanup_stale_owned_backup_temps()
        return super()._run_backup(manual=manual)

    def _backup_to_amazon_s3(self, db_name, backup_filename, backup_time):
        """Upload to S3/S3-compatible storage with deterministic cleanup."""
        if not (self.aws_access_key and self.aws_secret_access_key):
            return super()._backup_to_amazon_s3(
                db_name, backup_filename, backup_time
            )

        client_kwargs = self._get_s3_client_kwargs()
        s3_client = boto3.client("s3", **client_kwargs)
        if self.auto_remove:
            response = s3_client.list_objects(
                Bucket=self.bucket_file_name,
                Prefix=self.aws_folder_name,
            )
            today = fields.date.today()
            for file in response.get("Contents", []):
                if (today - file["LastModified"].date()).days >= \
                        self.days_to_remove:
                    s3_client.delete_object(
                        Bucket=self.bucket_file_name,
                        Key=file["Key"],
                    )

        s3 = boto3.resource("s3", **client_kwargs)
        s3.Object(self.bucket_file_name, self.aws_folder_name + "/").put()
        bucket = s3.Bucket(self.bucket_file_name)
        prefixes = {
            obj.key[:-1]
            for obj in bucket.objects.all()
            if obj.key.endswith("/")
        }
        if self.aws_folder_name not in prefixes:
            return

        temp = tempfile.NamedTemporaryFile(
            mode="wb+",
            prefix="backup-",
            suffix=f".{self.backup_format}",
            dir=self._owned_backup_tmp_dir(),
            delete=False,
        )
        lock_path = temp.name + ".lock"
        lock_stream = open(lock_path, "a+b")
        try:
            if fcntl is not None:
                fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX)
            with temp:
                self.dump_data(
                    db_name,
                    temp,
                    self.backup_format,
                    self.backup_frequency,
                )
                temp.flush()
            remote_file_path = f"{self.aws_folder_name}/{backup_filename}"
            s3.Object(
                self.bucket_file_name,
                remote_file_path,
            ).upload_file(temp.name)
        finally:
            lock_stream.close()
            for path in (temp.name, lock_path):
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
                except OSError as error:
                    _logger.warning(
                        "Unable to remove backup temporary path %s: %s",
                        path,
                        error,
                    )
