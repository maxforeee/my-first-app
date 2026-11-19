#!/usr/bin/env python3
"""Discover new phrases from article/news text and check them against dictionaries.

This is the growing-library loop for the phrase dictionary:
  1. Read article/news JSON files, take every English sentence.
  2. Generate candidate phrases from pattern templates (verb+prep,
     verb+particle, verb+to+verb, verb+-ing, be+adj+prep, prep+the+noun,
     verb+a+noun, verb+word+prep, ...).
  3. Normalise each candidate to its base form (looks for -> look for).
  4. Skip anything already in phrases.json.
  5. Check the base form against Free Dictionary API, then Wiktionary.
     Only phrases the dictionary actually lists are real phrases — the
     rest are just word combinations and are dropped.
  6. Print a JSON report (also saved to /tmp/phrase_candidates.json):
     [{p, pat, forms, en, ex, seen_in, example}]

New entries are NOT added automatically: the agent reviews the report,
writes the Chinese gloss (zh) and appends the entry to phrases.json,
then re-runs tag_phrases.py over all articles so the new phrase gets
underlined everywhere it occurs (old articles included).

Usage:
    PYTHONDONTWRITEBYTECODE=1 python3 scripts/discover_phrases.py articles/*.json news/2026-11-19.json
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_phrases import dictapi, wiktionary  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")

PREP = {"about", "above", "across", "after", "against", "along", "among",
        "around", "at", "before", "behind", "below", "beneath", "beside",
        "between", "beyond", "by", "down", "during", "for", "from", "in",
        "inside", "into", "like", "near", "of", "off", "on", "onto", "out",
        "over", "past", "through", "to", "toward", "towards", "under",
        "until", "up", "upon", "with", "within", "without"}
PART = {"up", "down", "out", "off", "away", "back", "over", "along",
        "around", "through", "on", "in"}
DET = {"a", "an", "the"}
BE = {"am", "is", "are", "was", "were", "be", "been", "being"}
STOP_FIRST = {"i", "you", "he", "she", "it", "we", "they", "this", "that",
              "these", "those", "the", "a", "an", "and", "but", "or", "so",
              "if", "when", "while", "because", "as", "my", "your", "his",
              "her", "its", "our", "their", "me", "him", "us", "them",
              "there", "here", "what", "who", "which", "how", "why",
              "not", "no", "yes", "very", "just", "also", "only", "even",
              "still", "already", "now", "today", "then", "once", "twice"}

IRREG = {
    "went": "go", "gone": "go", "took": "take", "taken": "take",
    "gave": "give", "given": "give", "found": "find", "made": "make",
    "saw": "see", "seen": "see", "got": "get", "gotten": "get",
    "kept": "keep", "brought": "bring", "thought": "think",
    "told": "tell", "became": "become", "left": "leave", "felt": "feel",
    "meant": "mean", "began": "begin", "begun": "begin", "broke": "break",
    "broken": "break", "chose": "choose", "chosen": "choose",
    "drew": "draw", "drawn": "draw", "drove": "drive", "driven": "drive",
    "ate": "eat", "eaten": "eat", "fell": "fall", "fallen": "fall",
    "flew": "fly", "flown": "fly", "forgot": "forget", "forgotten": "forget",
    "grew": "grow", "grown": "grow", "heard": "hear", "held": "hold",
    "hid": "hide", "hidden": "hide", "knew": "know", "known": "know",
    "laid": "lay", "led": "lead", "lent": "lend", "lost": "lose",
    "paid": "pay", "ran": "run", "rode": "ride", "ridden": "ride",
    "rose": "rise", "risen": "rise", "said": "say", "sang": "sing",
    "sung": "sing", "sat": "sit", "sent": "send", "slept": "sleep",
    "spoke": "speak", "spoken": "speak", "spent": "spend", "stood": "stand",
    "stole": "steal", "stolen": "steal", "swam": "swim", "swum": "swim",
    "taught": "teach", "tore": "tear", "torn": "tear", "won": "win",
    "wore": "wear", "worn": "wear", "wrote": "write", "written": "write",
    "built": "build", "bought": "buy", "caught": "catch", "sold": "sell",
    "shot": "shoot", "shut": "shut", "drank": "drink", "drunk": "drink",
    "woke": "wake", "woken": "wake", "cut": "cut", "set": "set",
    "cost": "cost", "hit": "hit", "let": "let", "read": "read", "put": "put",
    "drove": "drive", "did": "do", "done": "do", "does": "do", "had": "have",
    "has": "have", "was": "be", "were": "be", "been": "be", "being": "be",
    "am": "be", "is": "be", "are": "be",
}
IRREG_FORMS = {
    "go": ["go", "goes", "went", "gone"], "take": ["take", "takes", "took", "taken"],
    "give": ["give", "gives", "gave", "given"], "find": ["find", "finds", "found"],
    "make": ["make", "makes", "made"], "see": ["see", "sees", "saw", "seen"],
    "get": ["get", "gets", "got", "gotten"], "keep": ["keep", "keeps", "kept"],
    "bring": ["bring", "brings", "brought"], "think": ["think", "thinks", "thought"],
    "tell": ["tell", "tells", "told"], "become": ["become", "becomes", "became", "become"],
    "leave": ["leave", "leaves", "left"], "feel": ["feel", "feels", "felt"],
    "mean": ["mean", "means", "meant"], "begin": ["begin", "begins", "began", "begun"],
    "break": ["break", "breaks", "broke", "broken"], "choose": ["choose", "chooses", "chose", "chosen"],
    "draw": ["draw", "draws", "drew", "drawn"], "drive": ["drive", "drives", "drove", "driven"],
    "eat": ["eat", "eats", "ate", "eaten"], "fall": ["fall", "falls", "fell", "fallen"],
    "fly": ["fly", "flies", "flew", "flown"], "forget": ["forget", "forgets", "forgot", "forgotten"],
    "grow": ["grow", "grows", "grew", "grown"], "hear": ["hear", "hears", "heard"],
    "hold": ["hold", "holds", "held"], "hide": ["hide", "hides", "hid", "hidden"],
    "know": ["know", "knows", "knew", "known"], "lay": ["lay", "lays", "laid"],
    "lead": ["lead", "leads", "led"], "lend": ["lend", "lends", "lent"],
    "lose": ["lose", "loses", "lost"], "pay": ["pay", "pays", "paid"],
    "run": ["run", "runs", "ran"], "ride": ["ride", "rides", "rode", "ridden"],
    "rise": ["rise", "rises", "rose", "risen"], "say": ["say", "says", "said"],
    "sing": ["sing", "sings", "sang", "sung"], "sit": ["sit", "sits", "sat"],
    "send": ["send", "sends", "sent"], "sleep": ["sleep", "sleeps", "slept"],
    "speak": ["speak", "speaks", "spoke", "spoken"], "spend": ["spend", "spends", "spent"],
    "stand": ["stand", "stands", "stood"], "steal": ["steal", "steals", "stole", "stolen"],
    "swim": ["swim", "swims", "swam", "swum"], "teach": ["teach", "teaches", "taught"],
    "tear": ["tear", "tears", "tore", "torn"], "win": ["win", "wins", "won"],
    "wear": ["wear", "wears", "wore", "worn"], "write": ["write", "writes", "wrote", "written"],
    "build": ["build", "builds", "built"], "buy": ["buy", "buys", "bought"],
    "catch": ["catch", "catches", "caught"], "sell": ["sell", "sells", "sold"],
    "shoot": ["shoot", "shoots", "shot"], "drink": ["drink", "drinks", "drank", "drunk"],
    "wake": ["wake", "wakes", "woke", "woken"], "do": ["do", "does", "did", "done"],
    "have": ["have", "has", "had"], "be": ["be", "am", "is", "are", "was", "were", "been", "being"],
}


def norm(w):
    w = w.lower()
    if w.endswith("'s"):
        w = w[:-2]
    return w


def lemma(w):
    w = norm(w)
    if w in IRREG:
        return IRREG[w]
    if len(w) > 4 and w.endswith("ing"):
        base = w[:-3]
        if base and base[-1] == base[-2]:
            base = base[:-1]
        return base
    if len(w) > 3 and w.endswith("ed"):
        base = w[:-2]
        if base and base[-1] == base[-2]:
            base = base[:-1]
        return base
    if len(w) > 3 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def verb_forms(base):
    if base in IRREG_FORMS:
        return IRREG_FORMS[base]
    forms = [base, base + "s"]
    if base.endswith("e"):
        forms += [base + "d", base[:-1] + "ing"]
    elif base.endswith("y") and len(base) > 1 and base[-2] not in "aeiou":
        forms += [base[:-1] + "ied", base[:-1] + "ying"]
    elif (len(base) >= 3 and base[-1] not in "aeiouwx y" and base[-2] in "aeiou"
          and base[-3] not in "aeiou"):
        forms += [base + base[-1] + "ed", base + base[-1] + "ing"]
    else:
        forms += [base + "ed", base + "ing"]
    return forms


def clean(s):
    import re as _re
    s = _re.sub(r"\s+", " ", s or "").strip()
    return s[:140]


def candidates_from_sentence(words):
    """words: lowercased word tokens. Yields (base_form, pat, forms)."""
    n = len(words)
    for i in range(n):
        w0 = words[i]
        if w0 in STOP_FIRST or len(w0) < 2:
            continue
        v = lemma(w0)
        # [verb, prep]
        if i + 1 < n and words[i + 1] in PREP and words[i + 1] != "to":
            yield (f"{v} {words[i + 1]}", [v, words[i + 1]], {v: verb_forms(v)})
        if i + 1 < n and words[i + 1] in PART:
            yield (f"{v} {words[i + 1]}", [v, words[i + 1]], {v: verb_forms(v)})
        # [verb, to, DO] and [verb, DOING] and [be, adj, prep] are NOT
        # generated here: verb patterns are grammar, not dictionary
        # headwords (the earlier fetch proved it: 0 of 52 such patterns
        # are listed in any online dictionary), so querying them is pure
        # waste. Discovery only covers true idioms / phrasal verbs /
        # fixed chunks, which dictionaries do list.
        # [verb, word, prep]  (look forward to, get rid of)
        if i + 2 < n and words[i + 2] in PREP and words[i + 1] not in STOP_FIRST:
            yield (f"{v} {words[i + 1]} {words[i + 2]}", [v, words[i + 1], words[i + 2]],
                   {v: verb_forms(v)})
        # [prep, det, word] / [prep, det, word, of]
        if w0 in PREP and i + 2 < n and words[i + 1] in DET:
            yield (f"{w0} {words[i + 1]} {words[i + 2]}", [w0, words[i + 1], words[i + 2]], {})
            if i + 3 < n and words[i + 3] == "of":
                yield (f"{w0} {words[i + 1]} {words[i + 2]} of",
                       [w0, words[i + 1], words[i + 2], "of"], {})
        # [prep, word, to]  (in order to)
        if w0 in PREP and i + 2 < n and words[i + 2] == "to":
            yield (f"{w0} {words[i + 1]} to", [w0, words[i + 1], "to"], {})
        # [verb, det, word]  (take a look, make a decision)
        if i + 2 < n and words[i + 1] in DET and words[i + 2] not in STOP_FIRST:
            yield (f"{v} {words[i + 1]} {words[i + 2]}", [v, words[i + 1], words[i + 2]],
                   {v: verb_forms(v)})


def main():
    existing = {it["p"] for it in json.load(open(ROOT / "phrases.json"))["items"]}
    seen = {}  # base form -> {"pat","forms","seen_in","example"}
    for path in sys.argv[1:]:
        p = Path(path)
        if p.name.startswith("_") or p.name == "index.json":
            continue
        data = json.load(open(p))
        items = data["items"] if isinstance(data, dict) and "items" in data else [data]
        for art in items:
            if not isinstance(art, dict):
                continue
            for para in art.get("paras", []):
                for sent in para.get("en", []):
                    words = [norm(w) for w in WORD_RE.findall(sent)]
                    for base, pat, forms in candidates_from_sentence(words):
                        if base in existing or base in seen:
                            if base in seen:
                                seen[base]["seen_in"].add(art.get("id", "?"))
                            continue
                        seen[base] = {"pat": pat, "forms": forms,
                                      "seen_in": {art.get("id", "?")},
                                      "example": sent}
    print(f"candidates to check: {len(seen)}", file=sys.stderr)
    from concurrent.futures import ThreadPoolExecutor
    import threading
    found = []
    lock = threading.Lock()
    done = {"n": 0}
    total = len(seen)

    def check(item):
        base, info = item
        hit = dictapi(base)
        src = "dictapi" if hit else None
        if not hit:
            hit = wiktionary(base)
            src = "wiktionary" if hit else None
        with lock:
            done["n"] += 1
            if hit:
                defs = hit.get("defs") or []
                exs = hit.get("examples") or []
                found.append({"p": base, "pat": info["pat"], "forms": info["forms"],
                              "en": clean(defs[0]) if defs else "",
                              "ex": exs[0] if exs else "",
                              "seen_in": sorted(info["seen_in"]),
                              "example": info["example"], "dict_src": src})
                print(f"OK  {base} [{src}]", flush=True)
                json.dump(found, open("/tmp/phrase_candidates.json", "w"),
                          ensure_ascii=False, indent=2)
            if done["n"] % 50 == 0:
                print(f"... {done['n']}/{total} checked, {len(found)} found",
                      file=sys.stderr, flush=True)
        time.sleep(0.05)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(check, sorted(seen.items())))
    print(f"\n{len(found)} new dictionary phrases found", file=sys.stderr)


if __name__ == "__main__":
    main()
