"""Tests for the ambient world.

WorldContract (from the opsharness core) checks the generic promises: the
correct plan scores 1.0, doing nothing scores 0.0, approvals get enforced,
the harness survives injected model slips, and the world scores 1.0 over MCP.
The wrong agents below are ambient-specific mistakes a real model could make,
and each one has to lose points.
"""
from datetime import date, timedelta

import unittest

from opsharness.testing import WorldContract, play, strip_approvals
from opsharness_ambient.world import TODAY, AmbientEnv

SEEDS = range(100)


class Contract(WorldContract, unittest.TestCase):
    world = AmbientEnv


class WrongAgents(unittest.TestCase):
    def test_ambient_every_ill_statement(self):
        for s in SEEDS:
            env = AmbientEnv(s)
            plan = env.oracle_plan()
            anchored = set().union(*[t[1] for t in env.truth])
            for u in env.utts:
                if u["speaker"] == "me" and "I'll" in u["text"] and u["id"] not in anchored:
                    plan.append(("create_reminder", {"text": u["text"], "due_date": "2026-09-28",
                                                     "source_ids": [u["id"]]}))
            self.assertLess(play(env, plan)["score"], 1.0, f"seed {s}")
    def test_ambient_reads_only_page_one(self):
        hit = 0
        for s in SEEDS:
            env = AmbientEnv(s)
            page1 = {u["id"] for u in env.utts[:12]}
            plan = [(t, a) for t, a in env.oracle_plan() if set(a["source_ids"]) & page1]
            if len(plan) < len(env.truth):
                hit += 1
                self.assertLess(play(env, plan)["score"], 1.0, f"seed {s}")
        self.assertGreater(hit, 10)
    def test_ambient_weekday_off_by_a_week(self):
        for s in SEEDS:
            env = AmbientEnv(s)
            plan = []
            for t, a in env.oracle_plan():
                if t == "create_reminder" and a["due_date"] != (TODAY + timedelta(days=1)).isoformat():
                    a = {**a, "due_date": (date.fromisoformat(a["due_date"]) + timedelta(days=7)).isoformat()}
                if t == "create_event":
                    a = {**a, "start": (date.fromisoformat(a["start"][:10]) + timedelta(days=7)).isoformat()
                         + a["start"][10:]}
                plan.append((t, a))
            if plan != env.oracle_plan():
                self.assertLess(play(env, plan)["score"], 1.0, f"seed {s}")


if __name__ == "__main__":
    unittest.main()
