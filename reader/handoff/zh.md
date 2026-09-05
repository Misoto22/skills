`handoff` 让你在一个 agent 里正进行的对话，实时出现在另一个 agent 的历史里。在 Claude Code 里干活，关掉，打开 Codex —— 对话就在那儿。反过来也一样。

## 为什么这件事其实很小

两边收敛到了同一套东西，大概是互相借鉴的结果。

它们在相同的事件上触发 hook，配置格式也一样 —— Codex 的 `hooks.json` 用的就是 Claude Code 的 schema，连环境变量名都一样。而且两边都把历史写成「一行一个 JSON 对象」，边聊边追加，而不是结束时才存。所以任意一边的 hook 都能读到自己上次看过之后新增的部分，翻译成对面的格式写过去。

剩下的只是字段名对照：这边的 `type:assistant` 是那边的 `response_item/message`，`content[tool_use]` 是 `function_call`，以此类推。整个转换就是这张表。

## 它具体做什么

每次工具调用、每轮结束，hook 读取当前对话新增的行，翻译后追加到对面的镜像里。镜像是一条**独立的对话**，有自己的 id：往对面正开着的历史里追加，会跟那个工具自己的写入抢同一个文件，而一份写坏的记录比一份重复的记录代价大得多。

```
python3 scripts/handoff.py install     # 两边都注册 hook
python3 scripts/handoff.py status      # 配了哪些、各自读到哪儿
python3 scripts/handoff.py uninstall   # 摘掉 hook，镜像保留
```

`install` 会改两个你可能已经放了别的 hook 的文件 —— `~/.claude/settings.json` 和 `~/.codex/hooks.json`。它只碰命令里点名了这个脚本的条目，装第二次是替换而不是叠加。Codex 按哈希信任 hook，所以下一次 Codex 会话会让你确认一次。

## 它不是什么

**它是一份可读的记录，不是可续跑的回放。** Codex 用自己的密钥加密推理内容，Claude 给 thinking 块签名，两边的签名都没法从对方的文本重建。所以推理内容能保下来的部分是纯文本摘要。你可以在对面读完整段对话、接着往下做；但不能像它本来就跑在那边一样直接 resume。

**交接之后两份就各自长了。** 在一边继续，不会回流到另一边。

**它不会拖慢任何东西。** hook 不往 stdout 写任何内容，永远以 0 退出 —— hook 的输出会被跑它的 agent 当成反馈读进去，而一个失败的 hook 能中断一轮对话。做镜像属于记账，所以它的失败记在状态文件里、通过 `status` 浮出来，而不是打断你手头的活。

## 有一处是猜的

Codex 的 hook 载荷不会说它正在写哪个文件，所以 Codex 这一侧退回到「该目录下最近修改的那个 rollout」。同一个目录同时开两个 Codex 会话，有可能配错。配对之后会锁定它实际读过的那个文件，所以猜错的结果是多出一份错的镜像，而不是把对的那份写坏。
