# 新闻栏目（每天刷新）

## 文件

- `YYYY-MM-DD.json`：某一天的新闻，`{ "date": "YYYY-MM-DD", "items": [...] }`，每天 5–7 篇。
- `latest.json`：最新一天的副本，网页加载不到日期列表时用它兜底。
- `sources.json`：RSS 源列表（目前 BBC News + The Guardian），换源改这里。
- 每篇新闻的字段和 `articles/` 里的文章一样（`id/title/cat/level/minutes/desc/vocab/paras`），
  另加 `source`（如 BBC News）、`sourceUrl`（原文链接）、`published`（日期），
  以及 `phrases`（脚本用 `phrases.json` 词典从正文里扫出来的短语，每条带中文意思、英文解释、例句）。
  `cat` 固定是“新闻”，`level` 目前都是 B2，`id` 是 `news-YYYYMMDD-关键词`。

## 每天怎么刷新

每天 08:00（Asia/Shanghai）有一条定时任务跑一次：

1. 拉 `sources.json` 里的 RSS，取最新条目，跳过视频类（链接含 `/videos/` 的）。
2. 抓每篇的全文（Jina Reader `https://r.jina.ai/<原文链接>`，匿名额度不够时用直接抓 BBC 页面取 `<p>` 的办法），
   每篇截取 9 句（3 段×3 句），逐句翻成中文，每篇配 6 个重点词（词必须在正文中出现）。
   写完文件后跑 `python3 scripts/tag_phrases.py news/YYYY-MM-DD.json news/latest.json`，
   用仓库根目录的 `phrases.json` 词典（77 条短语，动词变形也认）扫正文，把短语写进每篇的 `phrases` 里，
   页面上就会划线、点开能看短语词条。
   再跑 `PYTHONDONTWRITEBYTECODE=1 python3 scripts/discover_phrases.py news/YYYY-MM-DD.json`，
   从当天新闻里筛候选短语、去 Free Dictionary API / Wiktionary 查证，查到的新短语审一遍
   （意思要跟新闻里的用法对得上，假的不要，比如字面意思的 "in the dark"、"set in 2022" 里的 set + 时间），
   写好中文意思后追加进 `phrases.json`，再用 tag 脚本把全部文章和新闻重新扫一遍——这样词库每天都在长大，
   新短语在旧文章里出现也会被划上。
3. 写成 `news/YYYY-MM-DD.json`，同时覆盖 `news/latest.json`，推到 GitHub。
4. 部署是自动的——Abasthan 后台 Auto Deploy 开关是开着的，推完约 1 分钟自动上线，不用手动部署（2026-11-19 查证：11:50 的推送 1 分钟内已自动部署成功，线上已能看到新内容）。

## 网页怎么读

`reading.html` 里的 `loadNews()`：先问 GitHub API 要 `news/` 的文件列表，
取日期最大的 `YYYY-MM-DD.json`；问不到就用 `latest.json`。
新闻和文章共用同一个阅读页（查词、发音、朗读、重点词条都一样）。
往日新闻不在当天列表里，但阅读历史里点开时会按日期去仓库里取那一天的文件。
