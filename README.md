RelBot

A friendly, SFW Discord relationship bot: dating, marriage (polygamy),
family bonds, affection interactions, streaks, and staff tools. No
NSFW content of any kind. Data is stored per server in SQLite.

Features

Date / marry / divorce / break up (multiple partners, configurable caps)
Adopt / disown (romantic bonds blocked across family bonds, not just direct
  parent/child — see "Family safety check" below)
SFW affection commands (hug, cuddle, pat, kiss-on-the-cheek, poke, high-five,
  compliment) that build affection points and a daily interaction streak
  between dating/married pairs
Anniversary tracking, nicknames, bio/title profile fields
Block list, /stop (pause proposals & interactions involving you),
  /forgetme (with confirmation), /exportme (download your own data)
Leaderboards, staff lock / log channel / force-break / wipe / relinfo /
  on-demand backup

Requirements

Python 3.12+ or Docker
A Discord bot application with:
  Privileged intents: Message Content, Server Members
  OAuth2 scopes: bot, applications.commands

Project layout

.
├── Dockerfile
├── docker-compose.yml
├── main.py
├── requirements.txt
├── .env.example
├── relbot/
│   ├── bot.py
│   ├── config.py
│   ├── db.py
│   ├── gates.py
│   ├── healthcheck.py
│   ├── media.py
│   ├── proposals.py
│   ├── views.py
│   └── cogs/
│       ├── admin.py
│       ├── affection.py
│       ├── bonds.py
│       ├── leaderboards.py
│       ├── maintenance.py
│       ├── profiles.py
│       └── safety.py
└── tests/
    └── test_helpers.py

Quick start (Docker)

Copy the env template and fill in your token:

cp .env.example .env
# edit .env: DISCORD_TOKEN=your-real-token

Build and run:

docker compose up -d --build
docker compose logs -f

SQLite lives in the relbot-data volume at /data/relationships.db. Rebuilds do not wipe marriages. Backups land in /data/backups inside the same volume (see "Backups" below).

Stop:

docker compose down

down keeps the volume. To wipe data as well:

docker compose down -v

Quick start (local)

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then edit DISCORD_TOKEN in it, or export it directly
export DISCORD_TOKEN=your-bot-token
python main.py

Optional: export DB_PATH=/path/to/relationships.db
Optional (dev): export TEST_GUILD_ID=your-test-server-id to get instant
slash-command sync in one server instead of waiting up to an hour for the
global sync.

Server setup

Invite the bot with bot + applications.commands.
In a staff channel: /reladmin action:set-log-here

Member commands

Safety
| Command | What it does |
|---|---|
| /forgetme | Delete your data in this server (asks for confirmation) |
| /exportme | Download a JSON copy of everything stored about you here |
| /stop | Pause proposals and interactions involving you for 30 minutes |
| /block /unblock | Block proposals and interactions from someone |

Bonds
| Command | What it does |
|---|---|
| /date | Dating proposal (buttons) |
| /marry | Marriage proposal (up to 8 spouses) |
| /divorce /breakup | End a bond |
| /adopt /disown | Family bond |
| /relationship | Full profile: bonds, streaks, bio, nicknames |
| /anniversaries | Your dating/marriage anniversaries, soonest first |

Profile
/settitle /setbio /nickname /privacy

Affection (SFW, no channel/role restrictions)
/hug /cuddle /pat /kiss /poke /highfive /compliment

Affection commands toward a partner (dating or married) add affection
points and bump a daily interaction streak — the first time you two
interact on a given UTC day it goes up by one; using more commands that
same day doesn't inflate it further, and skipping a day resets it. Used
on someone who isn't a partner, they're just a friendly, free-standing
gesture with no stats attached.

Proposals (/date, /marry, /adopt) share a short per-user cooldown so one person can't blast invites at many targets back to back. Affection commands share a separate, shorter per-user cooldown to stop spam-farming affection.

Other
/compatibility /marriedlb /affectionlb /streaklb /relhelp

Staff: /reladmin

Needs Manage Server.

