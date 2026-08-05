"""SENTINEL red-team probe — paraphrase evasion of the L1 critical-event fastpath.

22 plausible bodycam phrasings across the five categories the keyword fastpath
claims to cover, in four languages. Measures how many the deterministic layer
catches, and how many it hard-drops as `none` before any LLM sees them.

Tests the local layers only. The LLM router may still catch what falls through;
that is not measurable without API keys.

Usage:  python scripts/redteam_probe.py
"""
import os, sys, pathlib
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parent.parent
os.environ["SENTINEL_QUIET"] = "1"
sys.path.insert(0, str(REPO))

from agents.router_agent import RouterAgent
from agents.rapid_prosecution import RapidProsecutionAgent
from agents.retrieval_agent import RetrievalAgent

PROBES = [
    ("armed",    "en", "Put that blade down right now"),
    ("armed",    "en", "He's holding a knife, watch out"),
    ("armed",    "en", "Weapon! Something in his right hand"),
    ("taser",    "en", "I'm going less-lethal"),
    ("taser",    "en", "Taser out, taser out"),
    ("taser",    "en", "Red dot on him, stand by"),
    ("distress", "en", "I need units here now"),
    ("distress", "en", "He's got my radio, send backup"),
    ("distress", "en", "Man down, man down"),
    ("lethal",   "en", "Rounds downrange"),
    ("lethal",   "en", "Shots! Shots!"),
    ("lethal",   "en", "I fired two rounds"),
    ("warning",  "en", "This is the last time I'm telling you"),
    ("warning",  "en", "Don't make me do this"),
    ("warning",  "en", "You get one more chance"),
    ("armed",    "es", "Tiene un arma en la mano"),
    ("lethal",   "es", "Voy a disparar"),
    ("distress", "es", "Necesito refuerzos ahora"),
    ("armed",    "nl", "Hij heeft een mes"),
    ("distress", "nl", "Ik heb assistentie nodig"),
    ("armed",    "it", "Ha un coltello in mano"),
    ("distress", "it", "Serve rinforzo subito"),
]


def main():
    router = RouterAgent(region="us")
    rapid = RapidProsecutionAgent(region="us", retrieval=RetrievalAgent())
    tally = Counter()
    hard_dropped = []

    for cat, lang, text in PROBES:
        kw = router._keyword_classify(text)
        cls = kw.classification if kw else "->LLM router"
        rule = rapid._build_critical_event_alert(text).rule_id if cls == "critical_event" else None
        caught = bool(rule and rule != "CRIT-GENERIC")
        tally["caught" if caught else "missed"] += 1
        tally[f"{lang}_" + ("caught" if caught else "missed")] += 1
        if kw is not None and kw.classification == "none":
            tally["hard_dropped"] += 1
            hard_dropped.append((text, kw.stage, len(text.split())))
        print(f" {'OK  ' if caught else 'MISS'} [{lang}/{cat:8s}] {text!r:42s} -> {cls:14s} {rule or ''}")

    n = len(PROBES)
    print(f"\n caught by fastpath : {tally['caught']}/{n}")
    print(f" fell through to LLM: {n - tally['caught'] - tally['hard_dropped']}/{n}")
    print(f" HARD-DROPPED as 'none', never reach any LLM: {tally['hard_dropped']}/{n}")
    for text, stage, words in hard_dropped:
        print(f"   [{stage}, {words} words] {text!r}")
    print(f"\n by language: {dict(tally)}")


if __name__ == "__main__":
    main()
