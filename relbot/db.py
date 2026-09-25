import asyncio
import glob
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiosqlite

from relbot import config
from relbot.config import ACTION_RETENTION_DAYS, FAMILY_CHECK_DEPTH

log = logging.getLogger("relbot.db")

_CONFIG_COLUMNS = {
    "log_channel",
    "locked",
}
_PROFILE_COLUMNS = {
    "bio",
    "privacy",
    "title",
    "stopped_until",
}

_conn: Optional[aiosqlite.Connection] = None
_conn_lock = asyncio.Lock()


async def _get_db() -> aiosqlite.Connection:
    """Return the process-wide aiosqlite connection, opening it on first use.

    A single shared connection (instead of opening/closing a new sqlite3
    connection on every call) means every query goes through aiosqlite's
    background thread instead of blocking the bot's event loop.
    """
    global _conn
    if _conn is not None:
        return _conn
    async with _conn_lock:
        if _conn is None:
            conn = await aiosqlite.connect(config.DB_PATH, timeout=30)
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")
            await conn.execute("PRAGMA busy_timeout=30000")
            await conn.execute("PRAGMA foreign_keys=ON")
            _conn = conn
    return _conn


async def close_db():
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None


async def init_db():
    conn = await _get_db()
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS relations (
        guild_id INTEGER, user_a INTEGER, user_b INTEGER, kind TEXT,
        created_at TEXT, affection INTEGER DEFAULT 0,
        last_interaction TEXT DEFAULT '', streak INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_a, user_b, kind))"""
    )
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS profiles (
        guild_id INTEGER, user_id INTEGER,
        bio TEXT DEFAULT '', title TEXT DEFAULT '',
        privacy TEXT DEFAULT 'public',
        stopped_until TEXT DEFAULT '',
        PRIMARY KEY (guild_id, user_id))"""
    )
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS nicknames (
        guild_id INTEGER, owner_id INTEGER, target_id INTEGER, nickname TEXT,
        PRIMARY KEY (guild_id, owner_id, target_id))"""
    )
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS blocks (
        guild_id INTEGER, user_id INTEGER, blocked_id INTEGER,
        PRIMARY KEY (guild_id, user_id, blocked_id))"""
    )
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS proposals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER, from_id INTEGER, to_id INTEGER, kind TEXT,
        created_at TEXT, open INTEGER DEFAULT 1)"""
    )
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS config (
        guild_id INTEGER PRIMARY KEY,
        log_channel INTEGER,
        locked INTEGER DEFAULT 0)"""
    )
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER, actor INTEGER, target INTEGER, cmd TEXT, ts TEXT)"""
    )
    await conn.commit()
    # Best-effort migrations for older databases (e.g. upgrading from a
    # build that still had the NSFW columns/tables). Safe to run every
    # startup: each ALTER either succeeds once or fails silently forever
    # after because the column already exists.
    for alter in [
        "ALTER TABLE relations ADD COLUMN last_interaction TEXT DEFAULT ''",
        "ALTER TABLE relations ADD COLUMN streak INTEGER DEFAULT 0",
        "ALTER TABLE profiles ADD COLUMN bio TEXT DEFAULT ''",
        "ALTER TABLE profiles ADD COLUMN title TEXT DEFAULT ''",
        "ALTER TABLE profiles ADD COLUMN privacy TEXT DEFAULT 'public'",
        "ALTER TABLE profiles ADD COLUMN stopped_until TEXT DEFAULT ''",
        "ALTER TABLE config ADD COLUMN locked INTEGER DEFAULT 0",
    ]:
        try:
            await conn.execute(alter)
            await conn.commit()
        except Exception:
            pass
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_relations_a ON relations(guild_id, kind, user_a)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_relations_b ON relations(guild_id, kind, user_b)")
    await conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_open_proposal_pair
           ON proposals(guild_id, kind, MIN(from_id, to_id), MAX(from_id, to_id))
           WHERE open=1"""
    )
    await conn.commit()
    log.info("Database ready at %s", config.DB_PATH)


def now():
    return datetime.now(timezone.utc)


def now_iso():
    return now().isoformat()