| Action | Effect |
|---|---|
| lock / unlock | Kill switch for all bond/affection commands |
| set-log-here | Staff log channel |
| force-break | Remove dating/marriage between two members |
| wipe-user | Delete that member's bot data here (asks for confirmation) |
| relinfo | Recent actions + basic profile info |
| backup-now | Snapshot the DB to /data/backups immediately |

Family safety check

Romantic proposals and adoption (/marry, /date, /adopt) are blocked
whenever two members are connected by a chain of parent/child bonds, not just
when one is the other's direct parent. The check walks the parent/child graph
breadth-first up to FAMILY_CHECK_DEPTH hops (default 4), so it also catches
grandparent/grandchild, siblings who share a parent, and aunt/uncle-niece/
nephew bonds built up through chained /adopt calls — not only the immediate
pair. Raise or lower FAMILY_CHECK_DEPTH if your server's family trees run
deeper or you want a tighter/looser definition of "family."

Config constants

Edit relbot/config.py, or set these as environment variables:

| Name | Default | Meaning |
|---|---|---|
| MAX_SPOUSES | 8 | Marriage cap |
| MAX_DATING | 5 | Dating cap |
| DB_PATH | relationships.db or env | SQLite file |
| INTERACTION_COOLDOWN_SEC | 15 | Per-user cooldown on affection commands |
| PROPOSAL_COOLDOWN_SEC | 10 | Per-user cooldown between /date, /marry, /adopt |
| STOP_MINUTES | 30 | /stop duration |
| ACTION_RETENTION_DAYS | 30 | Staff action log prune |
| FAMILY_CHECK_DEPTH | 4 | Parent/child hops counted as "family" |
| BACKUP_DIR | <DB dir>/backups | Where scheduled/manual backups are written |
| BACKUP_INTERVAL_HOURS | 24 | How often the automatic backup runs |
| BACKUP_KEEP | 7 | How many backup snapshots to keep |
| HEARTBEAT_PATH | <DB dir>/heartbeat | File the Docker healthcheck watches |
| TEST_GUILD_ID | unset | Dev-only: sync commands to one guild instantly |

Backups

The maintenance cog snapshots the live database into BACKUP_DIR once a
day using SQLite's own online backup API (safe to run against a live WAL
database), then deletes old snapshots past BACKUP_KEEP. Staff can also
trigger one immediately with /reladmin action:backup-now. In Docker,
BACKUP_DIR defaults to /data/backups, which lives inside the same
relbot-data volume as the main database, so `docker compose down -v` wipes
both together — copy files out of the volume (or point BACKUP_DIR
elsewhere) if you want backups to survive a full teardown.

Tests

python -m unittest tests.test_helpers

Covers the multi-hop family check (parent/child, grandparent, siblings,
aunt/uncle, and a depth-limit boundary case), atomic proposal accept/close,
block-list symmetry, /forgetme's full data wipe, /exportme's payload,
nicknames, the daily affection streak logic, both cooldown trackers
(including the sweep that keeps them from growing forever), and the
backup routine.

Notes

SQLite access goes through a single shared aiosqlite connection instead
of opening a new blocking connection per call, so DB work doesn't stall
the bot's event loop under load. It's still one SQLite file per process —
if you ever need to run more than one bot process against the same
database (horizontal scaling, sharding), move to a real client-server
database instead.

Per-user command cooldowns (affection and proposal) are kept in an
in-memory dict rather than the database or an external cache. That's a
deliberate trade-off for this project's target scale (one process, one
or a few servers): it avoids adding a Redis/Memcached dependency, at the
cost of cooldowns resetting on restart and not being shareable across
more than one bot process. If you outgrow a single process, that's the
piece to swap out.

/forgetme and staff wipe-user both ask for confirmation via a button
before deleting anything, and delete bonds, profile, nicknames, blocks,
and proposals in that guild only. The action log still records that a
wipe happened. /exportme gives members a self-service way to see exactly
what's stored about them before deciding whether to use /forgetme.

If you're upgrading an existing database from an older build that had
NSFW commands, the old columns for that (kinks, limits, safeword, heat,
freeuse, etc.) are simply left unused in the SQLite file; nothing reads
or writes them anymore, and nothing needs to be dropped manually.

Token stays in .env (never .env.example, and never commit .env). Do not commit it.
