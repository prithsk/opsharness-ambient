"""Ambient personal assistant (Moonshot-style).

The agent reads a day of transcribed conversation and turns real open
loops into reminders and calendar events. Distractors include other
people's promises, hypotheticals, declined asks, and loops the user closed
later the same day. Dates are relative ("by Thursday"), so the agent has
to resolve them against today, Monday 2026-09-28. The transcript is paged,
so an agent that reads one page misses items.
"""
from datetime import date, timedelta

from opsharness.core import Env, Tool, ToolError, f1

TODAY = date(2026, 9, 28)  # Monday
WEEKDAYS = ["Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
NAMES = ["Maya", "Jordan", "Priya", "Sam", "Leo", "Nadia", "Chris", "Ava"]
DOCS = ["budget draft", "slide deck", "lease scan", "trip itinerary", "design mockups", "signed form"]
THINGS = ["the cake", "the dry cleaning", "a birthday card", "the package at the post office"]
APPTS = [("Dentist office", "cleaning"), ("Dr. Ruiz's office", "checkup"), ("Garage", "oil change"),
         ("Barber", "haircut")]
PAGE = 12


def wd(name):
    return (TODAY + timedelta(days=WEEKDAYS.index(name) + 1)).isoformat()


class AmbientEnv(Env):
    name = "ambient"

    def build(self):
        r = self.rng
        blocks, self.truth = [], []  # truth: (kind, anchor ids, date or datetime)
        names, docs = iter(r.sample(NAMES, len(NAMES))), iter(r.sample(DOCS, len(DOCS)))
        kinds = r.sample(["commit_weekday", "accepted_request", "appointment", "commit_tomorrow"], 3)
        for k in kinds:
            n, day = next(names), r.choice(WEEKDAYS)
            if k == "commit_weekday":
                doc = next(docs)
                blocks.append(([(n, f"Any update on the {doc}?"), ("me", f"I'll send you the {doc} by {day}.")],
                               ("reminder", [1], wd(day))))
            elif k == "accepted_request":
                thing = r.choice(THINGS)
                blocks.append(([(n, f"Could you pick up {thing} on {day}?"), ("me", "Yeah, I'll do it.")],
                               ("reminder", [0, 1], wd(day))))
            elif k == "appointment":
                who, what = r.choice(APPTS)
                h, mm = r.choice([(9, 15), (10, 30), (14, 0), (15, 30), (16, 45)])
                hh = h if h <= 12 else h - 12
                ampm = "am" if h < 12 else "pm"
                blocks.append(([(who, f"Hi, calling to confirm we moved your {what} to {day} at {hh}:{mm:02d} {ampm}."),
                                ("me", "Great, thanks, that works.")],
                               ("event", [0, 1], f"{wd(day)}T{h:02d}:{mm:02d}")))
            else:
                n2 = next(names)
                blocks.append(([("me", f"I'll call {n2} tomorrow about the deposit.")],
                               ("reminder", [0], (TODAY + timedelta(days=1)).isoformat())))
        # distractors
        blocks.append(([(next(names), f"I'll book the table for {r.choice(WEEKDAYS)}, don't worry about it.")], None))
        blocks.append(([("me", f"If I had more time I'd redo the {next(docs)} from scratch.")], None))
        blocks.append(([(next(names), f"Can you drive me to the airport on {r.choice(WEEKDAYS)}?"),
                        ("me", "I can't this week, sorry.")], None))
        blocks.append(([("me", f"I already sent the {next(docs)} to {next(names)} this morning.")], None))
        closer_name, doc = next(names), next(docs)
        # a loop the user opens and then closes later the same day
        self._closer = (closer_name, doc)
        filler = ["Traffic was terrible this morning.", "Did you see the game last night?", "I need more coffee.",
                  "The new place on Main has good tacos.", "Can you hear me okay?", "Let me grab my charger.",
                  "It's supposed to rain all week.", "Okay, where were we?"]
        r.shuffle(blocks)
        items = []
        for b in blocks:
            items.append(b)
            if r.random() < 0.6:
                items.append(([(r.choice(NAMES + ["me"]), r.choice(filler))], None))
        open_at = r.randint(0, len(items) // 2)
        close_at = r.randint(len(items) // 2 + 1, len(items))
        items.insert(close_at, ([("me", f"Okay, just emailed {closer_name} the {doc}.")], None))
        items.insert(open_at, ([("me", f"I'll email {closer_name} the {doc} today.")], None))

        self.utts, minute = [], 8 * 60 + r.randint(0, 30)
        for lines, label in items:
            ids = []
            for speaker, text in lines:
                uid = f"u{len(self.utts) + 1}"
                self.utts.append({"id": uid, "time": f"{minute // 60:02d}:{minute % 60:02d}",
                                  "speaker": speaker, "text": text})
                ids.append(uid)
                minute += r.randint(1, 4)
            minute += r.randint(10, 60)
            if label:
                kind, idx, when = label
                self.truth.append((kind, {ids[i] for i in idx}, when))
        self.reminders, self.events = [], []

    # ---- tools -----------------------------------------------------------
    def get_transcript(self, page=1):
        pages = (len(self.utts) + PAGE - 1) // PAGE
        if page < 1 or page > pages:
            raise ToolError(f"page must be between 1 and {pages}")
        return {"date": TODAY.isoformat(), "weekday": "Monday", "page": page, "pages": pages,
                "utterances": self.utts[(page - 1) * PAGE: page * PAGE]}

    def _ids(self, source_ids):
        known = {u["id"] for u in self.utts}
        bad = [s for s in source_ids if s not in known]
        if bad or not source_ids:
            raise ToolError(f"source_ids must be utterance ids from the transcript, got {source_ids}")

    def create_reminder(self, text, due_date, source_ids):
        self._ids(source_ids)
        try:
            date.fromisoformat(due_date)
        except ValueError:
            raise ToolError("due_date must be YYYY-MM-DD") from None
        self.reminders.append({"text": text, "due_date": due_date, "source_ids": source_ids})
        return {"status": "created", "reminder": len(self.reminders)}

    def create_event(self, title, start, source_ids):
        self._ids(source_ids)
        s = start.strip()[:16]
        try:
            date.fromisoformat(s[:10])
            h, m = int(s[11:13]), int(s[14:16])
            assert s[10] == "T" and 0 <= h < 24 and 0 <= m < 60
        except (ValueError, AssertionError, IndexError):
            raise ToolError("start must look like YYYY-MM-DDTHH:MM") from None
        self.events.append({"title": title, "start": s, "source_ids": source_ids})
        return {"status": "created", "event": len(self.events)}

    def env_tools(self):
        s = {"type": "string"}
        ids = {"type": "array", "items": s, "description": "Utterance ids this item came from."}
        return [
            Tool("get_transcript", "One page of today's transcript. Check 'pages' to see how many exist.",
                 {"page": {"type": "integer"}}, self.get_transcript),
            Tool("create_reminder", "Create a reminder for the user.",
                 {"text": s, "due_date": {"type": "string", "description": "YYYY-MM-DD"}, "source_ids": ids},
                 self.create_reminder, ["text", "due_date", "source_ids"]),
            Tool("create_event", "Put an appointment on the user's calendar.",
                 {"title": s, "start": {"type": "string", "description": "YYYY-MM-DDTHH:MM, local time"},
                  "source_ids": ids},
                 self.create_event, ["title", "start", "source_ids"]),
        ]

    def task(self):
        return ("Go through today's full transcript and set up reminders and calendar events for the user's "
                "real open loops. Today is Monday 2026-09-28.")

    # ---- answer key and scoring -------------------------------------------
    def oracle_plan(self):
        plan = []
        for kind, anchors, when in self.truth:
            src = sorted(anchors)
            if kind == "reminder":
                plan.append(("create_reminder", {"text": "follow up", "due_date": when, "source_ids": src}))
            else:
                plan.append(("create_event", {"title": "appointment", "start": when, "source_ids": src}))
        return plan

    def score(self):
        made = [("reminder", set(x["source_ids"]), x["due_date"]) for x in self.reminders] + \
               [("event", set(x["source_ids"]), x["start"]) for x in self.events]
        open_truth = list(self.truth)
        tp = fp = 0
        for kind, src, when in made:
            hit = next((t for t in open_truth if t[0] == kind and t[1] & src and t[2] == when), None)
            if hit:
                tp += 1
                open_truth.remove(hit)
            else:
                fp += 1
        fn = len(open_truth)
        return {"score": round(f1(tp, fp, fn), 4),
                "details": {"tp": tp, "fp": fp, "fn": fn, "planted": len(self.truth),
                            "utterances": len(self.utts)}}
