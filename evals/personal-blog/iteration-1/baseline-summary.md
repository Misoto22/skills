# Baseline observations

The following four prompts were run without the personal-blog skill. Full
responses were temporary scratch captures and are intentionally not published;
each observation below is limited to the paired verbatim response excerpts.

## Idea essay

Exact prompt:

> 写一篇博客，讨论人为什么总想给人生找到意义；不要把结尾写成鸡汤。

The response opens with an everyday scene, later prescribes questions and
actions, and ends in reassurance despite the requested ending:

> 有时候，焦虑并不是因为我们真的遇到了什么大事。
>
> 它可能出现在一个很普通的晚上：工作做完了，手机也刷累了，窗外安静下来。

> - 我最近真正累的是什么？
> - 有没有一件事能让我今天稍微舒服一点？
> - 我想靠近谁，或想远离什么？
> - 如果不要求自己立刻变好，我愿意先做哪一步？

> 先好好睡一觉，和信任的人聊聊天，去晒一会儿太阳，把手头的一件事做完。

> 如果此刻你还没有找到所谓的人生意义，也没关系。你不必急着证明自己的人生值得。
>
> 这些本身，就是意义开始生长的地方。

## Personal essay

Exact prompt:

> Turn these sparse notes into a personal blog essay: I left a long-term team; freedom felt quiet; I missed being seen. Do not add events I did not give you.

The response adds a date, a first-week reaction and routine, and later actions
that the prompt did not supply:

> 去年，我离开了一个待了很久的团队。

> 第一周，我很兴奋。
>
> 我睡到自然醒，给自己做咖啡，打开电脑时不再有一连串等待回复的消息。

> 离开团队之后，我开始有意识地建立一些新的「被看见」的方式。和朋友固定聊近况，找同行交换正在解决的问题，把零散的想法写下来发出去，也在完成一件小事时告诉某个人。

The published excerpts contain no visible placeholder for missing personal
material and do not establish how the response derived the writer's voice.

## Technical article

Exact prompt:

> Write a technical blog post about diagnosing PostgreSQL connection exhaustion in Django. Verify current claims and cite the primary documentation in Markdown.

The response distinguishes three possible limits rather than treating every
failure as the same pool:

> There are three ceilings to distinguish:
>
> 1. **PostgreSQL capacity.** The server declines a new backend because connection slots are already allocated.
> 2. **A proxy or driver pool capacity.** PgBouncer or another pooling layer makes callers wait because all of *its* permitted server connections are checked out.
> 3. **Application concurrency.** Django workers have enough requests needing database time that existing connections remain occupied or too many persistent connections accumulate.

This excerpt supports that three-layer distinction; it does not by itself audit
the response's remaining claims or citations.

## Draft edit

Exact prompt:

> Line-edit this blog paragraph for clarity while preserving its voice: “I keep reaching for abstractions too early. Maybe because naming a thing feels like understanding it. It doesn’t. Sometimes it only gives confusion a nicer coat.”

The response ends:

> I keep reaching for abstractions too early. Maybe because naming a thing feels like understanding it. It doesn't. Sometimes it just gives confusion a nicer coat.

Compared with the supplied paragraph, the excerpt changes the typographic
apostrophe in `doesn’t` to ASCII and replaces `only` with `just`; the other
sentences remain unchanged.
