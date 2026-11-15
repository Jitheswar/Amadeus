"""Goals: work Amadeus carries on by itself until it is done, checked, or needs the user.

A goal runs as a series of ordinary requests, each through the same enforcement point
and under the mode the user chose when starting it. Between rounds only a short list of
progress notes is kept, so a long goal does not grow a long conversation, and the
record on disk is enough to carry on after a restart."""
import json, re, threading, time, uuid
from . import config, audit

ID = re.compile(r"[a-z0-9]{6,12}")
MODES = ("ask", "sandbox", "auto")       # full access is confirmed per request, so never for unattended work
MAX_NOTES, NOTE_CHARS, MAX_ACTIVE = 12, 400, 3
LOCK = threading.RLock()

WORK = """You are working on a goal the user gave you, on your own, over several rounds. Each round starts fresh: \
only the notes below carry over, so write what the next round needs.

Goal: {text}

Notes from earlier rounds:
{notes}

Do the next useful part now. Then call goal_update exactly once before you stop:
- status "progress" with a note of what you did and what comes next, if more remains;
- status "blocked" with one question, if only the user can decide or approve something;
- status "finished" with a summary, if the whole goal is met.
A denied permission is an answer: report it as blocked, do not look for another way."""

VERIFY = """A previous round reported this goal finished. Check it independently by inspecting the real state of the system; \
do not trust the notes.

Goal: {text}

Notes:
{notes}

Change nothing unless something small is missing. Then call goal_update once: status "finished" with what you verified, \
or status "progress" with what is still wrong."""


class Quiet:
    """Stands in for a client connection: a goal has nobody watching its events."""
    alive, interactive = False, False

    def event(self, *a):
        pass


def path(ident):
    if not isinstance(ident, str) or not ID.fullmatch(ident):
        raise ValueError("no such goal")
    return config.DATA / "goals" / (ident + ".json")


def load(ident):
    try:
        return json.loads(path(ident).read_text())
    except (OSError, ValueError):
        raise ValueError("no such goal")


def store(goal):
    path(goal["id"]).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    config._atomic_config(path(goal["id"]), json.dumps(goal, indent=2, ensure_ascii=False))
    return goal


def listing():
    found = []
    for f in sorted((config.DATA / "goals").glob("*.json")):
        try:
            found.append(json.loads(f.read_text()))
        except (OSError, ValueError):
            continue
    return sorted(found, key=lambda g: -g.get("created", 0))


def note(goal, text):
    goal["notes"] = (goal["notes"] + [" ".join(str(text).split())[:NOTE_CHARS]])[-MAX_NOTES:]


def update(ident, status, text):
    """What a round reports about its own goal, through the goal_update tool."""
    if status not in ("progress", "blocked", "finished") or not str(text).strip():
        raise ValueError("status is progress, blocked or finished, with a note")
    with LOCK:
        goal = load(ident)
        if goal["state"] != "working":
            raise ValueError("this goal is not being worked on")
        note(goal, text)
        goal["reported"] = status
        return store(goal)["reported"]


def start(daemon, text, provider=None, mode="ask"):
    text = " ".join(str(text).split())
    if not 3 <= len(text) <= 2000:
        raise ValueError("describe the goal in a sentence or two")
    if mode not in MODES:
        raise ValueError("a goal runs in ask, sandbox or auto mode")
    if provider and provider not in daemon.cfg["providers"]:
        raise ValueError("choose a configured provider")
    with LOCK:
        if sum(g["state"] == "working" for g in listing()) >= MAX_ACTIVE:
            raise ValueError(f"{MAX_ACTIVE} goals are already being worked on; stop one or wait")
        goal = store({"id": uuid.uuid4().hex[:8], "text": text, "provider": provider or "", "mode": mode, "state": "working",
                      "notes": [], "rounds": 0, "silent": 0, "claimed": False, "question": "", "created": time.time()})
    audit.record("goal_start", goal=goal["id"], text=text, mode=mode)
    launch(daemon, goal["id"])
    return goal


def launch(daemon, ident):
    threading.Thread(target=work, args=(daemon, ident), daemon=True).start()


def resume(daemon):
    """After a restart: goals that were being worked on carry on from their notes."""
    for goal in listing():
        if goal["state"] == "working":
            goal["session"] = ""        # the round that was running ended with the old daemon
            store(goal)
            launch(daemon, goal["id"])


def settle(goal, state, question=""):
    goal.update(state=state, question=question, session="")
    store(goal)
    audit.record("goal_" + state, goal=goal["id"], rounds=goal["rounds"])
    daemon_notify(goal)


def daemon_notify(goal):
    import subprocess
    title = {"done": "Goal finished", "waiting": "A goal needs you", "failed": "A goal could not continue", "stopped": "Goal stopped"}[goal["state"]]
    try:
        subprocess.run(["notify-send", "-a", "Amadeus", title, (goal["question"] or (goal["notes"] or [goal["text"]])[-1])[:240]], capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass


def work(daemon, ident):
    limit = int(daemon.cfg["ai"].get("goal_rounds", 8))
    while True:
        with LOCK:
            goal = load(ident)
            if goal["state"] != "working" or goal.get("session"):
                return
            if goal["rounds"] >= limit:
                return settle(goal, "waiting", f"I worked {limit} rounds without finishing. Answer to let me continue, or stop the goal.")
            goal["rounds"] += 1
            goal["reported"] = ""
            goal["session"] = session = f"goal-{ident}-{goal['rounds']}"
            store(goal)
        prompt = (VERIFY if goal["claimed"] else WORK).format(text=goal["text"], notes="\n".join(f"- {n}" for n in goal["notes"]) or "- (none yet)")
        error = ""
        try:
            daemon.ask(Quiet(), None, prompt, session=session, provider=goal["provider"] or None, options={"mode": goal["mode"]})
        except Exception as e:
            error = str(e)[:300]
        finally:
            daemon.sessions.pop(session, None)
        with LOCK:
            goal = load(ident)
            goal["session"] = ""
            if goal["state"] != "working":
                store(goal)
                return
            reported = goal.get("reported", "")
            if error:
                note(goal, "This round failed: " + error)
                goal["silent"] += 1
            elif not reported:
                note(goal, "(a round ended without reporting)")
                goal["silent"] += 1
            else:
                goal["silent"] = 0
            if goal["silent"] >= 2:
                return settle(goal, "failed" if error else "waiting", "" if error else "Two rounds ended without a report. Answer to let me continue, or stop the goal.")
            if reported == "blocked":
                return settle(goal, "waiting", goal["notes"][-1])
            if reported == "finished":
                if goal["claimed"]:
                    return settle(goal, "done")
                goal["claimed"] = True          # the next round checks the claim before it counts
            elif reported == "progress":
                goal["claimed"] = False
            store(goal)


def stop(daemon, ident):
    with LOCK:
        goal = load(ident)
        session = goal.get("session")
        if goal["state"] not in ("working", "waiting"):
            return goal
        goal.update(state="stopped", question="", session="")
        store(goal)
    if session:
        daemon.stop(session)
    audit.record("goal_stopped", goal=ident)
    return goal


def answer(daemon, ident, text):
    text = " ".join(str(text).split())
    with LOCK:
        goal = load(ident)
        if goal["state"] != "waiting":
            raise ValueError("this goal is not waiting for an answer")
        note(goal, "The user answered: " + (text or "continue"))
        goal.update(state="working", question="", rounds=0, silent=0, claimed=False)
        store(goal)
    launch(daemon, ident)
    return goal
