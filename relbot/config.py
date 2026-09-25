import os

MAX_SPOUSES = 8
MAX_DATING = 5
DB_PATH = os.getenv("DB_PATH", "relationships.db")
ADULT_ROLE_NAME = "18+"
LEWD_COOLDOWN_SEC = 25
PROPOSAL_COOLDOWN_SEC = 10
HEAT_DECAY_PER_HOUR = 8
STOP_MINUTES = 30
EMBED_FIELD_MAX = 1020
ACTION_RETENTION_DAYS = 30

# How many parent/child hops count as "family" when blocking lewd commands.
# 1 = direct parent/child only. 4 also catches grandparent/grandchild,
# siblings (shared parent), and aunt/uncle-niece/nephew bonds formed
# through chained /adopt calls.
FAMILY_CHECK_DEPTH = int(os.getenv("FAMILY_CHECK_DEPTH", "4"))

_DB_DIR = os.path.dirname(os.path.abspath(DB_PATH)) or "."
BACKUP_DIR = os.getenv("BACKUP_DIR", os.path.join(_DB_DIR, "backups"))
BACKUP_INTERVAL_HOURS = int(os.getenv("BACKUP_INTERVAL_HOURS", "24"))
BACKUP_KEEP = int(os.getenv("BACKUP_KEEP", "7"))
HEARTBEAT_PATH = os.getenv("HEARTBEAT_PATH", os.path.join(_DB_DIR, "heartbeat"))
