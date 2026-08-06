---
name: tempering
description: Rewrites blunt, sarcastic, or impatient workplace messages into professional ones that retain the underlying request, offering three registers from collegial to formally documented. Use when a draft is addressed to a colleague, manager, client, vendor, or cross-team counterpart and carries visible frustration — sarcasm, blame, exasperation, ultimatums, or lines such as "are you serious", "脑子有问题", "到底做不做", "有没有一个准信". Trigger on requests to make a message professional, soften it, tone it down, check whether it is too harsh, or work out how to say something without damaging the relationship, including 润色一下, 帮我改得客气点, 这样发出去会不会太冲, 怎么说才不得罪人. Also handles the reverse direction — plain-language interpretation of corporate phrasing when asked what a message actually means, 说人话, or decode this. Not for marketing copy, resumes, blog posts, or grammar cleanup without interpersonal stakes.
license: MIT
metadata:
  version: "0.6.0"
---

# Tempering

Convert a message the sender cannot send into one they can, without discarding the request it carries.

## Why the obvious rewrite fails

Built-in polish features fail the same way every time: they remove the emotion and the substance together. "Is anyone actually going to decide this or not?" becomes "Would you be able to share the final decision or an estimated timeline?" — grammatically professional, and now containing no deadline, no consequence, and no reason for the recipient to prioritise a reply. The urgency was carried entirely by the tone, and the rewrite deleted it.

The operating principle: **remove the attack on the person, preserve the pressure on the problem.**

## Method

Every effective rewrite combines the five transforms below. Nothing further is required; additions beyond these are usually padding.

| # | Transform | Before | After |
|---|---|---|---|
| 1 | Person to artefact — assess the work, not the judgement behind it | You're being an idiot | There are a few things in this approach I can't follow |
| 2 | Emotion to impact — replace the sender's state with the cost to the business | This is infuriating | If this stays blocked, Friday's release slips |
| 3 | Accusation to dated request — an accusation looks backwards, a request looks forwards | Are you going to do this or not | Can we lock this down by Wednesday |
| 4 | Open complaint to closed question — a complaint can be ignored, a direct question cannot | Still no straight answer | Is it A or B? If neither works I'll schedule against C |
| 5 | Preserve the recipient's position — an exit route produces cooperation, a corner produces defence | You clearly didn't test this | Is it possible this case wasn't covered? |

Transforms 3 and 4 carry the weight. A rewrite that loses the date or the specific question has failed regardless of how well it reads.

## Output format

Produce all three registers, in this order, each labelled. The sender chooses according to how much relationship capital the situation justifies spending.

```
**Reading of the draft**: <one line stating what the raw message indicates about the
sender's actual situation — how many times this has been raised, what is now at risk.
This is diagnostic, and informs which register is appropriate.>

**1. Collegial** — working relationship is sound, timeline is not yet critical
<message>

**2. Direct but measured** — courteous, while making clear the matter is being tracked
<message>

**3. On the record** — suitable for copying in a manager, and for being read again in three months
<message>
```

Say so plainly and stop if the draft is already appropriate. Not every message needs revision.

## Constraints

Read [shared/tone.md](shared/tone.md) and [shared/format.md](shared/format.md) before producing any register. They carry the apology, inflation, filler, fact-preservation, channel, and language rules for this plugin, and are deliberately not restated here.

Two things they do not cover:

**Reverse mode is exempt from the filler ban.** Decoding corporate phrasing requires quoting it.

**All three registers, every time.** The register is the sender's call, not yours. Do not recommend one unless asked, except in the cases below.

## When softening is the wrong response

In these situations the direct version is the professional version, and the recommendation is to send it rather than revise it:

- Safety, harassment, discrimination, or any matter with a legal or compliance dimension. Ambiguity here creates liability; the account should be plain and factual.
- A hard deadline that has already passed with material consequences. One clear sentence is appropriate; register 1 is not.
- A third or subsequent follow-up on the same unanswered thread. Escalating courtesy reads as diminishing authority. Go straight to register 3, and note that copying in an additional recipient is now the relevant instrument.
- The sender is drafting something they have no intention of sending. Confirm a rewrite is wanted before producing one.

## Worked examples

See [examples.md](references/examples.md) for five annotated cases covering instant messaging, email, upward communication to a manager, and the reverse direction. Read that file when a rewrite involves an unfamiliar channel or an unusually high-stakes relationship, or when the sender asks why a particular version was chosen.

## Reverse mode: plain-language interpretation

When given corporate phrasing and asked what it means, apply the transforms in reverse and answer in one line each, without embellishment. Follow with the response the reading warrants.

| Received | Reading |
|---|---|
| Let's align on the granularity and park this for next sprint | No one is free this week, and probably not next week either |
| I'd love to get your thoughts before we lock anything in | The decision is made |
| Thanks for the feedback, we'll keep iterating | This will not change |
| Let's take this offline | Stop raising this in the group |
| Let's evaluate this a bit further | No one is willing to own it |
| Just flagging this for visibility | A record is being created |

Keep this mode brief. Where a message is straightforwardly polite with nothing underneath, say so — manufacturing subtext is a worse failure than missing it.

## Composition with other skills

This skill selects register and rewrites content. It does not own channel formatting or transport. Where a channel-specific skill is also active — the `email` skill in this plugin governs policy, rendering, and send verification — settle register and wording here first, then hand the chosen version to that skill. Never restate its rules; a rewrite that changes a recipient, a policy-fixed string, or a protected fact is that skill's failure to catch, not this skill's licence to introduce.
