import sqlite3
import time
from pathlib import Path
import logging
import json

LOG = logging.getLogger("session_manager")
STATE_DIR = Path("C:/sterling/state") if Path("C:/sterling").exists() else Path("./state")
STATE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = STATE_DIR / "connector_state.sqlite"

class SessionManager:
    def __init__(self):
        self.session_id = None
        self.accounts = []
        self._conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self._init_db()
        self.outbound_callback = None

    def _init_db(self):
        cur = self._conn.cursor()
        cur.execute(
            """CREATE TABLE IF NOT EXISTS idempotency (
                key TEXT PRIMARY KEY,
                result TEXT,
                created_at INTEGER
            )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS session_meta (
                k TEXT PRIMARY KEY, v TEXT
            )"""
        )
        self._conn.commit()

    def set_session(self, session_id: str, accounts: list):
        self.session_id = session_id
        self.accounts = accounts
        self._set_meta("session_id", session_id)
        self._set_meta("accounts", json.dumps(accounts))

    def _set_meta(self, k, v):
        cur = self._conn.cursor()
        cur.execute("INSERT OR REPLACE INTO session_meta (k,v) VALUES (?,?)", (k, v))
        self._conn.commit()

    def get_meta(self, k, default=None):
        cur = self._conn.cursor()
        cur.execute("SELECT v FROM session_meta WHERE k = ?", (k,))
        r = cur.fetchone()
        return r[0] if r else default

    def is_idempotent(self, key: str):
        cur = self._conn.cursor()
        cur.execute("SELECT result FROM idempotency WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else None

    def store_idempotent(self, key: str, result: str):
        cur = self._conn.cursor()
        cur.execute("INSERT OR REPLACE INTO idempotency (key, result, created_at) VALUES (?, ?, ?)", (key, result, int(time.time())))
        self._conn.commit()

    def register_outbound_callback(self, cb):
        self.outbound_callback = cb

    def handle_inbound_event(self, msg: dict):
        LOG.info("Inbound event: %s", msg)
        if self.outbound_callback:
            try:
                self.outbound_callback(msg)
            except Exception:
                LOG.exception("Error forwarding inbound event")