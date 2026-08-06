# Worked examples

Five annotated cases. Each shows the diagnostic reading, the three registers, and a note on why the highest register works.

## Contents

1. Instant messaging — direct insult
2. Instant messaging — chasing a decision
3. Email — blocked by a peer
4. Email — raising a problem upward
5. Reverse mode — interpreting received messages

---

## 1. Instant messaging — direct insult

**Draft**: Honestly, do you even think before you write this stuff?

**Reading**: The point has been explained at least twice and the same approach keeps coming back. The sender is out of patience, not out of argument.

**1. Collegial**
> I don't think I explained this well — want to walk through it together?

**2. Direct but measured**
> I think we're working from different assumptions here. Can we sync before this goes any further? Reworking it later gets expensive.

**3. On the record**
> This version doesn't match what we agreed on Wednesday. I'm holding off until we've confirmed which one we're building — can you let me know which to follow?

**Note**: register 3 introduces a date and a stated consequence. The draft contained neither — only frustration — so the frustration had to be converted into them rather than deleted. A rewrite producing only "let's discuss this again" would have removed the sender's position entirely.

---

## 2. Instant messaging — chasing a decision

**Draft**: is anyone actually going to decide this or not

**Reading**: The sender is waiting on someone else's decision, and the wait has begun consuming their own schedule.

**1. Collegial**
> Has the direction on this been settled? Want to sequence my week around it.

**2. Direct but measured**
> I've parked this one — give me a shout once the direction is set and I'll pick it back up, rather than build something we throw away.

**3. On the record**
> Still no decision on this, and my schedule has been blocked behind it since Monday. Can we get a direction this week? If not, I'll proceed on option A and re-estimate if we change course later.

**Note**: the standard platform rewrite of this message ("Would you be able to share the final decision or an estimated timeline?") sits correctly at register 2 but carries no consequence, which is why it tends not to produce a reply. Register 3 works because it states what will happen by default in the absence of an answer. Few things prompt a decision as reliably as the prospect of someone else making it.

---

## 3. Email — blocked by a peer

**Draft**: Third time asking. I can't ship anything until you review this PR. Do you actually care?

**Reading**: The sender is accountable for a delivery date controlled by someone else. This is a resourcing problem presenting as an interpersonal one.

**1. Collegial**
> Subject: PR #482 — any chance of a look this week?
>
> Hey — no rush if you're buried, but #482 is the last thing between me and the release. Happy to walk you through it if that's faster than reading it cold.

**2. Direct but measured**
> Subject: PR #482 — blocked, need ~20 min of review
>
> Following up on #482. It's blocking the release branch, so I'm holding everything behind it. Could you get to it by Thursday? If reviewing it whole is the problem, I can split it into two smaller PRs.

**3. On the record**
> Subject: PR #482 — release blocked since 28 Jul
>
> #482 has been open for review since 28 July, and the release branch has been frozen behind it since Monday. I need a review by Thursday 14:00 to hold the sprint date. If that isn't workable, let me know who else can review it and I'll route it there instead.

**Note**: register 3 contains no adjective describing the recipient — only dates, states, and an alternative. That is precisely what makes it safe to copy to a third party. The offer to reroute is transform 5: it gives the recipient a way out that does not require admitting fault.

---

## 4. Email — raising a problem upward

**Draft**: There's no way this scope fits in two weeks. Who promised the client that?

**Reading**: A commitment was made without consulting the person who has to deliver it. The sender needs the scope or the date changed, and needs it on record that they raised it early.

**1. Collegial**
> About the two-week estimate on Project X — can we go through the scope together? Against the current requirements list I'm getting a bit over three weeks, and I'd like to work out what could move to phase two.

**2. Direct but measured**
> Subject: Project X timeline — scope or date needs to move
>
> Against the requirements list as confirmed, my estimate is 3.5 weeks, against the two weeks committed to the client. The gap is mostly [Module A] and the data migration.
>
> Two options: move [Module A] to phase two and deliver the rest inside two weeks, or keep the full scope and move delivery to [date]. Let me know which you'd prefer — if we settle it this week I can still adjust the schedule.

**3. On the record**
> Subject: Project X delivery risk — decision needed by [date]
>
> Flagging a delivery risk while it is still solvable. Against the requirements list confirmed on [date], the estimate is 3.5 weeks against the two weeks committed to the client — a gap of 1.5 weeks, concentrated in [Module A] and the data migration.
>
> Two workable options: (1) [Module A] moves to phase two and the remainder ships on the original date; (2) the full scope is kept and delivery moves to [date].
>
> A decision is needed by [date]; past that point either option still affects final delivery. Please confirm which one to proceed on.

**Note**: upward communication is the case where register 3 is most often the correct choice rather than the aggressive one. It presents options instead of objections, and it establishes a timestamped record that the risk was raised while it could still be solved. The draft's accusatory question ("who promised the client that?") is dropped entirely — assigning blame does not move the date, and raising it invites a defensive response from the one person whose cooperation is needed.

---

## 5. Reverse mode — interpreting received messages

Answer in one line, without embellishment, then state what response the reading warrants.

| Received | Reading |
|---|---|
| Let's align on the granularity and park this for next sprint | No one is free this week, and probably not next week either |
| I'd love to get your thoughts before we lock anything in | The decision is made |
| Thanks for the feedback, we'll keep iterating | This will not change |
| Let's take this offline | Stop raising this in the group |
| Let's evaluate this a bit further | No one is willing to own it |
| Just flagging this for visibility | A record is being created |

Where the reading matters, follow with the appropriate action. For "just flagging this for visibility", that is usually: reply on the same thread with the factual position, so the record contains both sides.

Do not manufacture subtext. When a message is simply courteous with nothing underneath, saying so is the correct answer.
