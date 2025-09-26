import logging
import time
import sqlite3
from pathlib import Path

LOG = logging.getLogger("session_manager")

STATE_DIR = Path("C:/sterling/state") if Path("C:/sterling").exists() else Path("./state")
STATE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = STATE_DIR / "connector_state.sqlite"

class SessionManager:
    def __init__(self):
        self.accounts = []
        self.session_id = "sterling-session"
        self.outbound_callback = None
        self._init_db()

    def _init_db(self):
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        cur = self.conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS idempotency (key TEXT PRIMARY KEY, result TEXT, created_at INTEGER)""")
        self.conn.commit()

    def is_idempotent(self, key):
        cur = self.conn.cursor()
        cur.execute("SELECT result FROM idempotency WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else None

    def store_idempotent(self, key, result):
        cur = self.conn.cursor()
        cur.execute("INSERT OR REPLACE INTO idempotency (key, result, created_at) VALUES (?, ?, ?)", (key, result, int(time.time())))
        self.conn.commit()

    def handle_inbound_event(self, msg):
        LOG.info("Inbound event: %s", msg)
        if self.outbound_callback:
            try:
                self.outbound_callback(msg)
            except Exception:
                LOG.exception("Error forwarding inbound event")

    def register_outbound_callback(self, cb):
        self.outbound_callback = cb

    def set_accounts(self, accounts):
        self.accounts = accounts

    def get_accounts(self):
        return self.accounts