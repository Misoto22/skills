`star-prune` 处理那些早就没用了、却一直留在 star 里的仓库：作者已经归档的，README 里改成「已废弃，请改用 X」的，还有被 GitHub 直接禁用的。它们夹在你还会回头看的那些 star 中间，让整个列表越来越难用。这个技能把它们找出来，说清楚每一个为什么被标出，只取消你同意取消的。

## 它会标出什么，又会放过什么

```
Wrote prune.json: 21 of 156 starred repositories flagged.
  archived     3  haha114514/No_Telstra_IPv6, meta-llama/codellama, siddharthvaddem/openscreen
  dormant     18  apachecn/awesome-cs-courses-zh, cits4407/assignment1, ijpq/cs267 ...
Proposed: unstar 3, keep 18.
```

已归档、被禁用、标为 deprecated 的仓库，默认建议取消 star。判断 deprecated 必须有仓库自己的描述或 topic 作依据，报告里会引出它找到的那几个词。两年没有提交的仓库只列出来，默认保留：做完了的库和没人管的库从外面看是一样的，你特意留着的课程笔记和学习路线也不该被顺手清掉。你自己名下的仓库从不会被标出。

每一个都由你决定。说一句「已归档的取消，其他保留」就照办；不想取消 star、只是不想再看到的，应该收进一个 Archive 收藏夹，那是 `star-lists` 的活。

## 怎么保证不出事

你没看过清单、没点头之前，一个都不会取消。取消前它先存一份备份，记下每个仓库和它所在的收藏夹，取消后再读回你的 star 列表，确认每一个都已经没有了。`restore` 会重新加 star，并把每个仓库放回原来的收藏夹。GitHub 不保留原来的 star 时间，恢复的 star 会按新加的排序，这是恢复唯一找不回来的东西。

和 `star-lists` 一样，它能在一台什么都没装的机器上跑：`run.sh doctor --install` 从发布页下载 GitHub CLI 和 uv，逐个核对官方公布的 SHA-256，装进你的用户目录，不用 `sudo`。

## 它不做什么

它不把 star 归进收藏夹，不加新的 star，不归档或删除你自己的仓库，也不碰通知。改过名的仓库不会被标出，因为 GitHub 会自动跟随改名。它写出的所有文件一律是英文，不管你用什么语言提要求。
