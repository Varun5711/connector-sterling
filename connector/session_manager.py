import sqlite3, time
from pathlib import Path
import logging

LOG = logging.getLogger("session_manager")
STATE_DIR = Path("./state")
STATE_DIR.mkdir(exist_ok=True)
DB_PATH = STATE_DIR / "connector_state.sqlite"

class SessionManager:
    def __init__(self):
        self.session_id = None
        self.accounts = []
        self._conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._init_db()
        self.outbound_callback = None

    def _init_db(self):
        cur = self._conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS idempotency (key TEXT PRIMARY KEY, result TEXT, created_at INTEGER)")
        self._conn.commit()

    def set_session(self, session_id, accounts):
        self.session_id = session_id
        self.accounts = accounts

    def is_idempotent(self, key):
        cur = self._conn.cursor()
        cur.execute("SELECT result FROM idempotency WHERE key=?", (key,))
        r = cur.fetchone()
        return r[0] if r else None

    def store_idempotent(self, key, result):
        cur = self._conn.cursor()
        cur.execute("INSERT OR REPLACE INTO idempotency VALUES (?,?,?)", (key, result, int(time.time())))
        self._conn.commit()

    def register_outbound_callback(self, cb):
        self.outbound_callback = cb

    def handle_inbound_event(self, msg):
        LOG.info("Inbound event: %s", msg)
        if self.outbound_callback:
            self.outbound_callback(msg)