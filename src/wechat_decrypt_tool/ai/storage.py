from __future__ import annotations
from .diagnostics import observed, event as diagnostic_event
import logging

import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from ..app_paths import get_output_dir


# 事件默认保留窗口；超过该窗口且无需重放的事件会被回收。
EVENT_RETENTION_SECONDS = 24 * 3600
# 事件表空闲页超过该阈值才执行 VACUUM，避免频繁全库重写。
COMPACT_MINIMUM_BYTES = 64 * 1024 * 1024

SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS records (
        kind TEXT NOT NULL, id TEXT NOT NULL, account TEXT NOT NULL DEFAULT '',
        body TEXT NOT NULL, updated REAL NOT NULL, PRIMARY KEY(kind,id));
    CREATE INDEX IF NOT EXISTS records_account ON records(kind,account,updated);
    CREATE INDEX IF NOT EXISTS records_status ON records(kind,json_extract(body,'$.status'),updated);
    CREATE INDEX IF NOT EXISTS records_task_usage ON records(kind,account,json_extract(body,'$.task_id'));
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, account TEXT NOT NULL,
        kind TEXT NOT NULL, body TEXT NOT NULL, unique_key TEXT UNIQUE,
        delivered INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
"""


class AIStore:
    """短事务业务存储；与工作流检查点分开，避免模型请求持有数据库锁。"""

    def __init__(self, root: Path | None = None):
        self.root = root or get_output_dir() / "ai"
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "ai.sqlite3"
        self.lock = threading.RLock()
        self.revoked_accounts = set()
        # SSE 订阅者通过条件变量等待新事件；SQLite 仍是断线重放的权威来源。
        # 使用按账号修订号，避免其他账号的高频事件无谓唤醒当前连接。
        self._event_condition = threading.Condition()
        self._event_revisions = {}
        with self.connection() as db:
            db.executescript(SCHEMA_SQL)

    @contextmanager
    def connection(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=30)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA journal_mode=WAL")
            try:
                with db:
                    yield db
            except Exception as error:
                diagnostic_event('storage.transaction.failed', level=logging.ERROR, error=error, committed=False)
                raise
            finally:
                db.close()

    def put(self, kind, body, id=None, account=""):
        id = id or body.get("id") or uuid.uuid4().hex
        body = {**body, "id": id}
        with self.connection() as db:
            if (account or body.get("account", "")) in self.revoked_accounts:
                return body
            db.execute("INSERT INTO records VALUES(?,?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET body=excluded.body, account=excluded.account, updated=excluded.updated",
                       (kind, id, account or body.get("account", ""), json.dumps(body, ensure_ascii=False), time.time()))
        return body

    def get(self, kind, id):
        with self.connection() as db:
            row = db.execute("SELECT body FROM records WHERE kind=? AND id=?", (kind, id)).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, kind, account=None, limit=None, offset=0, compact=False):
        column = "json_remove(body,'$.results','$.overview','$.models','$.cursors')" if compact else "body"
        args = [kind] if account is None else [kind, account]
        sql = f"SELECT {column} FROM records WHERE kind=?" + (" AND account=?" if account is not None else "") + " ORDER BY updated DESC"
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            args.extend([limit, offset])
        with self.connection() as db:
            rows = db.execute(sql, args).fetchall()
        return [json.loads(row[0]) for row in rows]

    def tasks_in_status(self, statuses):
        placeholders = ",".join("?" for _ in statuses)
        with self.connection() as db:
            rows = db.execute(f"SELECT body FROM records WHERE kind='task' AND json_extract(body,'$.status') IN ({placeholders}) ORDER BY updated DESC", statuses).fetchall()
        return [json.loads(row[0]) for row in rows]

    @observed('storage.recover_interrupted_usage')
    def recover_interrupted_usage(self):
        """仅在服务启动、尚未接受请求时收尾上次进程遗留的调用。"""
        now = time.time()
        with self.connection() as db:
            # 无法获知进程退出的准确时间，不补造结束时间、耗时或 Token。
            db.execute("""UPDATE records SET
                body=json_set(body,'$.status','interrupted','$.error_type','ProcessInterrupted',
                              '$.recovered_at',?), updated=?
                WHERE kind='usage' AND json_extract(body,'$.status')='running'""", (now, now))
            recovered = db.execute('SELECT changes()').fetchone()[0]
        diagnostic_event('storage.usage.recovered', count=recovered, status='interrupted')

    def latest_event_id(self):
        with self.connection() as db:
            return db.execute("SELECT coalesce(max(id),0) FROM events").fetchone()[0]

    def delete(self, kind, id):
        with self.connection() as db:
            db.execute("DELETE FROM records WHERE kind=? AND id=?", (kind, id))

    def event(self, account, kind, body, unique_key=None, replace=False):
        """写入事件供 SSE 重放。

        默认行为保持不变：提供 `unique_key` 时按去重语义写入（同 key 已存在则忽略），
        用于提醒等只应投递一次的事件。`replace=True` 时改为用最新快照替换旧行，
        让高频进度事件每个逻辑任务只保留一行，同时因 INSERT OR REPLACE 会删除旧行、
        新行仍获得递增的自增 id，断线重连的 EventSource 依然能收到最新状态。
        """
        with self.connection() as db:
            if account in self.revoked_accounts:
                return
            payload = json.dumps(body, ensure_ascii=False)
            if unique_key is None:
                cursor = db.execute(
                    "INSERT INTO events(account,kind,body,created) VALUES(?,?,?,?)",
                    (account, kind, payload, time.time()))
            elif replace:
                cursor = db.execute(
                    "INSERT OR REPLACE INTO events(account,kind,body,unique_key,created) VALUES(?,?,?,?,?)",
                    (account, kind, payload, unique_key, time.time()))
            else:
                cursor = db.execute(
                    "INSERT OR IGNORE INTO events(account,kind,body,unique_key,created) VALUES(?,?,?,?,?)",
                    (account, kind, payload, unique_key, time.time()))
            inserted = cursor.rowcount > 0
        if inserted:
            with self._event_condition:
                self._event_revisions[account] = self._event_revisions.get(account, 0) + 1
                self._event_condition.notify_all()

    def event_revision(self, account):
        """返回进程内事件修订号，用于无竞态地建立 SSE 等待点。"""
        with self._event_condition:
            return self._event_revisions.get(account, 0)

    def wait_for_event(self, account, revision, timeout):
        """阻塞等待账号出现新事件；超时后由 SSE 发送低频心跳。"""
        with self._event_condition:
            changed = self._event_condition.wait_for(
                lambda: self._event_revisions.get(account, 0) != revision,
                timeout=max(0, timeout),
            )
            return changed, self._event_revisions.get(account, 0)

    def events(self, after=0, account=None, pending=False):
        sql, args = "SELECT * FROM events WHERE id>?", [after]
        if account is not None:
            sql += " AND account=?"
            args.append(account)
        if pending:
            sql += " AND delivered=0 AND kind='notification'"
        with self.connection() as db:
            rows = db.execute(sql + " ORDER BY id LIMIT 100", args).fetchall()
        return [{**dict(row), "body": json.loads(row["body"])} for row in rows]

    @observed('storage.acknowledge')
    def acknowledge(self, id):
        with self.connection() as db:
            db.execute("UPDATE events SET delivered=1 WHERE id=?", (id,))

    @observed('storage.prune_duplicates')
    def prune_duplicate_events(self, batch=2000):
        """一次性折叠旧版追加式进度事件：每个逻辑任务只保留最新快照。

        新写入的进度事件已带 unique_key、本身只保留一行；这里主要清理升级前
        历史遗留的、同一任务多次追加的整份快照，避免巨型库只能等 TTL 慢慢过期。
        """
        total = 0
        for kind, field in (('local_search_index', '$.id'), ('local_search_download', '$.id'),
                            ('local_search_total', '$.job_id')):
            with self.connection() as db:
                db.execute("CREATE TEMP TABLE IF NOT EXISTS keep_event_ids(id INTEGER PRIMARY KEY)")
                db.execute("DELETE FROM keep_event_ids")
                db.execute(
                    f"INSERT INTO keep_event_ids SELECT max(id) FROM events "
                    f"WHERE kind=? AND unique_key IS NULL GROUP BY json_extract(body,'{field}')", (kind,))
                while True:
                    removed = db.execute(
                        "DELETE FROM events WHERE id IN (SELECT id FROM events "
                        "WHERE kind=? AND unique_key IS NULL AND id NOT IN (SELECT id FROM keep_event_ids) LIMIT ?)",
                        (kind, batch)).rowcount
                    total += removed
                    db.commit()
                    if removed < batch:
                        break
                db.execute("DELETE FROM keep_event_ids")
        for kind in ('local_search_device', 'local_search_gpu'):
            with self.connection() as db:
                total += db.execute(
                    "DELETE FROM events WHERE kind=? AND unique_key IS NULL AND id < (SELECT max(id) FROM events WHERE kind=?)",
                    (kind, kind)).rowcount
        if total:
            diagnostic_event('storage.events.deduplicated', count=total)
        return total

    @observed('storage.prune_events')
    def prune_events(self, max_age=EVENT_RETENTION_SECONDS, batch=2000):
        """按 TTL 批量回收事件：非通知事件直接过期；已投递通知同样回收，未投递通知保留。"""
        cutoff = time.time() - max_age
        total = 0
        while True:
            with self.connection() as db:
                removed = db.execute(
                    "DELETE FROM events WHERE id IN (SELECT id FROM events "
                    "WHERE created<? AND (kind!='notification' OR delivered=1) LIMIT ?)",
                    (cutoff, batch)).rowcount
            total += removed
            if removed < batch:
                break
        if total:
            diagnostic_event('storage.events.pruned', count=total, retention_seconds=max_age)
        return total

    @observed('storage.compact')
    def compact(self, minimum_bytes=COMPACT_MINIMUM_BYTES):
        """回收已删除行遗留的空闲页；空闲空间不多时不做全库重写。"""
        with self.lock:
            probe = sqlite3.connect(self.path, timeout=30)
            try:
                page_size = probe.execute('PRAGMA page_size').fetchone()[0]
                free = probe.execute('PRAGMA freelist_count').fetchone()[0] * page_size
            finally:
                probe.close()
            if free < minimum_bytes:
                return 0
            # VACUUM 不能在事务内执行，使用独立连接并先截断 WAL。
            db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
            try:
                db.execute('PRAGMA journal_mode=WAL')
                db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
                db.execute('VACUUM')
            finally:
                db.close()
        diagnostic_event('storage.compacted', freed_bytes=free)
        return free

    def maintain(self, max_age=EVENT_RETENTION_SECONDS, minimum_bytes=COMPACT_MINIMUM_BYTES):
        """启动维护：折叠遗留重复事件、回收过期事件，再按需压缩数据库文件。"""
        deduplicated = self.prune_duplicate_events()
        removed = self.prune_events(max_age)
        freed = self.compact(minimum_bytes)
        return deduplicated, removed, freed

    @observed('storage.purge_account')
    def purge_account(self, account):
        with self.connection() as db:
            self.revoked_accounts.add(account)
            db.execute("DELETE FROM records WHERE account=?", (account,))
            db.execute("DELETE FROM events WHERE account=?", (account,))
