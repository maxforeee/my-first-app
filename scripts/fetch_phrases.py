#!/usr/bin/env python3
"""Fetch dictionary entries for the phrase list used by the reading tool.

Sources (checked in order):
  1. Free Dictionary API  https://api.dictionaryapi.dev/api/v2/entries/en/<phrase>
  2. Wiktionary REST       https://en.wiktionary.org/api/rest_v1/page/definition/<phrase>

Writes a lookup report to /tmp/phrase_lookup.json:
  { phrase: { "src": "dictapi"|"wiktionary"|null,
              "defs": [..], "examples": [..] } }
The phrases.json dictionary is then assembled from this report plus
hand-written Chinese glosses (standard textbook meanings).
Run: python3 scripts/fetch_phrases.py
"""
import json
import time
import urllib.parse
import urllib.request

# (display, pattern tokens, forms) — DO = any word (verb slot after "to"),
# DOING = any word ending in "ing". First token may list its surface forms.
CANDS = [
    ("forget to do", ["forget", "to", "DO"], {"forget": ["forget", "forgets", "forgot", "forgotten"]}),
    ("forget doing", ["forget", "DOING"], {"forget": ["forget", "forgets", "forgot", "forgotten"]}),
    ("remember to do", ["remember", "to", "DO"], {"remember": ["remember", "remembers", "remembered"]}),
    ("remember doing", ["remember", "DOING"], {"remember": ["remember", "remembers", "remembered"]}),
    ("keep doing", ["keep", "DOING"], {"keep": ["keep", "keeps", "kept"]}),
    ("stop doing", ["stop", "DOING"], {"stop": ["stop", "stops", "stopped"]}),
    ("stop to do", ["stop", "to", "DO"], {"stop": ["stop", "stops", "stopped"]}),
    ("decide to do", ["decide", "to", "DO"], {"decide": ["decide", "decides", "decided"]}),
    ("plan to do", ["plan", "to", "DO"], {"plan": ["plan", "plans", "planned"]}),
    ("hope to do", ["hope", "to", "DO"], {"hope": ["hope", "hopes", "hoped"]}),
    ("agree to do", ["agree", "to", "DO"], {"agree": ["agree", "agrees", "agreed"]}),
    ("refuse to do", ["refuse", "to", "DO"], {"refuse": ["refuse", "refuses", "refused"]}),
    ("manage to do", ["manage", "to", "DO"], {"manage": ["manage", "manages", "managed"]}),
    ("fail to do", ["fail", "to", "DO"], {"fail": ["fail", "fails", "failed"]}),
    ("learn to do", ["learn", "to", "DO"], {"learn": ["learn", "learns", "learned", "learnt"]}),
    ("try to do", ["try", "to", "DO"], {"try": ["try", "tries", "tried"]}),
    ("try doing", ["try", "DOING"], {"try": ["try", "tries", "tried"]}),
    ("want to do", ["want", "to", "DO"], {"want": ["want", "wants", "wanted"]}),
    ("need to do", ["need", "to", "DO"], {"need": ["need", "needs", "needed"]}),
    ("have to do", ["have", "to", "DO"], {"have": ["have", "has", "had"]}),
    ("have to do with", ["have", "to", "do", "with"], {"have": ["have", "has", "had"]}),
    ("start to do", ["start", "to", "DO"], {"start": ["start", "starts", "started"]}),
    ("start doing", ["start", "DOING"], {"start": ["start", "starts", "started"]}),
    ("begin to do", ["begin", "to", "DO"], {"begin": ["begin", "begins", "began", "begun"]}),
    ("enjoy doing", ["enjoy", "DOING"], {"enjoy": ["enjoy", "enjoys", "enjoyed"]}),
    ("like doing", ["like", "DOING"], {"like": ["like", "likes", "liked"]}),
    ("love doing", ["love", "DOING"], {"love": ["love", "loves", "loved"]}),
    ("hate doing", ["hate", "DOING"], {"hate": ["hate", "hates", "hated"]}),
    ("mind doing", ["mind", "DOING"], {"mind": ["mind", "minds", "minded"]}),
    ("practice doing", ["practice", "DOING"], {"practice": ["practice", "practices", "practiced", "practised"]}),
    ("avoid doing", ["avoid", "DOING"], {"avoid": ["avoid", "avoids", "avoided"]}),
    ("finish doing", ["finish", "DOING"], {"finish": ["finish", "finishes", "finished"]}),
    ("suggest doing", ["suggest", "DOING"], {"suggest": ["suggest", "suggests", "suggested"]}),
    ("give up doing", ["give", "up", "DOING"], {"give": ["give", "gives", "gave", "given"]}),
    ("go on doing", ["go", "on", "DOING"], {"go": ["go", "goes", "went", "gone"]}),
    ("be used to", ["be", "used", "to"], {"be": ["be", "am", "is", "are", "was", "were", "been", "being"]}),
    ("get used to", ["get", "used", "to"], {"get": ["get", "gets", "got", "gotten"]}),
    ("used to do", ["used", "to", "DO"], {}),
    ("look forward to", ["look", "forward", "to"], {"look": ["look", "looks", "looked"]}),
    ("be interested in", ["be", "interested", "in"], {"be": ["be", "am", "is", "are", "was", "were", "been", "being"]}),
    ("be good at", ["be", "good", "at"], {"be": ["be", "am", "is", "are", "was", "were", "been", "being"]}),
    ("be afraid of", ["be", "afraid", "of"], {"be": ["be", "am", "is", "are", "was", "were", "been", "being"]}),
    ("be able to", ["be", "able", "to"], {"be": ["be", "am", "is", "are", "was", "were", "been", "being"]}),
    ("be ready to do", ["be", "ready", "to", "DO"], {"be": ["be", "am", "is", "are", "was", "were", "been", "being"]}),
    ("be busy doing", ["be", "busy", "DOING"], {"be": ["be", "am", "is", "are", "was", "were", "been", "being"]}),
    ("be worth doing", ["be", "worth", "DOING"], {"be": ["be", "am", "is", "are", "was", "were", "been", "being"]}),
    ("spend time doing", ["spend", "time", "DOING"], {"spend": ["spend", "spends", "spent"]}),
    ("have fun doing", ["have", "fun", "DOING"], {"have": ["have", "has", "had"]}),
    ("would like to do", ["would", "like", "to", "DO"], {}),
    ("help to do", ["help", "to", "DO"], {"help": ["help", "helps", "helped"]}),
    ("take part in", ["take", "part", "in"], {"take": ["take", "takes", "took", "taken"]}),
    ("take care of", ["take", "care", "of"], {"take": ["take", "takes", "took", "taken"]}),
    ("pay attention to", ["pay", "attention", "to"], {"pay": ["pay", "pays", "paid"]}),
    ("make sure", ["make", "sure"], {"make": ["make", "makes", "made"]}),
    ("make a decision", ["make", "a", "decision"], {"make": ["make", "makes", "made"]}),
    ("at the same time", ["at", "the", "same", "time"], {}),
    ("in the end", ["in", "the", "end"], {}),
    ("at first", ["at", "first"], {}),
    ("at last", ["at", "last"], {}),
    ("in fact", ["in", "fact"], {}),
    ("for example", ["for", "example"], {}),
    ("do something", ["do", "something"], {"do": ["do", "does", "did", "done"]}),
    ("to do something", ["to", "do", "something"], {}),
    ("turn into", ["turn", "into"], {"turn": ["turn", "turns", "turned"]}),
    ("grow up", ["grow", "up"], {"grow": ["grow", "grows", "grew", "grown"]}),
    ("take place", ["take", "place"], {"take": ["take", "takes", "took", "taken"]}),
    ("find out", ["find", "out"], {"find": ["find", "finds", "found"]}),
    ("look for", ["look", "for"], {"look": ["look", "looks", "looked"]}),
    ("look at", ["look", "at"], {"look": ["look", "looks", "looked"]}),
    ("talk about", ["talk", "about"], {"talk": ["talk", "talks", "talked"]}),
    ("think about", ["think", "about"], {"think": ["think", "thinks", "thought"]}),
    ("worry about", ["worry", "about"], {"worry": ["worry", "worries", "worried"]}),
    ("learn from", ["learn", "from"], {"learn": ["learn", "learns", "learned", "learnt"]}),
    ("come from", ["come", "from"], {"come": ["come", "comes", "came"]}),
    ("arrive at", ["arrive", "at"], {"arrive": ["arrive", "arrives", "arrived"]}),
    ("arrive in", ["arrive", "in"], {"arrive": ["arrive", "arrives", "arrived"]}),
    ("get ready for", ["get", "ready", "for"], {"get": ["get", "gets", "got", "gotten"]}),
]

