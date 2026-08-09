# Baseline observations

The supplied raw baseline captures show the following observable behavior. The
excerpts are verbatim from those captures.

## Idea essay

`baseline-idea.md` opens immediately with a Markdown heading and contains no
surrounding assistant preface or delivery commentary. It uses a repeated,
sectioned progression from an everyday scene through explanation, questions,
reassurance, and a concluding restatement. Its opening and closing are:

> 有时候，焦虑并不是因为我们真的遇到了什么大事。
>
> 它可能出现在一个很普通的晚上：工作做完了，手机也刷累了，窗外安静下来。

> 如果此刻你还没有找到所谓的人生意义，也没关系。你不必急着证明自己的人生值得。
>
> 这些本身，就是意义开始生长的地方。

The result also gives a prescribed list of small next questions and actions:

> - 我最近真正累的是什么？
> - 有没有一件事能让我今天稍微舒服一点？
> - 我想靠近谁，或想远离什么？
> - 如果不要求自己立刻变好，我愿意先做哪一步？

> 先好好睡一觉，和信任的人聊聊天，去晒一会儿太阳，把手头的一件事做完。

## Personal essay

`baseline-personal.md` presents a complete first-person narrative with specific
events, routines, interpretations, and later actions:

> 去年，我离开了一个待了很久的团队。

> 第一周，我很兴奋。
>
> 我睡到自然醒，给自己做咖啡，打开电脑时不再有一连串等待回复的消息。

> 离开团队之后，我开始有意识地建立一些新的「被看见」的方式。和朋友固定聊近况，找同行交换正在解决的问题，把零散的想法写下来发出去，也在完成一件小事时告诉某个人。

The supplied capture contains the completed prose only; it does not show a
visible placeholder for omitted personal material or a separate account of how
the writer's voice was derived.

## Technical article and draft edit

`baseline-technical-edit.md` contains a fully structured technical article after
`Request A`, including a thesis, numbered diagnosis and remediation sections,
code blocks, and documentation links. For example:

> There are three ceilings to distinguish:
>
> 1. **PostgreSQL capacity.** The server declines a new backend because connection slots are already allocated.
> 2. **A proxy or driver pool capacity.** PgBouncer or another pooling layer makes callers wait because all of *its* permitted server connections are checked out.
> 3. **Application concurrency.** Django workers have enough requests needing database time that existing connections remain occupied or too many persistent connections accumulate.

The capture then ends after this separate `Request B` draft fragment:

> I keep reaching for abstractions too early. Maybe because naming a thing feels like understanding it. It doesn't. Sometimes it just gives confusion a nicer coat.

No response after `Request B` is present in the supplied raw file, so the
capture does not provide observable evidence of how an edit would preserve that
draft's voice.
