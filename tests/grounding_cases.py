"""30 grounding-eval cases for the deterministic answer verifier.

Each case: an evidence pack, a candidate model reply, and the expected
verifier outcome. Replies are fixtures, not live model output — the eval
measures VERIFIER correctness (the part that loops every answer), which
must hold regardless of which model produced the reply.

Eval rule (per plan): 30-case grounding eval green — all 30 must pass
with zero regressions; any miss fails the suite.
"""

from __future__ import annotations

# (evidence_texts, reply, expected_valid_badges, expected_invalid_badges)
CASES: list[tuple[list[str], str, list[str], list[str]]] = [
    # --- straightforward grounded answers (1-8)
    (["the user is Venki"], "You are Venki [E1].", ["E1"], []),
    (["the user likes dibble"], "Venki is the user [E1].", ["E1"], []),
    (["today is Friday"], "Today is Friday [E1].", ["E1"], []),
    (["the dog is Milo"], "Your dog is Milo [E1].", ["E1"], []),
    (["the dog is Milo"], "Milo is your dog [E1]. Yes, Milo [E1].", ["E1"], []),
    (["last login failed 3 times"], "There were 3 failed logins [E1].", ["E1"], []),
    (["audit chain is valid"], "The audit chain is intact [E1].", ["E1"], []),
    (["filter coffee is liked in the morning"],
     "You like filter coffee [E1].", ["E1"], []),
    # --- multi-badge answers (9-12)
    (["Venki", "Milo the dog"], "Venki owns Milo [E1] [E2].", ["E1", "E2"], []),
    (["Venki", "Milo"], "Venki is the owner and Milo is the dog [E1] [E2].",
     ["E1", "E2"], []),
    (["two facts here", "and a third"], "Facts: [E1], [E2], [E1] again.",
     ["E1", "E2"], []),
    (["a", "b", "c"], "A and B and C: [E1] [E2] [E3].", ["E1", "E2", "E3"], []),
    # --- hallucinated ids (13-18)
    (["only one fact"], "The value is fifty thousand [E9].", [], ["E9"]),
    (["one fact"], "A made-up source [E2] proves it.", [], ["E2"]),
    (["one fact"], "Also [E42] to fake it.", [], ["E42"]),
    (["x"], "Bad mix [E1] and [E7], the second is fake.", ["E1"], ["E7"]),
    (["x", "y"], "E3? No, only E1 and E2 exist: [E1] [E2].", ["E1", "E2"], []),
    (["real"], "Real one [E1], fake one [E99] stripped.", ["E1"], ["E99"]),
    # --- unsourced-facts replies (19-24)
    (["one fact"], "The weather in Chennai is 32 degrees.", [], []),
    (["one fact"], "Your pinball score was 9,204 points last week.", [], []),
    (["one fact"], "Milo is a golden retriever and two years old.", [], []),
    (["one fact"], "The company grew 40 percent this quarter.", [], []),
    (["one fact"], "There were three cats outside today.", [], []),
    (["one fact"], "Filter coffee is better than tea [E1].", ["E1"], []),
    # --- honesty markers must NOT be flagged (25-28)
    (["one fact"], "I don't have evidence for that yet.", [], []),
    (["one fact"], "I do not know the answer to that.", [], []),
    (["one fact"], "Hi! I don't have evidence for that yet.", [], []),
    (["one fact"], "Thanks — I could not find anything on that.", [], []),
    # --- greetings / meta (29-30)
    (["one fact"], "Hello! How can I help you today?", [], []),
    (["one fact"], "Here is what I know: [E1]", ["E1"], []),
]
