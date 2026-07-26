# Playbook: lead magnet funnel (systeme.io free plan)

Build to this playbook. Where it disagrees with the general design guidance,
this wins.

## What this funnel is for

A free download in exchange for an email address. The list is the asset —
one person who downloads the freebie can be sold to repeatedly as the
catalogue grows. The download exists to make someone want the full product,
never to replace it.

## Free-plan limits — check before building

The free plan allows 3 funnels, 1 automation rule, and 1 workflow.

Call `get_funnels` before creating anything and count what already exists.
If there are already 3, stop and say so instead of creating a fourth. Tell
the account owner how many funnel slots are left when you finish.

The single automation rule is the tightest of those limits — people hit it
within days. Never suggest spending it on something trivial like a tagging
rule. A workflow accepts unlimited actions in any order, including waits, so
the entire email sequence belongs inside the one workflow and the rule stays
free for something that genuinely needs it later.

## Shape

In systeme.io this is **Funnels → Create → Build an audience**, which gives
exactly the two pages below. Create them in this order:

1. `squeeze` — the opt-in page
2. `opt_in_thank_you_page` — the thank-you page

## The opt-in page has one job

Nothing on this page may compete with the email field. This is the rule most
worth following and the easiest to break by reflex.

- **One section.** A hero, containing a headline, a short subhead, and the
  Form. That is the whole page.
- **No** menu or navigation bar, **no** footer, **no** social links, **no**
  second call to action, **no** testimonials, **no** FAQ, **no** stats band,
  **no** logos, **no** countdown. Nothing clickable except the form button.
- The Form asks for **email only** unless told otherwise. Every extra field
  costs signups.
- A reassurance line under the button — "No spam. Unsubscribe any time." —
  as Text, not as a link.

Shape of the copy: name the reader's specific problem in their own words,
say what the download is in one line, say what it gets them. Concrete, not
clever.

> You get about twelve minutes with your doctor.
> Don't spend eight of them remembering.
>
> A free one-page checklist to take to your next appointment — so you walk
> out having said the thing you actually came to say.

## The thank-you page is the warmest moment you get

Most people leave it blank. It's free real estate and this person just
raised their hand. Two sections:

1. **Confirmation.** Tell them it's on its way, and to check spam or
   promotions if it hasn't landed in ten minutes — and to drag it to the
   main inbox so the next one arrives properly. That sentence is worth real
   money in deliverability; do not drop it.
2. **One soft sell.** Name the paid product, say plainly that the free thing
   is one piece of it, and give a single button. One link. No urgency.

## Tone

Useful first, warm always, never pushy. Assume a reader who has been sold to
badly and dismissed repeatedly. One hard-sell line and she's gone.

Never use: countdown timers, "limited time", "only X left", manufactured
deadlines, or any scarcity that isn't literally true. This buyer clocks a
fake deadline instantly and it costs trust permanently.

Never invent a statistic. If a claim would need a number, either leave the
number out or write it as a bracketed placeholder and list it in your
closing summary as something to verify against a source before publishing.
The same goes for testimonials — do not put invented quotes on these pages.

## The email sequence

You cannot build this. systeme.io's tools cover funnels, pages, contacts,
tags and newsletters — there is no workflow or automation tool, so the
sequence has to be created by hand in **Automations → Workflows → Create**,
triggered on this funnel's opt-in form being submitted.

Everything goes inside that one workflow, waits included. Do not propose a
second workflow or an automation rule.

So write it out instead. After the pages are saved, output the full sequence
as copy the account owner can paste in:

| Email | Timing | Job |
|---|---|---|
| 1 | immediately | Deliver the download. One genuinely useful tip on using it. Set expectations for what's coming. Give explicit permission to unsubscribe — it cuts spam complaints. |
| 2 | wait 2 days | Pure value, no pitch at all. This is what earns the right to send email 4. |
| 3 | wait 3 days | The insight that reframes their problem. Practical, two concrete things they can do. |
| 4 | wait 4 days | The soft pitch. One product, one link, one mention. No urgency, no countdown. Close by saying it's fine if the free thing was all they needed. |

Four emails, nine days, one workflow — inside the free tier.

Optional fifth email, six days after the pitch, if the account owner wants
it: a sequence close that says you won't clutter their inbox, names what
you're building next, and asks them to reply and say what they'd find
useful. "Just reply and tell me" is worth more than it looks — replies are
free product research, and mailbox providers treat them as a strong positive
signal. Offer it; don't add it unasked.

Give each email a subject line and full body, with `[first name]` and
`[download link]` as placeholders.

## Things to tell the account owner when you finish

- Upload the download file in systeme.io (Contacts → Files — file storage is
  included on the free plan) and paste its URL into email 1. You have no way
  to upload it yourself.
- The optional segmentation dropdown ("where are you in this?") **cannot be
  built through the page tools** — the form only supports email, first name,
  last name and phone. Add it in the page editor by hand, or capture it
  later with tags.
- Test it end to end on your own address, signing up as a stranger would,
  before pointing any traffic at it. Confirm the download arrives, the link
  works, and email 2 fires on schedule. This is the step people skip, and a
  broken lead magnet burns every visitor you send it.
- How many of the 3 free funnel slots are now used.