UA = {"User-Agent": "Mozilla/5.0 (reading-tool dictionary lookup)"}


def get_json(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def clean(s):
    import re
    s = re.sub(r"<[^>]+>", "", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def dictapi(phrase):
    url = "https://api.dictionaryapi.dev/api/v2/entries/en/" + urllib.parse.quote(phrase)
    try:
        data = get_json(url)
    except Exception:
        return None
    defs, examples = [], []
    for entry in data if isinstance(data, list) else []:
        for m in entry.get("meanings", []):
            for d in m.get("definitions", []):
                if d.get("definition"):
                    defs.append(clean(d["definition"]))
                if d.get("example"):
                    examples.append(clean(d["example"]))
    return {"defs": defs[:3], "examples": examples[:2]} if defs else None


def wiktionary(phrase):
    url = "https://en.wiktionary.org/api/rest_v1/page/definition/" + urllib.parse.quote(phrase)
    try:
        data = get_json(url)
    except Exception:
        return None
    defs, examples = [], []
    for lang_entries in data.values() if isinstance(data, dict) else []:
        for block in lang_entries:
            for d in block.get("definitions", []):
                if d.get("definition"):
                    defs.append(clean(d["definition"]))
                for ex in d.get("examples", []) or []:
                    if isinstance(ex, str):
                        examples.append(clean(ex))
    return {"defs": defs[:3], "examples": examples[:2]} if defs else None


def main():
    report = {}
    for phrase, _pat, _forms in CANDS:
        hit = dictapi(phrase)
        src = "dictapi" if hit else None
        if not hit:
            hit = wiktionary(phrase)
            src = "wiktionary" if hit else None
        report[phrase] = {"src": src, "defs": hit["defs"] if hit else [],
                           "examples": hit["examples"] if hit else []}
        # save after every phrase so an interrupted run keeps its progress
        json.dump(report, open("/tmp/phrase_lookup.json", "w"), ensure_ascii=False, indent=2)
        print(f"{'OK ' if src else '-- '} {phrase} [{src}]", flush=True)
        time.sleep(0.15)
    found = sum(1 for v in report.values() if v["src"])
    print(f"\n{found}/{len(report)} found in a dictionary")


if __name__ == "__main__":
    main()