def parse_iso(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def pair(a, b):
    return (min(a, b), max(a, b))


async def cfg(guild_id):
    conn = await _get_db()
    await conn.execute("INSERT OR IGNORE INTO config (guild_id) VALUES (?)", (guild_id,))
    await conn.commit()
    cur = await conn.execute("SELECT * FROM config WHERE guild_id=?", (guild_id,))
    return await cur.fetchone()


async def set_cfg(guild_id, **kwargs):
    await cfg(guild_id)
    conn = await _get_db()
    for k, v in kwargs.items():
        if k not in _CONFIG_COLUMNS:
            raise ValueError(f"Refusing to set unknown config column: {k!r}")
        await conn.execute(f"UPDATE config SET {k}=? WHERE guild_id=?", (v, guild_id))
    await conn.commit()


async def ensure_profile(gid, uid):
    conn = await _get_db()
    await conn.execute("INSERT OR IGNORE INTO profiles (guild_id, user_id) VALUES (?,?)", (gid, uid))
    await conn.commit()


async def get_profile(gid, uid):
    await ensure_profile(gid, uid)
    conn = await _get_db()
    cur = await conn.execute("SELECT * FROM profiles WHERE guild_id=? AND user_id=?", (gid, uid))
    return await cur.fetchone()


async def set_prof(gid, uid, **kwargs):
    await ensure_profile(gid, uid)
    conn = await _get_db()
    for k, v in kwargs.items():
        if k not in _PROFILE_COLUMNS:
            raise ValueError(f"Refusing to set unknown profile column: {k!r}")
        await conn.execute(f"UPDATE profiles SET {k}=? WHERE guild_id=? AND user_id=?", (v, gid, uid))
    await conn.commit()


async def wipe_user(gid, uid):
    conn = await _get_db()
    await conn.execute("DELETE FROM relations WHERE guild_id=? AND (user_a=? OR user_b=?)", (gid, uid, uid))
    await conn.execute("DELETE FROM profiles WHERE guild_id=? AND user_id=?", (gid, uid))
    await conn.execute(
        "DELETE FROM nicknames WHERE guild_id=? AND (owner_id=? OR target_id=?)", (gid, uid, uid)
    )
    await conn.execute("DELETE FROM blocks WHERE guild_id=? AND (user_id=? OR blocked_id=?)", (gid, uid, uid))
    await conn.execute("DELETE FROM proposals WHERE guild_id=? AND (from_id=? OR to_id=?)", (gid, uid, uid))
    await conn.commit()


async def export_user(gid, uid) -> dict:
    """Everything this bot stores about uid in guild gid, for /exportme."""
    conn = await _get_db()
    profile = await get_profile(gid, uid)

    cur = await conn.execute(
        "SELECT user_a, user_b, kind, created_at, affection, streak, last_interaction "
        "FROM relations WHERE guild_id=? AND (user_a=? OR user_b=?)",
        (gid, uid, uid),
    )
    relations = [dict(r) for r in await cur.fetchall()]

    cur = await conn.execute(
        "SELECT target_id, nickname FROM nicknames WHERE guild_id=? AND owner_id=?", (gid, uid)
    )
    nicknames_given = [dict(r) for r in await cur.fetchall()]

    cur = await conn.execute("SELECT blocked_id FROM blocks WHERE guild_id=? AND user_id=?", (gid, uid))
    blocked = [r["blocked_id"] for r in await cur.fetchall()]

    cur = await conn.execute(
        "SELECT id, from_id, to_id, kind, created_at, open FROM proposals "
        "WHERE guild_id=? AND (from_id=? OR to_id=?)",
        (gid, uid, uid),
    )
    proposals = [dict(r) for r in await cur.fetchall()]

    return {
        "guild_id": gid,
        "user_id": uid,
        "profile": dict(profile) if profile else None,
        "relations": relations,
        "nicknames_given": nicknames_given,
        "blocked_user_ids": blocked,
        "proposals": proposals,
    }


async def is_blocked(gid, actor, target):
    conn = await _get_db()
    cur = await conn.execute(
        "SELECT 1 FROM blocks WHERE guild_id=? AND user_id=? AND blocked_id=?",
        (gid, target, actor),
    )
    return (await cur.fetchone()) is not None


async def either_blocked(gid, a, b):
    return await is_blocked(gid, a, b) or await is_blocked(gid, b, a)


async def add_block(gid, uid, blocked):
    conn = await _get_db()
    await conn.execute("INSERT OR IGNORE INTO blocks VALUES (?,?,?)", (gid, uid, blocked))
    await conn.commit()


async def del_block(gid, uid, blocked):
    conn = await _get_db()
    await conn.execute(
        "DELETE FROM blocks WHERE guild_id=? AND user_id=? AND blocked_id=?",
        (gid, uid, blocked),
    )
    await conn.commit()


async def log_action(gid, actor, target, cmd):
    conn = await _get_db()
    await conn.execute(
        "INSERT INTO actions (guild_id, actor, target, cmd, ts) VALUES (?,?,?,?,?)",
        (gid, actor, target, cmd, now_iso()),
    )
    await conn.commit()


async def prune_actions():
    cutoff = (now() - timedelta(days=ACTION_RETENTION_DAYS)).isoformat()
    conn = await _get_db()
    cur = await conn.execute("DELETE FROM actions WHERE ts < ?", (cutoff,))
    await conn.commit()
    return cur.rowcount


async def count_kind(gid, uid, kind):
    conn = await _get_db()
    cur = await conn.execute(
        "SELECT COUNT(*) FROM relations WHERE guild_id=? AND kind=? AND (user_a=? OR user_b=?)",
        (gid, kind, uid, uid),
    )
    row = await cur.fetchone()
    return row[0]


async def are_related(gid, a, b, kind):
    ua, ub = pair(a, b)
    conn = await _get_db()
    cur = await conn.execute(
        "SELECT 1 FROM relations WHERE guild_id=? AND user_a=? AND user_b=? AND kind=?",
        (gid, ua, ub, kind),
    )
    return bool(await cur.fetchone())


async def _parent_neighbors(gid, uid):
    """Everyone directly one parent/child hop away from uid, either direction."""
    conn = await _get_db()
    cur = await conn.execute(
        """SELECT user_a, user_b FROM relations WHERE guild_id=? AND kind='parent'
           AND (user_a=? OR user_b=?)""",
        (gid, uid, uid),
    )
    rows = await cur.fetchall()
    return {r["user_b"] if r["user_a"] == uid else r["user_a"] for r in rows}


async def is_family(gid, a, b, max_depth: int = FAMILY_CHECK_DEPTH) -> bool:
    """True if a and b are connected by a chain of parent/child bonds.

    This walks the (undirected) parent/child graph breadth-first instead
    of only checking a direct pair, so it also catches grandparent/
    grandchild, siblings (shared parent), and aunt/uncle-niece/nephew
    bonds built up through chained /adopt calls, up to max_depth hops.
    """
    if a == b:
        return True
    visited = {a}
    frontier = {a}
    for _ in range(max_depth):
        next_frontier = set()
        for node in frontier:
            for neighbor in await _parent_neighbors(gid, node):
                if neighbor == b:
                    return True
                if neighbor not in visited:
                    visited.add(neighbor)
                    next_frontier.add(neighbor)
        if not next_frontier:
            break
        frontier = next_frontier
    return False


async def is_romantic(gid, a, b):
    return await are_related(gid, a, b, "married") or await are_related(gid, a, b, "dating")


async def couple_kind(gid, a, b):
    if await are_related(gid, a, b, "married"):
        return "married"
    if await are_related(gid, a, b, "dating"):
        return "dating"
    return None


async def get_partners(gid, uid, kind):
    conn = await _get_db()
    cur = await conn.execute(
        """SELECT user_a, user_b, created_at, affection, streak FROM relations
           WHERE guild_id=? AND kind=? AND (user_a=? OR user_b=?)""",
        (gid, kind, uid, uid),
    )
    rows = await cur.fetchall()
    out = []
    for r in rows:
        other = r["user_b"] if r["user_a"] == uid else r["user_a"]
        out.append(
            {
                "id": other,
                "since": r["created_at"],
                "affection": r["affection"],
                "streak": r["streak"] or 0,
            }
        )
    return out


async def add_relation(gid, a, b, kind):
    ua, ub = pair(a, b)
    conn = await _get_db()
    await conn.execute(
        "INSERT OR IGNORE INTO relations (guild_id, user_a, user_b, kind, created_at, affection) "
        "VALUES (?,?,?,?,?,0)",
        (gid, ua, ub, kind, now_iso()),
    )
    await conn.commit()


async def remove_relation(gid, a, b, kind):
    ua, ub = pair(a, b)
    conn = await _get_db()
    await conn.execute(
        "DELETE FROM relations WHERE guild_id=? AND user_a=? AND user_b=? AND kind=?",
        (gid, ua, ub, kind),
    )
    await conn.commit()


async def add_affection(gid, a, b, kind, amount=0):
    """Add affection points to a bond and bump its daily interaction streak.

    The streak increases by 1 the first time in a UTC calendar day that
    this pair interacts, stays flat on repeat interactions the same day,
    and resets to 1 if a day was skipped.
    """
    ua, ub = pair(a, b)
    conn = await _get_db()
    cur = await conn.execute(
        "SELECT last_interaction, streak FROM relations WHERE guild_id=? AND user_a=? AND user_b=? AND kind=?",
        (gid, ua, ub, kind),
    )
    row = await cur.fetchone()
    if row is None:
        return None

    today = now().date()
    last = parse_iso(row["last_interaction"])
    streak = row["streak"] or 0
    if last is None or last.date() < today - timedelta(days=1):
        streak = 1
    elif last.date() == today - timedelta(days=1):
        streak += 1
    # else: already interacted today, streak unchanged

    await conn.execute(
        """UPDATE relations SET affection=affection+?, last_interaction=?, streak=?
           WHERE guild_id=? AND user_a=? AND user_b=? AND kind=?""",
        (amount, now_iso(), streak, gid, ua, ub, kind),
    )
    await conn.commit()
    return streak


async def add_parent(gid, parent, child):
    conn = await _get_db()
    await conn.execute(
        "INSERT OR IGNORE INTO relations (guild_id, user_a, user_b, kind, created_at, affection) "
        "VALUES (?,?,?,?,?,0)",
        (gid, parent, child, "parent", now_iso()),
    )
    await conn.commit()


async def do_remove_parent(gid, parent, child) -> bool:
    conn = await _get_db()
    cur = await conn.execute(
        "DELETE FROM relations WHERE guild_id=? AND user_a=? AND user_b=? AND kind='parent'",
        (gid, parent, child),
    )
    await conn.commit()
    return cur.rowcount > 0


async def children_of(gid, pid):
    conn = await _get_db()
    cur = await conn.execute(
        "SELECT user_b, created_at FROM relations WHERE guild_id=? AND kind='parent' AND user_a=?",
        (gid, pid),
    )
    rows = await cur.fetchall()
    return [{"id": r["user_b"], "since": r["created_at"]} for r in rows]


async def parents_of(gid, cid):
    conn = await _get_db()
    cur = await conn.execute(
        "SELECT user_a, created_at FROM relations WHERE guild_id=? AND kind='parent' AND user_b=?",
        (gid, cid),
    )
    rows = await cur.fetchall()
    return [{"id": r["user_a"], "since": r["created_at"]} for r in rows]


async def set_nickname(gid, owner_id, target_id, nickname: Optional[str]):
    conn = await _get_db()
    if nickname:
        await conn.execute(
            "INSERT INTO nicknames (guild_id, owner_id, target_id, nickname) VALUES (?,?,?,?) "
            "ON CONFLICT(guild_id, owner_id, target_id) DO UPDATE SET nickname=excluded.nickname",
            (gid, owner_id, target_id, nickname),
        )
    else:
        await conn.execute(
            "DELETE FROM nicknames WHERE guild_id=? AND owner_id=? AND target_id=?",
            (gid, owner_id, target_id),
        )
    await conn.commit()


async def get_nickname(gid, owner_id, target_id) -> Optional[str]:
    conn = await _get_db()
    cur = await conn.execute(
        "SELECT nickname FROM nicknames WHERE guild_id=? AND owner_id=? AND target_id=?",
        (gid, owner_id, target_id),
    )
    row = await cur.fetchone()
    return row["nickname"] if row else None


async def has_open_proposal(gid, a, b, kind):
    conn = await _get_db()
    cur = await conn.execute(
        """SELECT 1 FROM proposals WHERE guild_id=? AND kind=? AND open=1
           AND ((from_id=? AND to_id=?) OR (from_id=? AND to_id=?))""",
        (gid, kind, a, b, b, a),
    )
    return bool(await cur.fetchone())


async def create_proposal(gid, frm, to, kind) -> Optional[int]:
    conn = await _get_db()
    try:
        cur = await conn.execute(
            "INSERT INTO proposals (guild_id, from_id, to_id, kind, created_at, open) VALUES (?,?,?,?,?,1)",
            (gid, frm, to, kind, now_iso()),
        )
        pid = cur.lastrowid
        await conn.commit()
    except sqlite3.IntegrityError:
        await conn.rollback()
        return None
    return pid


async def get_proposal(pid):
    conn = await _get_db()
    cur = await conn.execute("SELECT * FROM proposals WHERE id=?", (pid,))
    return await cur.fetchone()


async def try_close_proposal(pid) -> bool:
    conn = await _get_db()
    cur = await conn.execute("UPDATE proposals SET open=0 WHERE id=? AND open=1", (pid,))
    await conn.commit()
    return cur.rowcount == 1


async def reopen_proposal(pid) -> bool:
    conn = await _get_db()
    try:
        await conn.execute("UPDATE proposals SET open=1 WHERE id=?", (pid,))
        await conn.commit()
        return True
    except sqlite3.IntegrityError:
        await conn.rollback()
        log.warning("Could not reopen proposal %s (duplicate open pair)", pid)
        return False


async def list_married_lb(gid):
    conn = await _get_db()
    cur = await conn.execute(
        """SELECT user_id, COUNT(*) n FROM (
        SELECT user_a user_id FROM relations WHERE guild_id=? AND kind='married'
        UNION ALL SELECT user_b FROM relations WHERE guild_id=? AND kind='married')
        GROUP BY user_id ORDER BY n DESC LIMIT 10""",
        (gid, gid),
    )
    return await cur.fetchall()


async def list_affection_lb(gid):
    conn = await _get_db()
    cur = await conn.execute(
        """SELECT user_a,user_b,kind,affection FROM relations
           WHERE guild_id=? AND kind IN ('married','dating') ORDER BY affection DESC LIMIT 10""",
        (gid,),
    )
    return await cur.fetchall()


async def list_streak_lb(gid):
    conn = await _get_db()
    cur = await conn.execute(
        """SELECT user_a,user_b,kind,streak FROM relations
           WHERE guild_id=? AND kind IN ('married','dating') AND streak > 0
           ORDER BY streak DESC LIMIT 10""",
        (gid,),
    )
    return await cur.fetchall()


async def list_anniversaries_for(gid, uid):
    """All of uid's married/dating bonds, soonest upcoming anniversary first."""
    conn = await _get_db()
    cur = await conn.execute(
        """SELECT user_a, user_b, kind, created_at FROM relations
           WHERE guild_id=? AND kind IN ('married','dating') AND (user_a=? OR user_b=?)""",
        (gid, uid, uid),
    )
    rows = await cur.fetchall()
    out = []
    today = now().date()
    for r in rows:
        other = r["user_b"] if r["user_a"] == uid else r["user_a"]
        started = parse_iso(r["created_at"])
        if not started:
            continue
        this_year = started.date().replace(year=today.year)
        if this_year < today:
            try:
                this_year = this_year.replace(year=today.year + 1)
            except ValueError:
                # Feb 29 on a non-leap upcoming year; push to Mar 1.
                this_year = this_year.replace(month=3, day=1, year=today.year + 1)
        days_away = (this_year - today).days
        out.append(
            {
                "id": other,
                "kind": r["kind"],
                "since": r["created_at"],
                "days_away": days_away,
            }
        )
    out.sort(key=lambda x: x["days_away"])
    return out


async def list_actions(gid, uid, limit=15):
    conn = await _get_db()
    cur = await conn.execute(
        """SELECT cmd, actor, target, ts FROM actions
           WHERE guild_id=? AND (actor=? OR target=?) ORDER BY id DESC LIMIT ?""",
        (gid, uid, uid, limit),
    )
    return await cur.fetchall()


def _do_backup_sync(dest_path: str):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    src = sqlite3.connect(config.DB_PATH)
    dest = sqlite3.connect(dest_path)
    try:
        with dest:
            src.backup(dest)
    finally:
        src.close()
        dest.close()


def _prune_backups_sync():
    files = sorted(glob.glob(os.path.join(config.BACKUP_DIR, "relationships-*.db")))
    excess = len(files) - config.BACKUP_KEEP
    for f in files[: max(excess, 0)]:
        try:
            os.remove(f)
        except OSError:
            pass


async def backup_db() -> str:
    """Snapshot the live DB into BACKUP_DIR using SQLite's online backup
    API, then prune old snapshots down to BACKUP_KEEP. Runs in a worker
    thread (via asyncio.to_thread) so it never blocks the event loop, and
    opens its own plain sqlite3 connections rather than reusing the
    shared aiosqlite one, so a slow backup can't stall live commands.
    """
    dest_path = os.path.join(config.BACKUP_DIR, f"relationships-{now().strftime('%Y%m%dT%H%M%SZ')}.db")
    await asyncio.to_thread(_do_backup_sync, dest_path)
    await asyncio.to_thread(_prune_backups_sync)
    return dest_path
