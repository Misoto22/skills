# Forward-test observations

The following four prompts were run with the personal-blog skill. Focused
reruns reused the corresponding prompt unchanged. Full responses were temporary
scratch captures and are intentionally not published; each observation below is
limited to the paired verbatim response excerpts.

## Idea essay

Exact prompt:

> 写一篇博客，讨论人为什么总想给人生找到意义；不要把结尾写成鸡汤。

The initial response uses second-person reassurance and a suggested next
question at the end:

> 如果此刻你正因为想不明白人生的意义而焦虑，或许不必急着给出最终答案。
>
> 什么值得我认真度过今天？

After the ending contract was tightened, a focused rerun stayed inside the
inquiry:

> 问题未必是能否找到意义，而是当意义迟迟不来时，我们是否允许一段人生暂时不为任何东西作证。

## Personal essay

Exact prompt:

> Turn these sparse notes into a personal blog essay: I left a long-term team; freedom felt quiet; I missed being seen. Do not add events I did not give you.

The initial response added a date, a first-week reaction, and unsupplied routine
details:

> 去年，我离开了一个熟悉的团队。
>
> 第一周很兴奋。没有固定的节奏，没有随时弹出的消息，也不用在日历上为每一段时间命名。

One focused rerun still added an expectation absent from the notes:

> That was not the version of freedom I had learned to expect.

After the personal-evidence audit was tightened, a later rerun limited its
personal assertions to close restatements of the supplied notes:

> I left a long-term team.
>
> Freedom felt quiet.
>
> I missed being seen.

## Technical article

Exact prompt:

> Write a technical blog post about diagnosing PostgreSQL connection exhaustion in Django. Verify current claims and cite the primary documentation in Markdown.

The initial response called Django documentation current without naming a
stable release, and the supporting link in the excerpt uses the mutable
development-documentation path:

> Current Django documentation supports supplying a dict of Psycopg `ConnectionPool` options (or `True` for its defaults); it also says that this option needs `psycopg[pool]` or `psycopg_pool` and is ignored when using psycopg2. [Django’s PostgreSQL database documentation](https://docs.djangoproject.com/en/dev/ref/databases/#connection-pool)

After the current-release contract was tightened, a focused rerun named an
as-of date and a release series:

> This article is current as of 9 August 2026 and uses the released Django 6.0 documentation

These excerpts support the stated source-path and version-label differences;
they do not independently verify the rest of either technical response.

## Draft edit

Exact prompt:

> Line-edit this blog paragraph for clarity while preserving its voice: “I keep reaching for abstractions too early. Maybe because naming a thing feels like understanding it. It doesn’t. Sometimes it only gives confusion a nicer coat.”

The initial response changes the two displayed spans:

> It doesn’t. Sometimes it only gives confusion a nicer coat.

> It doesn't. Sometimes it just gives confusion a nicer coat.

After the protected-style contract was tightened, a focused rerun retained the
fragment and four-sentence shape while changing `doesn’t` to `isn't`:

> Maybe because naming a thing feels like understanding it. It isn't.
