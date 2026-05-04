from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Optional

import pytest

from app.services import backup_scheduler


class FakeSession:
    """记录调度循环对数据库会话的事务操作。"""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closes += 1


class FakeStopEvent(threading.Event):
    """让 `_run_loop()` 只执行一轮，避免测试启动真实后台线程。"""

    def __init__(self) -> None:
        self.wait_calls = 0
        self.clear_calls = 0
        self.set_calls = 0

    def wait(self, timeout: Optional[float] = None) -> bool:
        self.wait_calls += 1
        return self.wait_calls > 1

    def clear(self) -> None:
        self.clear_calls += 1

    def set(self) -> None:
        self.set_calls += 1


def test_backup_scheduler_start_is_idempotent_and_stop_joins(monkeypatch: pytest.MonkeyPatch) -> None:
    """重复启动时复用已有线程，停止时等待线程退出。"""

    created_threads = []

    class FakeThread:
        """替代真实线程，避免测试产生异步时序抖动。"""

        def __init__(self, target: Callable[[], None], name: str, daemon: bool) -> None:
            self.target = target
            self.name = name
            self.daemon = daemon
            self.started = False
            self.join_timeout: int | None = None
            created_threads.append(self)

        def start(self) -> None:
            self.started = True

        def is_alive(self) -> bool:
            return self.started

        def join(self, timeout: int) -> None:
            self.join_timeout = timeout
            self.started = False

    monkeypatch.setattr(threading, "Thread", FakeThread)
    scheduler = backup_scheduler.BackupScheduler(interval_seconds=60)

    scheduler.start()
    scheduler.start()
    scheduler.stop()

    assert len(created_threads) == 1
    assert created_threads[0].name == "backup-scheduler"
    assert created_threads[0].daemon is True
    assert created_threads[0].join_timeout == 5


def test_backup_scheduler_run_loop_commits_when_backup_record_created(monkeypatch: pytest.MonkeyPatch) -> None:
    """到期备份实际执行后，调度循环提交事务并关闭会话。"""

    session = FakeSession()
    scheduler = backup_scheduler.BackupScheduler(interval_seconds=60)
    scheduler._stop_event = FakeStopEvent()

    monkeypatch.setattr(backup_scheduler, "SessionLocal", lambda: session)
    monkeypatch.setattr(backup_scheduler, "run_due_backup", lambda db: object())

    scheduler._run_loop()

    assert session.commits == 1
    assert session.rollbacks == 0
    assert session.closes == 1


def test_backup_scheduler_run_loop_skips_commit_when_no_backup_is_due(monkeypatch: pytest.MonkeyPatch) -> None:
    """没有到期备份时不提交事务，但仍关闭会话。"""

    session = FakeSession()
    scheduler = backup_scheduler.BackupScheduler(interval_seconds=60)
    scheduler._stop_event = FakeStopEvent()

    monkeypatch.setattr(backup_scheduler, "SessionLocal", lambda: session)
    monkeypatch.setattr(backup_scheduler, "run_due_backup", lambda db: None)

    scheduler._run_loop()

    assert session.commits == 0
    assert session.rollbacks == 0
    assert session.closes == 1


def test_backup_scheduler_run_loop_rolls_back_and_closes_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """调度检查失败时回滚事务，并保证会话被关闭。"""

    session = FakeSession()
    scheduler = backup_scheduler.BackupScheduler(interval_seconds=60)
    scheduler._stop_event = FakeStopEvent()

    def fail_run_due_backup(db: object) -> None:
        raise RuntimeError("scheduled backup failed")

    monkeypatch.setattr(backup_scheduler, "SessionLocal", lambda: session)
    monkeypatch.setattr(backup_scheduler, "run_due_backup", fail_run_due_backup)

    scheduler._run_loop()

    assert session.commits == 0
    assert session.rollbacks == 1
    assert session.closes == 1
