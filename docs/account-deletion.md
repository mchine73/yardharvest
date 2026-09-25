# Deleting an account

`DELETE /api/auth/account` — the right to erasure, and what it actually does.

## Why the row survives

46 tables carry a foreign key to `user` and almost every one is `NOT NULL`, so
`db.session.delete(user)` either fails on a constraint or cascades through
records that belong to other people: the dues ledger a treasurer reconciles,
a comment thread the garden was having, the plot history explaining who had
bed 12 last season.

So the row stays as a **tombstone** with every personal field scrubbed, and
`deleted_at` marks it. Anything still pointing at it renders as "Deleted user".

This is erasure as the GDPR defines it, not as the word sounds — Art. 17(3) is
explicit that the right is not absolute.

## Three buckets

| | What | Examples |
| --- | --- | --- |
| **purge** | Theirs alone, of no interest to anyone else | cart, notifications, waitlist places, likes, RSVPs, shift signups, memberships, analytics |
| **release** | Theirs to hold, someone else's to use next | plot assignments (back to `available`), checked-out resources, listings deactivated |
| **retain** | Legally required, or also somebody else's | dues, orders, payouts, expenses, refunds; comments, photos, messages — content kept, attribution anonymised |

Releasing plots matters more than it looks: a bed still assigned to a deleted
account is one nobody can claim, and a waitlist that never moves.

## The one hard blocker

`community_garden.organizer_id` is `NOT NULL`. A garden owner cannot be erased
without orphaning the garden and everyone in it, so they are asked to transfer
it first. The refusal names the gardens and says what to do — a refusal that
doesn't is just a dead end, and this is the one screen where a dead end reads
as the product refusing to let you leave.

A connected Stripe payout account with payouts enabled also blocks, so funds
can't end up attached to an account nobody can reach.

## Two gates

- **The password**, so a session someone walked away from — or a stolen token —
  can't destroy an account on its own.
- **Typing `DELETE`**, so it can't be reached by clicking through.

Rate limited to 3/hour.

## Before anything is destroyed

`GET /api/auth/account/deletion-check` returns `blockers`, `removed` and
`retained` in plain words. A confirmation dialog that only asks "are you
sure?" is not informed consent to lose your data.

## Afterwards

A confirmation email goes to the address that was just erased. It earns the
exception: it completes their own request, and **if the request wasn't theirs
it's the only thing that will tell them.** Sent after the commit and
best-effort, so a mail failure can't leave an account half-deleted.

## Still missing

**There is no UI.** The endpoint exists; nothing in the app calls it, so the
right is not yet self-service and the privacy policy says "ask us" rather than
claiming settings that don't exist. Building the screen is what makes this
real for a user.

Data export (portability) is also still manual.
