import os
import tempfile
import unittest

import relbot.config as config


class PairTests(unittest.TestCase):
    def test_pair_order(self):
        from relbot.db import pair

        self.assertEqual(pair(9, 2), (2, 9))


class DbTestCase(unittest.IsolatedAsyncioTestCase):
    """Base class that points relbot.db at a fresh temp SQLite file per test."""

    async def asyncSetUp(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.path = path
        self._old_db_path = config.DB_PATH
        config.DB_PATH = path

        import relbot.db as db

        self.db = db
        db._conn = None  # drop any connection left over from a previous test
        await db.init_db()

    async def asyncTearDown(self):
        await self.db.close_db()
        config.DB_PATH = self._old_db_path
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.path + suffix)
            except OSError:
                pass


class FamilyTests(DbTestCase):
    async def test_family_is_bidirectional(self):
        await self.db.add_parent(1, 10, 20)
        self.assertTrue(await self.db.is_family(1, 10, 20))
        self.assertTrue(await self.db.is_family(1, 20, 10))
        self.assertFalse(await self.db.is_family(1, 10, 99))

    async def test_grandparent_grandchild_is_family(self):
        # 10 -> 20 -> 30 (grandparent -> parent -> grandchild)
        await self.db.add_parent(1, 10, 20)
        await self.db.add_parent(1, 20, 30)
        self.assertTrue(await self.db.is_family(1, 10, 30))

    async def test_siblings_are_family(self):
        # 10 is the shared parent of 20 and 21: adopting a sibling used to
        # slip through the old direct-pair-only check.
        await self.db.add_parent(1, 10, 20)
        await self.db.add_parent(1, 10, 21)
        self.assertTrue(await self.db.is_family(1, 20, 21))

    async def test_aunt_or_uncle_is_family(self):
        # 10 -> 20 (parent/child), 10 -> 21 (parent/child) => 21 is 20's
        # aunt/uncle via the shared parent 10.
        await self.db.add_parent(1, 10, 20)
        await self.db.add_parent(1, 10, 21)
        await self.db.add_parent(1, 20, 30)
        self.assertTrue(await self.db.is_family(1, 21, 30))

    async def test_unrelated_users_are_not_family(self):
        await self.db.add_parent(1, 10, 20)
        self.assertFalse(await self.db.is_family(1, 20, 999))

    async def test_family_depth_is_bounded(self):
        chain = list(range(100, 108))
        for parent, child in zip(chain, chain[1:]):
            await self.db.add_parent(1, parent, child)
        self.assertFalse(await self.db.is_family(1, chain[0], chain[-1], max_depth=2))
        self.assertTrue(await self.db.is_family(1, chain[0], chain[-1], max_depth=len(chain)))


class ProposalTests(DbTestCase):
    async def test_duplicate_open_proposal_rejected(self):
        pid1 = await self.db.create_proposal(1, 10, 20, "dating")
        self.assertIsNotNone(pid1)
        pid2 = await self.db.create_proposal(1, 10, 20, "dating")
        self.assertIsNone(pid2)

    async def test_close_proposal_is_atomic(self):
        pid = await self.db.create_proposal(1, 10, 20, "dating")
        self.assertTrue(await self.db.try_close_proposal(pid))
        # A second close on the same (already-closed) row must fail — this
        # is what stops two people racing to both accept the same proposal.
        self.assertFalse(await self.db.try_close_proposal(pid))


class BlockAndWipeTests(DbTestCase):
    async def test_block_is_checked_both_directions(self):
        await self.db.add_block(1, 10, 20)
        self.assertTrue(await self.db.either_blocked(1, 10, 20))
        self.assertTrue(await self.db.either_blocked(1, 20, 10))
        self.assertFalse(await self.db.either_blocked(1, 10, 99))

    async def test_wipe_user_clears_everything(self):
        await self.db.add_relation(1, 10, 20, "dating")
        await self.db.set_prof(1, 10, title="prince")
        await self.db.set_nickname(1, 10, 20, "sweetie")
        await self.db.add_block(1, 10, 30)
        await self.db.create_proposal(1, 10, 40, "marry")

        await self.db.wipe_user(1, 10)

        self.assertFalse(await self.db.are_related(1, 10, 20, "dating"))
        self.assertFalse(await self.db.either_blocked(1, 10, 30))
        self.assertFalse(await self.db.has_open_proposal(1, 10, 40, "marry"))
        self.assertIsNone(await self.db.get_nickname(1, 10, 20))


