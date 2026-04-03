"""
Heartbeat service — tracks liveness of platform components.

Each long-running service (paper engine, data feed, scheduler)
calls ping() on a regular interval. If a ping goes missing for
more than max_age_seconds, the service is considered stale and
a Telegram alert is sent.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Dict, Optional

from app.core.constants import HEARTBEAT_INTERVAL_SECONDS, HEARTBEAT_STALE_THRESHOLD_SECONDS
from app.core.interfaces import IHeartbeatService
from app.core.models import HeartbeatRecord

logger = logging.getLogger(__name__)


class InMemoryHeartbeatService(IHeartbeatService):
    """
    In-memory heartbeat tracker.

    Suitable for single-process deployments.
    For multi-process: use the DB-backed HeartbeatRepository instead.
    """

    def __init__(self) -> None:
        self._records: Dict[str, HeartbeatRecord] = {}
        self._lock = threading.Lock()

    def ping(
        self,
        service_name: str,
        status: str = "ok",
        message: str = "",
    ) -> HeartbeatRecord:
        record = HeartbeatRecord(
            service_name=service_name,
            status=status,
            timestamp=datetime.utcnow(),
            message=message,
        )
        with self._lock:
            self._records[service_name] = record
        logger.debug("Heartbeat: %s [%s]", service_name, status)
        return record

    def is_alive(
        self, service_name: str, max_age_seconds: int = HEARTBEAT_STALE_THRESHOLD_SECONDS
    ) -> bool:
        record = self.get_last_heartbeat(service_name)
        if record is None:
            return False
        age = (datetime.utcnow() - record.timestamp).total_seconds()
        return age < max_age_seconds

    def get_last_heartbeat(self, service_name: str) -> Optional[HeartbeatRecord]:
        with self._lock:
            return self._records.get(service_name)

    def get_all_statuses(self) -> Dict[str, Dict]:
        with self._lock:
            result = {}
            for name, record in self._records.items():
                age = (datetime.utcnow() - record.timestamp).total_seconds()
                result[name] = {
                    "status": record.status,
                    "last_seen_secs": round(age, 1),
                    "alive": age < HEARTBEAT_STALE_THRESHOLD_SECONDS,
                    "timestamp": record.timestamp.isoformat(),
                }
            return result


class HeartbeatWorker:
    """
    Background thread that pings the heartbeat service on an interval.
    Start one of these per long-running service.

    Usage:
        worker = HeartbeatWorker(
            service_name="paper_engine",
            heartbeat_service=hb_service,
            interval=60,
        )
        worker.start()
        # ... your main loop ...
        worker.stop()
    """

    def __init__(
        self,
        service_name: str,
        heartbeat_service: IHeartbeatService,
        interval: int = HEARTBEAT_INTERVAL_SECONDS,
    ) -> None:
        self._service_name = service_name
        self._hb = heartbeat_service
        self._interval = interval
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=f"hb-{self._service_name}"
        )
        self._thread.start()
        logger.info("HeartbeatWorker started for service=%s interval=%ds",
                    self._service_name, self._interval)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("HeartbeatWorker stopped for service=%s", self._service_name)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._hb.ping(self._service_name, status="ok")
            except Exception as exc:
                logger.error("Heartbeat ping failed for %s: %s", self._service_name, exc)
            self._stop_event.wait(timeout=self._interval)
