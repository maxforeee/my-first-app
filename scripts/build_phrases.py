#!/usr/bin/env python3
"""Assemble phrases.json from the dictionary lookup report + hand glosses.

Dictionary definitions/examples come from /tmp/phrase_lookup.json
(Free Dictionary API, then Wiktionary). Verb patterns like "forget to do"
are grammar constructions, not dictionary headwords, so no online
dictionary lists them — those entries use standard textbook glosses
written here (marked by en/ex being filled in GLOSS below).

GLOSS[phrase] = (zh, en, ex, exZh); en/ex None means "use the dictionary
result from the lookup report" (only for the 25 phrases the dictionaries
actually cover). Overrides are used where the dictionary's first sense
is the wrong one (e.g. "have to do" returned the "have to do with" sense).

Run: python3 scripts/build_phrases.py   -> writes phrases.json
"""
import json
import re

from fetch_phrases import CANDS

LOOKUP = "/tmp/phrase_lookup.json"
OUT = "phrases.json"

# (zh, en, ex, exZh) — None = take from the dictionary lookup report.
GLOSS = {
    "forget to do": ("忘记做某事", "to not remember to do something that you should do",
                     "Don't forget to do your homework.", "别忘了做作业。"),
    "forget doing": ("忘记做过某事", "to not remember that you did something",
                     "I forgot meeting her before.", "我忘了以前见过她。"),
    "remember to do": ("记得要做某事", "to not forget to do something",
                       "Remember to do your homework.", "记得做作业。"),
    "remember doing": ("记得做过某事", "to have a memory of doing something",
                       "I remember seeing this film before.", "我记得以前看过这部电影。"),
    "keep doing": ("一直做某事", "to continue doing something",
                   "Keep trying, and you will succeed.", "坚持下去，你会成功的。"),
    "stop doing": ("停止做某事", "to no longer do something",
                   "Please stop talking.", "请不要再说话了。"),
    "stop to do": ("停下来去做某事", "to stop what you are doing in order to do something else",
                   "He stopped to talk with an old friend.", "他停下来和一位老朋友聊了几句。"),
    "decide to do": ("决定做某事", "to make a choice to do something",
                     "She decided to study abroad.", "她决定出国留学。"),
    "plan to do": ("计划做某事", "to intend to do something",
                   "We plan to visit Beijing next year.", "我们计划明年去北京。"),
    "hope to do": ("希望做某事", "to want something to happen or to be true",
                   "I hope to see you again soon.", "希望很快能再见到你。"),
    "agree to do": ("同意做某事", "to say yes to doing something",
                    "He agreed to help us.", "他同意帮助我们。"),
    "refuse to do": ("拒绝做某事", "to say no to doing something",
                     "She refused to answer the question.", "她拒绝回答这个问题。"),
    "manage to do": ("设法做成某事", "to succeed in doing something difficult",
                     "He managed to finish the work on time.", "他设法按时完成了工作。"),
    "fail to do": ("未能做某事", "to not succeed in doing something",
                   "He failed to pass the exam.", "他考试没通过。"),
    "learn to do": ("学会做某事", "to gain the skill to do something",
                    "Children learn to read at school.", "孩子们在学校学会阅读。"),
    "try to do": ("设法做某事；努力做某事", "to attempt to do something",
                  "Try to arrive on time.", "尽量准时到。"),
    "try doing": ("试着做某事（换个方法试试）", "to do something as an experiment, to see if it works",
                  "If you can't sleep, try reading a book.", "如果你睡不着，试试看书。"),
    "want to do": ("想要做某事", "to wish to do something",
                   "I want to learn English.", "我想学英语。"),
    "need to do": ("需要做某事", "to have to do something; to require doing something",
                   "You need to eat more vegetables.", "你需要多吃蔬菜。"),
    "have to do": ("不得不做某事", "must; to be obliged to do something",
                   "I have to do my homework now.", "我现在必须做作业。"),
    "have to do with": ("与……有关", None, None, None),
    "start to do": ("开始做某事", "to begin to do something",
                    "It started to rain.", "开始下雨了。"),
    "start doing": ("开始做某事", "to begin doing something",
                    "She started learning the piano at six.", "她六岁开始学钢琴。"),
    "begin to do": ("开始做某事", "to start to do something",
                    "He began to feel tired.", "他开始感到累了。"),
    "enjoy doing": ("喜欢做某事", "to get pleasure from doing something",
                    "I enjoy reading in the evening.", "我喜欢晚上看书。"),
    "like doing": ("喜欢做某事", "to find doing something pleasant",
                   "She likes swimming in summer.", "她喜欢夏天游泳。"),
    "love doing": ("喜爱做某事", "to like doing something very much",
                   "I love listening to music.", "我很喜欢听音乐。"),
    "hate doing": ("讨厌做某事", "to dislike doing something very much",
                   "I hate waiting in line.", "我讨厌排队。"),
    "mind doing": ("介意做某事", "to be annoyed or worried by doing something",
                   "Do you mind opening the window?", "你介意开一下窗吗？"),
    "practice doing": ("练习做某事", "to do something repeatedly to improve",
                     "Practice speaking English every day.", "每天练习说英语。"),
    "avoid doing": ("避免做某事", "to keep away from doing something",
                    "Avoid eating too much sugar.", "避免吃太多糖。"),
    "finish doing": ("做完某事", "to complete doing something",
                     "Have you finished reading the book?", "你读完这本书了吗？"),
    "suggest doing": ("建议做某事", "to say that someone should do something",
                     "I suggest going by train.", "我建议坐火车去。"),
    "give up doing": ("放弃做某事", "to stop doing something, especially something you have done for a long time",
                     "He gave up smoking last year.", "他去年戒烟了。"),
    "go on doing": ("继续做某事", "to continue doing something",
                   "Go on reading, please.", "请继续读。"),
    "be used to": ("习惯于", None, None, None),
    "get used to": ("逐渐习惯于", None, None, None),
    "used to do": ("过去常常做某事", "to do something regularly in the past, but not now",
                   "I used to play football when I was young.", "我小时候常踢足球。"),
    "look forward to": ("期待", None, "I look forward to seeing you.", "我期待见到你。"),
    "be interested in": ("对……感兴趣", "to want to know or learn about something",
                         "She is interested in music.", "她对音乐感兴趣。"),
    "be good at": ("擅长", "to be skilled at doing something",
                   "He is good at maths.", "他数学很好。"),
    "be afraid of": ("害怕", "to feel fear of something",
                    "She is afraid of dogs.", "她怕狗。"),
    "be able to": ("能够", None, "I am able to swim.", "我会游泳。"),
    "be ready to do": ("准备好做某事", "to be prepared to do something",
                       "Are you ready to go?", "你准备好走了吗？"),
    "be busy doing": ("忙于做某事", "to be occupied with doing something",
                      "She is busy preparing dinner.", "她正忙着做晚饭。"),
    "be worth doing": ("值得做某事", "to be good or important enough to do",
                       "This book is worth reading.", "这本书值得一读。"),
    "spend time doing": ("花时间做某事", "to use time doing something",
                         "He spends a lot of time playing games.", "他花很多时间打游戏。"),
    "have fun doing": ("做某事很开心", "to enjoy doing something",
                       "We had fun playing football.", "我们踢足球玩得很开心。"),
    "would like to do": ("想要做某事（客气说法）", "to want to do something (a polite way to say 'want')",
                         "I would like to visit London.", "我想去伦敦看看。"),
    "help to do": ("帮助做某事", "to assist someone to do something",
                   "Can you help me to carry this box?", "你能帮我搬一下这个箱子吗？"),
    "take part in": ("参加", "to join in an activity",
                     "Many students took part in the sports meeting.", "很多学生参加了运动会。"),
    "take care of": ("照顾；小心", None, None, None),
    "pay attention to": ("注意", "to listen to or watch something carefully",
                         "Pay attention to your teacher.", "注意听老师讲。"),
    "make sure": ("确保；一定要", None, None, None),
    "make a decision": ("做决定", None, None, None),
    "at the same time": ("同时", None, None, None),
    "in the end": ("最后；终于", None, None, None),
    "at first": ("起初", None, None, None),
    "at last": ("最后；终于", None, None, None),
    "in fact": ("事实上", "actually; in reality", None, None),
    "for example": ("例如", None, "For example, I like apples and bananas.", "例如，我喜欢苹果和香蕉。"),
    "do something": ("做某事", "to perform an action",
                     "Let's do something fun today.", "今天我们做点有趣的事吧。"),
    "to do something": ("去做某事", "to perform an action (used after verbs like want, need, decide)",
                        "She wants to do something special.", "她想做点特别的事。"),
    "turn into": ("变成", None, None, None),
    "grow up": ("长大", None, None, None),
    "take place": ("发生；举行", None, None, None),
    "find out": ("发现；查明", None, "Please find out when the train leaves.", "请查一下火车什么时候开。"),
    "look for": ("寻找", None, None, None),
    "look at": ("看", None, "Look at the blackboard, please.", "请看黑板。"),
    "talk about": ("谈论", "to speak about something; to discuss",
                   "Let's talk about your plan.", "我们来谈谈你的计划。"),
    "think about": ("思考；考虑", None, None, None),
    "worry about": ("担心", "to feel troubled about something",
                    "Don't worry about the exam.", "别担心考试。"),
    "learn from": ("向……学习；从……吸取教训", "to gain knowledge by studying or experiencing something",
                  "We can learn from our mistakes.", "我们可以从错误中吸取教训。"),
    "come from": ("来自", None, "Where do you come from?", "你来自哪里？"),
    "arrive at": ("到达（小地方）", None, "We arrived at the station at nine.", "我们九点到达车站。"),
    "arrive in": ("到达（大地方）", "to reach a large place, such as a city or country",
                 "They arrived in London yesterday.", "他们昨天到达伦敦。"),
    "get ready for": ("为……做好准备", "to prepare for something",
                      "Get ready for school!", "准备好去上学！"),
}


def clean_def(s):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s[:140]


def main():
    report = json.load(open(LOOKUP))
    items = []
    for phrase, pat, forms in CANDS:
        zh, en, ex, exZh = GLOSS[phrase]
        look = report.get(phrase, {})
        if en is None:
            defs = look.get("defs") or []
            en = clean_def(defs[0]) if defs else ""
        if ex is None:
            exs = look.get("examples") or []
            ex = exs[0] if exs else ""
        if exZh is None:
            exZh = ""
        assert zh and en, phrase
        items.append({"p": phrase, "pat": pat, "forms": forms,
                      "zh": zh, "en": en, "ex": ex, "exZh": exZh})
    data = {"version": 1,
            "note": "Short-phrase dictionary for the reading tool. English definitions/examples checked against Free Dictionary API and Wiktionary (25 of 77 are dictionary headwords); verb patterns like 'forget to do' are grammar constructions, not dictionary entries, so their glosses are standard textbook meanings.",
            "items": items}
    json.dump(data, open(OUT, "w"), ensure_ascii=False, indent=2)
    print(f"wrote {OUT}: {len(items)} phrases")
    no_ex = [it["p"] for it in items if not it["ex"]]
    print("entries without an example:", no_ex)


if __name__ == "__main__":
    main()