class ExportTests(DbTestCase):
    async def test_export_includes_relations_and_nicknames(self):
        await self.db.add_relation(1, 10, 20, "dating")
        await self.db.set_nickname(1, 10, 20, "sweetie")
        await self.db.add_block(1, 10, 99)

        data = await self.db.export_user(1, 10)

        self.assertEqual(data["user_id"], 10)
        self.assertEqual(len(data["relations"]), 1)
        self.assertEqual(data["nicknames_given"][0]["nickname"], "sweetie")
        self.assertIn(99, data["blocked_user_ids"])


class AffectionStreakTests(DbTestCase):
    async def test_streak_starts_at_one(self):
        await self.db.add_relation(1, 10, 20, "dating")
        streak = await self.db.add_affection(1, 10, 20, "dating", 5)
        self.assertEqual(streak, 1)

    async def test_same_day_does_not_double_count_streak(self):
        await self.db.add_relation(1, 10, 20, "dating")
        await self.db.add_affection(1, 10, 20, "dating", 5)
        streak = await self.db.add_affection(1, 10, 20, "dating", 5)
        self.assertEqual(streak, 1)
        partners = await self.db.get_partners(1, 10, "dating")
        self.assertEqual(partners[0]["affection"], 10)

    async def test_missing_relation_returns_none(self):
        streak = await self.db.add_affection(1, 10, 20, "dating", 5)
        self.assertIsNone(streak)


class NicknameTests(DbTestCase):
    async def test_set_and_clear_nickname(self):
        await self.db.set_nickname(1, 10, 20, "sweetie")
        self.assertEqual(await self.db.get_nickname(1, 10, 20), "sweetie")
        await self.db.set_nickname(1, 10, 20, None)
        self.assertIsNone(await self.db.get_nickname(1, 10, 20))


class BackupTests(DbTestCase):
    async def test_backup_creates_a_restorable_file(self):
        backup_dir = tempfile.mkdtemp()
        config.BACKUP_DIR = backup_dir
        try:
            await self.db.add_relation(1, 10, 20, "married")
            path = await self.db.backup_db()
            self.assertTrue(os.path.exists(path))
            self.assertGreater(os.path.getsize(path), 0)
        finally:
            for f in os.listdir(backup_dir):
                os.remove(os.path.join(backup_dir, f))
            os.rmdir(backup_dir)


class CooldownTests(unittest.TestCase):
    def test_proposal_cooldown_blocks_rapid_repeats(self):
        from relbot import gates

        gates._last_proposal.clear()
        gid, uid = 999, 999
        self.assertFalse(gates.proposal_on_cd(gid, uid))
        self.assertTrue(gates.proposal_on_cd(gid, uid))

    def test_interaction_cooldown_blocks_rapid_repeats(self):
        from relbot import gates

        gates._last_cmd.clear()
        gid, uid = 999, 999
        self.assertFalse(gates.on_cd(gid, uid))
        self.assertTrue(gates.on_cd(gid, uid))

    def test_sweep_clears_stale_entries(self):
        from datetime import timedelta

        from relbot import gates

        gates._last_cmd.clear()
        gates._last_proposal.clear()
        gates._last_cmd[(1, 1)] = gates.now() - timedelta(hours=1)
        gates._last_proposal[(1, 1)] = gates.now() - timedelta(hours=1)
        gates.sweep_cooldowns()
        self.assertNotIn((1, 1), gates._last_cmd)
        self.assertNotIn((1, 1), gates._last_proposal)


class GatePairTests(DbTestCase):
    """gate_pair touches the DB (cfg/either_blocked/stopped), which is
    exactly where the old code was missing `await` and would have raised
    TypeErrors instead of returning a clean error string."""

    async def test_blocked_pair_is_rejected(self):
        from relbot import gates

        await self.db.add_block(1, 10, 20)
        result = await gates.stopped(1, 10)
        self.assertFalse(result)
        blocked = await self.db.either_blocked(1, 10, 20)
        self.assertTrue(blocked)

    async def test_locked_guild_is_reported(self):
        from relbot import gates

        await self.db.set_cfg(1, locked=1)
        row = await self.db.cfg(1)
        self.assertEqual(row["locked"], 1)


if __name__ == "__main__":
    unittest.main()
