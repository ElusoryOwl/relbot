import os

MAX_SPOUSES = 8
MAX_DATING = 5
DB_PATH = os.getenv("DB_PATH", "relationships.db")

# Cooldowns
INTERACTION_COOLDOWN_SEC = int(os.getenv("INTERACTION_COOLDOWN_SEC", "15"))
PROPOSAL_COOLDOWN_SEC = int(os.getenv("PROPOSAL_COOLDOWN_SEC", "10"))

# /stop pause duration
STOP_MINUTES = int(os.getenv("STOP_MINUTES", "30"))

EMBED_FIELD_MAX = 1020
BIO_MAX = 500
TITLE_MAX = 32
NICKNAME_MAX = 32

ACTION_RETENTION_DAYS = int(os.getenv("ACTION_RETENTION_DAYS", "30"))

# How many parent/child hops count as "family" when blocking romantic
# bonds (dating/marriage) and adoption between relatives.
# 1 = direct parent/child only. 4 also catches grandparent/grandchild,
# siblings (shared parent), and aunt/uncle-niece/nephew bonds formed
# through chained /adopt calls.
FAMILY_CHECK_DEPTH = int(os.getenv("FAMILY_CHECK_DEPTH", "4"))

_DB_DIR = os.path.dirname(os.path.abspath(DB_PATH)) or "."
BACKUP_DIR = os.getenv("BACKUP_DIR", os.path.join(_DB_DIR, "backups"))
BACKUP_INTERVAL_HOURS = int(os.getenv("BACKUP_INTERVAL_HOURS", "24"))
BACKUP_KEEP = int(os.getenv("BACKUP_KEEP", "7"))
HEARTBEAT_PATH = os.getenv("HEARTBEAT_PATH", os.path.join(_DB_DIR, "heartbeat"))

# Optional: sync slash commands to a single guild instantly instead of
# waiting up to an hour for a global sync. Useful in dev; leave unset in
# production so the bot works across every server it's in.
TEST_GUILD_ID = int(os.getenv("TEST_GUILD_ID")) if os.getenv("TEST_GUILD_ID") else None
