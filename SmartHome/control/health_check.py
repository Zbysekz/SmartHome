#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import psutil
from datetime import datetime, timezone
from templates.threadModule import cThreadModule
from parameters import parameters
from logger import Logger
from databaseMySQL import cMySQL

DISK_USED_THRESHOLD_PERCENT = 90


class cHealthCheck(cThreadModule):
    _type = 'health_check'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.mySQL = cMySQL()
        self.logger = Logger("health_check", verbosity=parameters.VERBOSITY, mySQL=self.mySQL)

    def _handle(self):
        self._check_disks()
        self._check_cpu()
        self._check_ram()
        self._check_backups()

    def _check_disks(self):
        for partition in psutil.disk_partitions():
            if partition.mountpoint.startswith('/snap'):
                continue
            try:
                usage = psutil.disk_usage(partition.mountpoint)
            except PermissionError:
                continue
            free_gb = usage.free / (1024 ** 3)
            self.mySQL.insertValue('disk_free_gb', partition.mountpoint, round(free_gb, 2),
                                   periodicity=60 * 60, writeNowDiff=5)
            if usage.percent >= DISK_USED_THRESHOLD_PERCENT:
                self.logger.log(
                    f"Disk critical on {partition.mountpoint}: "
                    f"{usage.percent:.1f}% used, {free_gb:.1f} GB free",
                    Logger.CRITICAL
                )

    def _check_cpu(self):
        cpu_percent = psutil.cpu_percent(interval=1)
        self.mySQL.insertValue('cpu_usage', 'server', round(cpu_percent, 1),
                               periodicity=60 * 60, writeNowDiff=5)

    def _check_ram(self):
        mem = psutil.virtual_memory()
        free_gb = mem.available / (1024 ** 3)
        self.mySQL.insertValue('ram_free_gb', 'server', round(free_gb, 2),
                               periodicity=60 * 60, writeNowDiff=1)

    def _check_backups(self):
        self._update_backup_state('last_db_backup', parameters.RESTIC_PATH_DB)
        self._update_backup_state('last_pc_backup', parameters.RESTIC_PATH_PC)

    def _update_backup_state(self, state_column, restic_path):
        snapshots_dir = os.path.join(restic_path, 'snapshots')
        try:
            files = os.listdir(snapshots_dir)
            if not files:
                self.logger.log(f"No snapshots found in {snapshots_dir}", Logger.CRITICAL)
                return
            latest_mtime = max(
                os.path.getmtime(os.path.join(snapshots_dir, f)) for f in files
            )
            dt = datetime.fromtimestamp(latest_mtime, tz=timezone.utc)
            self.mySQL.updateState(state_column, dt.strftime('%Y-%m-%d %H:%M:%S'))
        except Exception as e:
            self.logger.log(f"Failed to read restic snapshots at {snapshots_dir}: {e}")
