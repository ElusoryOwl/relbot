RelBot

Discord relationship bot for 18+ servers. Dating, marriage (polygamy), family bonds, opt-in NSFW scenes, profiles, and staff tools.

Data is stored per server in SQLite. Lewd commands only work in NSFW channels, after both people opt in, and only if both have the configured adult role.

Features

Date / marry / divorce / break up (multiple partners, configurable caps)
Adopt / disown (lewd commands blocked across family bonds, not just direct parent/child — see "Family safety check" below)
Opt-in NSFW commands with intensity, heat/lust, aftercare
Kink card, limits, safeword, titles, free-use flag
Separate privacy for lewd output vs profile visibility
Block list, /stop, /forgetme
Leaderboards and staff lock / wipe / log channel / on-demand backup

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
│   ├── lines.py
│   ├── proposals.py
│   └── cogs/
│       ├── admin.py
│       ├── bonds.py
│       ├── leaderboards.py
│       ├── lewd.py
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

Server setup

Invite the bot with bot + applications.commands.
Create an adult role (default name: 18+).
Prefer setting it by ID: /reladmin action:set-adult-role role:@18+
Mark lewd channels as NSFW.
In a staff channel: /reladmin action:set-log-here
Tell members to /optin before using lewd commands.

Member commands

Safety
| Command | What it does |
|---|---|
| /optin | Allow lewd commands on you |
| /optout | Turn off lewd + free-use |
| /forgetme | Delete your data in this server |
| /stop | Freeze lewd involving you for 30 minutes |
| /block /unblock | Block proposals and lewd from someone |
| /privacy | Public vs ephemeral lewd output |
| /profileprivacy | Hide kinks/limits on your card |
| /freeuse | Strangers who opted in can use lewd on you |
| /setsafeword | Safeword shown on profile |

Bonds
| Command | What it does |
|---|---|
| /date | Dating proposal (buttons) |
| /marry | Marriage proposal (up to 8 spouses) |
| /divorce /breakup | End a bond |
| /adopt /disown | Family bond (blocks lewd across the whole family chain, see below) |
| /relationship | Full profile |

Profiles
/settitle /setkinks /setlimits /kinks

Lewd (NSFW channel + adult role + opt-in)
/fuck /tease /spank /blow /ride /breed /claim /leash /kiss /hug /scene /aftercare

/fuck takes intensity: vanilla, rough, degrading.
/aftercare only works if you two shared a lewd command in the last 2 hours.
Proposals (/date, /marry, /adopt) share a short per-user cooldown so one person can't blast invites at many targets back to back.

Other
/compatibility /marriedlb /lustlb /heatlb /relhelp

Staff: /reladmin

Needs Manage Server.

| Action | Effect |
|---|---|
| lock-lewd / unlock-lewd | Kill switch for lewd commands |
| set-log-here | Staff log channel |
| set-adult-role | Adult role by ID (preferred) |
| set-adult-role-name | Fallback if you only have a name |
| stranger-scene-on/off | Whether /scene works without dating/marriage |
| force-break | Remove dating/marriage between two members |
| wipe-user | Delete that member's bot data here |
| relinfo | Recent actions + flags |
| backup-now | Snapshot the DB to /data/backups immediately |

Family safety check

Lewd commands and family-adjacent proposals (/marry, /date, /adopt) are blocked
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
| ADULT_ROLE_NAME | 18+ | Used if no role ID is set |
| LEWD_COOLDOWN_SEC | 25 | Per-user lewd cooldown |
| PROPOSAL_COOLDOWN_SEC | 10 | Per-user cooldown between /date, /marry, /adopt |
| HEAT_DECAY_PER_HOUR | 8 | Heat drain |
| STOP_MINUTES | 30 | /stop duration |
| ACTION_RETENTION_DAYS | 30 | Staff action log prune |
| FAMILY_CHECK_DEPTH | 4 | Parent/child hops counted as "family" for lewd blocking |
| BACKUP_DIR | <DB dir>/backups | Where scheduled/manual backups are written |
| BACKUP_INTERVAL_HOURS | 24 | How often the automatic backup runs |
| BACKUP_KEEP | 7 | How many backup snapshots to keep |
| HEARTBEAT_PATH | <DB dir>/heartbeat | File the Docker healthcheck watches |

Backups

The maintenance cog snapshots the live database into BACKUP_DIR once a day
using SQLite's own online backup API (safe to run against a live WAL
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
block-list symmetry, /forgetme's full data wipe, and the backup routine —
i.e. the logic that actually enforces consent and age gating, not just
string helpers.

Notes

SQLite access now goes through a single shared aiosqlite connection
instead of opening a new blocking connection per call, so DB work no
longer stalls the bot's event loop under load. It's still one SQLite file
per process — if you ever need to run more than one bot process against
the same database (horizontal scaling, sharding), move to a real
client-server database instead.

Per-user command cooldowns (lewd and proposal) are still kept in an
in-memory dict rather than the database or an external cache. That's a
deliberate trade-off for this project's target scale (one process, one
or a few servers): it avoids adding a Redis/Memcached dependency, at the
cost of cooldowns resetting on restart and not being shareable across
more than one bot process. If you outgrow a single process, that's the
piece to swap out.

/forgetme and staff wipe delete bonds, profile, blocks, and proposals in that guild only. The action log still records that a wipe happened.
Token stays in .env (never .env.example, and never commit .env). Do not commit it.
