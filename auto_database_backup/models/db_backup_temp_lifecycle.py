# -*- coding: utf-8 -*-
"""Hardening for backup temporary-file lifecycle.

This intentionally avoids sweeping generic files from the operating-system
``temp`` directory. Only files created under the module-owned namespace are
eligible for stale cleanup.
"""

import logging
import os
import tempfile
import time

import boto3

from odoo import models

_logger = logging.getLogger(__name__)

_OWNED_TMP_DIRNAME = "odoo-auto-database-backup"
_STALE_AFTER_SECONDS = 2 * 60 * 60


class DbBackupConfigureTempLifecycle(models.Model):
    _inherit = "db.backup.configure"

    def _owned_backup_tmp_dir(self):
        """Return a private namespace for temporary backup payloads."""
        root = os.path.join(tempfile.gettempdir(), _OWNED_TMP_DIRNAME)
        os.makedirs(root, mode=0o700, exist_ok=True)
        try:
            os.chmod(root, 0o700)
        except OSError:
            # The directory may live on a filesystem that does not support
            # POSIX permissions. Creation/isolation is still useful there.
            pass
        return root

    def _cleanup_stale_owned_backup_temps(self):
        """Remove only stale files created by this module.

        The upstream fix scanned generic ``/tmp/tmp*`` entries. That can touch
        temporary data owned by unrelated processes. Keeping an explicit
        namespace makes cleanup deterministic and safe for shared hosts.
        """
        root = self._owned_backup_tmp_dir()
        cutoff = time.time() - _STALE_AFTER_SECONDS
        try:
            entries = os.scandir(root)
        except OSError as error:
            _logger.warning("Unable to scan backup temp namespace: %s", error)
            return

        with entries:
            for entry in entries:
                if not entry.name.startswith("backup-") or not entry.is_file():
                    continue
                try:
                    if entry.stat().st_mtime < cutoff:
                        os.remove(entry.path)
                except OSError as error:
                    _logger.info(
                        "Unable to remove stale backup temp %s: %s",
                        entry.path,
                        error,
                    )

    def _run_backup(self, manual=False):
        """Clean our namespace before each scheduled or manual backup run."""
        self._cleanup_stale_owned_backup_temps()
        return super()._run_backup(manual=manual)

    def _backup_to_amazon_s3(self, db_name, backup_filename, backup_time):
        """Upload to S3/S3-compatible storage with deterministic cleanup."""
        if not (self.aws_access_key and self.aws_secret_access_key):
            # Preserve the canonical validation and translated error from the
            # base implementation instead of duplicating it here.
            return super()._backup_to_amazon_s3(
                db_name, backup_filename, backup_time
            )

        client_kwargs = self._get_s3_client_kwargs()
        s3_client = boto3.client("s3", **client_kwargs)
        if self.auto_remove:
            response = s3_client.list_objects(
                Bucket=self.bucket_file_name, Prefix=self.aws_folder_name
            )
            today = self.env["ir.fields.converter"]._context.get("date") \
                if "ir.fields.converter" in self.env else None
            # Fall back to the parent for retention behavior. The hardening in
            # this override is deliberately scoped to temp-file lifecycle.
            if response.get("Contents") and today is not None:
                return super()._backup_to_amazon_s3(
                    db_name, backup_filename, backup_time
                )

        s3 = boto3.resource("s3", **client_kwargs)
        s3.Object(self.bucket_file_name, self.aws_folder_name + "/").put()
        bucket = s3.Bucket(self.bucket_file_name)
        prefixes = {
            obj.key[:-1] for obj in bucket.objects.all() if obj.key.endswith("/")
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
        try:
            with temp:
                self.dump_data(
                    db_name, temp, self.backup_format, self.backup_frequency
                )
                temp.flush()
            remote_file_path = f"{self.aws_folder_name}/{backup_filename}"
            s3.Object(self.bucket_file_name, remote_file_path).upload_file(
                temp.name
            )
        finally:
            try:
                os.remove(temp.name)
            except FileNotFoundError:
                pass
            except OSError as error:
                _logger.warning(
                    "Unable to remove backup temporary file %s: %s",
                    temp.name,
                    error,
                )
