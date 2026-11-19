#!/usr/bin/env python3
"""Tag phrases in article JSON files.

Reads the shared dictionary (phrases.json) and, for each article in the
given files, finds which dictionary phrases actually occur in its English
text (verb forms recognised: forgot to do, kept doing, ...; DO = any word
after "to", DOING = any -ing word). Writes a `phrases` list into each
article: [{p, surf, zh, en, ex, exZh}] where `surf` is the list of surface
forms found in this article (e.g. ["started to", "start to"]).

Usage:
    python3 scripts/tag_phrases.py articles/ai-learning.json news/2026-11-19.json
A news day file ({"items": [...]}) is tagged item by item.
Re-running is safe: the `phrases` field is recomputed from scratch.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def norm(w):
    w = w.lower()
    if w.endswith("'s"):
        w = w[:-2]
    return w


def load_dict():
    data = json.load(open(ROOT / "phrases.json"))
    items = sorted(data["items"], key=lambda it: (-len(it["pat"]), data["items"].index(it)))
    return items


def token_match(tok, word, forms):
    """Does dictionary token `tok` match the text word `word`?"""
    w = norm(word)
    if tok == "DO":
        return True
    if tok == "DOING":
        return len(w) > 3 and w.endswith("ing")
    if tok in forms:
        return w in [f.lower() for f in forms[tok]]
    if w == tok:
        return True
    # s/es tolerance, same rule as the page's vocab matcher
    if len(w) > 3 and w.endswith("s"):
        if w[:-1] == tok:
            return True
        if w.endswith("es") and w[:-2] == tok:
            return True
    return False


def find_in_sentence(words, phrases):
    """words: list of surface word tokens. Returns list of
    (phrase_index, start, end, surf_string). Longest match wins at each
    position; scanning is left to right."""
    found = []
    i = 0
    while i < len(words):
        best = None
        for pi, ph in enumerate(phrases):
            pat = ph["pat"]
            if i + len(pat) > len(words):
                continue
            ok = True
            for j, tok in enumerate(pat):
                forms = ph["forms"] if j == 0 else {}
                if not token_match(tok, words[i + j], forms):
                    ok = False
                    break
            if ok:
                best = (pi, i, i + len(pat))
                break  # phrases are pre-sorted longest-first
        if best:
            pi, s, e = best
            surf = " ".join(norm(w) for w in words[s:e])
            found.append((pi, s, e, surf))
            i = e
        else:
            i += 1
    return found


def tag_article(article, phrases):
    by_phrase = {}
    order = []
    for para in article.get("paras", []):
        for sent in para.get("en", []):
            words = WORD_RE.findall(sent)
            for pi, _s, _e, surf in find_in_sentence(words, phrases):
                ph = phrases[pi]
                if pi not in by_phrase:
                    by_phrase[pi] = {"p": ph["p"], "surf": set(),
                                     "zh": ph["zh"], "en": ph["en"],
                                     "ex": ph["ex"], "exZh": ph["exZh"]}
                    order.append(pi)
                by_phrase[pi]["surf"].add(surf)
    out = []
    for pi in order:
        d = by_phrase[pi]
        out.append({"p": d["p"], "surf": sorted(d["surf"]), "zh": d["zh"],
                    "en": d["en"], "ex": d["ex"], "exZh": d["exZh"]})
    article["phrases"] = out
    return out


def main():
    phrases = load_dict()
    for path in sys.argv[1:]:
        p = Path(path)
        if p.name.startswith("_") or p.name == "index.json":
            continue
        data = json.load(open(p))
        if isinstance(data, list):
            continue
        if isinstance(data, dict) and "items" in data:
            targets = data["items"]
        else:
            targets = [data]
        total = 0
        for art in targets:
            got = tag_article(art, phrases)
            total += len(got)
            print(f"  {art.get('id', '?')}: {len(got)} phrases — " +
                  ", ".join(g['p'] for g in got))
        json.dump(data, open(p, "w"), ensure_ascii=False, indent=2)
        print(f"{p}: {total} phrase entries written")


if __name__ == "__main__":
    main()
