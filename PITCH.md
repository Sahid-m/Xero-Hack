# Voca — the pitch

**One line:** Xero already proved small businesses want to do their books over WhatsApp. Xero just
walked away from it. Voca is that channel, rebuilt properly, running entirely on Xero's own API.

---

## 1. The problem — a regulatory deadline the UK's smallest businesses aren't ready for

**Making Tax Digital for Income Tax Self Assessment (MTD ITSA)** rolls out in three mandatory waves:

| Wave | Mandated from | Threshold | Who |
|---|---|---|---|
| 1 | **6 April 2026** (already live) | Income over £50,000 | **864,000** sole traders and landlords |
| 2 | 6 April 2027 | Income over £30,000 | further ~1.1M |
| 3 | 6 April 2028 | Income over £20,000 | further ~1.0M |

*(Source: HMRC/gov.uk, Feb 2026 — "Act now: 864,000 sole traders and landlords face new tax rules
in two months")*

By 2028, an estimated **~2.9 million self-employed people and landlords** — out of roughly
**4.57 million self-employed workers in the UK** (ONS, Q1 2026) — will be legally required to keep
digital records and file quarterly, not annually. Most of them have never used accounting software.
Many are still on a shoebox of receipts and a bank statement.

**Every one of these people needs a Xero-shaped product in their pocket in the next 24 months, whether
they want one or not.** That's not a marketing opportunity — it's a compliance deadline with a fixed
customer count and a fixed date.

**The burden this creates is real and measured**, not hypothetical: Sage's own 2025 UK research put
small business owners at **24 lost days a year** on financial admin — roughly 13 months of work for
12 months of pay. A typical UK bookkeeper costs **£100–£150+/month** even for straightforward
sole-trader books (median £150.50/month, 6 Figure Bookkeeper's 2025 UK pricing survey) — a real cost
against a razor-thin margin for the exact people MTD is about to force online.

---

## 2. Why this is Xero's problem to lose, specifically

Here's the part that should worry Xero, not just excite a hackathon judge: **Xero already built this.**

Xero's own AI agent, **JAX (Just Ask Xero)**, launched chat access over **WhatsApp, SMS, and email** —
the exact "invoice Coastal Plumbing $2,400" conversational flow this hackathon bounty is asking for.
And per Xero's own release notes, **that WhatsApp/SMS/email access is being discontinued, effective
1 June 2026** — JAX chat survives only inside the Xero app itself.

Read that back: **Xero validated the demand, shipped the feature, and pulled it back to inside the
app** — right as ~864,000 people are being legally forced to start keeping digital records for the
first time, most of them exactly the kind of non-technical, phone-first user who will never
voluntarily open an accounting app.

That gap doesn't stay empty. **76% of UK adults use WhatsApp daily** (Ofcom, 2025) — it's the most-used
messaging platform in the country, already open on every one of those 864,000 phones. If Xero doesn't
own that surface, whoever does gets first contact with the wave of new digital-record-keepers MTD is
about to create — and first contact usually means the customer's whole ledger, not just a feature.
The AI-bookkeeping-automation category is heating up independently of this (Dext/AutoEntry already
sit across Xero, QuickBooks, Sage, and FreeAgent as a neutral automation layer; Intuit is pushing its
own "agentic AI" accounting push hard in 2025–2026). **Every month WhatsApp-native bookkeeping isn't a
first-party Xero experience is a month those 864,000-and-counting new mandatory users can be captured
by something that isn't Xero.**

Voca closes that exact gap — the one Xero opened and then closed again — using nothing but Xero's
public API.

---

## 3. Why Voca, and why it's better than "just re-launch JAX on WhatsApp"

Voca isn't a chat wrapper around Xero. It's a small number of concrete guardrails that make a
WhatsApp bookkeeper trustworthy enough to actually hand your books to:

| Risk with any conversational bookkeeper | What Voca does about it |
|---|---|
| LLM mishears "two hundred" as "two thousand" | **Confirm-before-write** on every financial action, no exceptions |
| User says "$200," bot silently books £200 | Explicit **currency-mismatch guardrail** — flags it and asks, never guesses |
| Fuzzy contact matching "East Repair" → wrong existing "Eastside Club" contact | Matching **only acts on real matches**; creates a new contact rather than silently misattributing a transaction |
| Receipt OCR reads a photo wrong | States uncertainty out loud ("this doesn't look like a fuel receipt...") instead of confidently guessing |
| "Add it" said twice by accident | Receipts are marked **added** after the write — a stray second "yes" can't double-bill |
| Reconciliation matches the wrong bank line to the wrong invoice | Only proposes matches above a **confidence threshold** (amount + date + contact-name similarity), and only acts after explicit confirmation |
| Bot goes silent on a slow multi-step Xero write | **Acks in under a second**, does the real work in the background, delivers the answer a few seconds later — no dead air |
| "Am I MTD-compliant right now?" has no easy answer for a sole trader | **MTD quarter readiness check** — which HMRC quarter you're in, the exact submission deadline and days remaining, and the income/expenses/net profit that quarter's digital update will be built from, computed live from Xero |

And every single one of those actions is a **real Xero API call** — invoices, bills, payments, bank
transactions. Nothing is simulated locally. The WhatsApp thread is a control surface; Xero stays the
ledger of record, which is exactly what makes this safe to pitch to an accountant, not just a sole
trader.

**The full loop, in one thread:** photograph a receipt → it's read and categorised → confirm → it's
a real bill in Xero → ask Voca to reconcile → it matches the bank payment to that bill and closes both
out → ask "am I ready for my MTD update?" → the exact quarter, deadline, and numbers HMRC will ask for,
answered from live Xero data in under a second. Receipt → expense → reconciliation → **the actual
regulatory deadline this whole pitch is about** — entirely from the app already open on the phone.

---

## 4. The 3-minute demo — as a story

**Cold open (20s).** *"Meet a plumber. April 2026. HMRC just told her she's now legally required to
keep digital tax records — quarterly, not annually. She's one of 864,000 people this happened to
this year alone. She has never opened accounting software in her life. She has WhatsApp open right
now, because everyone does — 76% of UK adults use it daily. That's the whole pitch: meet her there."*

**Beat 1 — the books, without opening Xero (25s).** She's just finished a job and grabs a receipt out
of her pocket. She texts a photo: *"here's my receipt."* Voca reads it — real vendor, real amount,
real category, straight off the photo, no typing. *"Add it"* — and it's a real bill in Xero, seconds
later. *(Flip to Xero on the projector: the bill is there.)* "No app. No login beyond the one she did
months ago. Just the thing she already had open."

**Beat 2 — closing the loop, not just logging it (35s).** Now the plumber asks Voca to check her
books against the bank: *"can you reconcile my bank transactions with my bills please."* Voca
cross-references what's actually moved in her bank account against what's still open in Xero, finds
a payment that matches a bill by amount, date, and supplier name, and asks her to confirm before
touching anything. She says yes. *(Flip to Xero: the bill flips to Paid, a real payment record
links it to the bank line.)* "That's the step bookkeeping software usually leaves for a human
squinting at two screens — done from a WhatsApp reply."

**Beat 3 — paying off the cold open (25s).** She asks the question this whole story started with:
*"am I ready for my MTD update?"* Voca answers instantly — which HMRC quarter she's in, the exact
digital-update deadline, days remaining, and this quarter's income, expenses, and net profit, live
from Xero. *"Remember her at the start, legally required to file quarterly? That's the actual
question she has, and it's the one thing every other 'AI bookkeeper' demo skips."*

**Beat 4 — the moment Xero should feel this (30s).** *"Here's the uncomfortable part. Xero built
exactly this reach — JAX over WhatsApp, SMS, email. And this June, Xero turned it off. Meanwhile
864,000 people just became legally required to do exactly what we showed you, and another two
million are on the way by 2028. That's not our stat to win. It's Xero's stat to lose — to whoever
else decides to meet these people on the phone they're already holding."*

**Close (15s).** *"Receipt in, bill recorded, payment matched, tax deadline answered — every number
on that screen came from the real Xero API. Nobody opened Xero. Nobody needed to. Xero already proved
people want this. We're the version that's safe enough to actually ship it."*

---

## Sources

- [gov.uk — Act now: 864,000 sole traders and landlords face new tax rules in two months](https://www.gov.uk/government/news/act-now-864000-sole-traders-and-landlords-face-new-tax-rules-in-two-months)
- [gov.uk — Find out if and when you need to use Making Tax Digital for Income Tax](https://www.gov.uk/guidance/find-out-if-and-when-you-need-to-use-making-tax-digital-for-income-tax)
- [ICAEW — Up to 3 million individuals may need to comply with MTD](https://www.icaew.com/insights/tax-news/2025/aug-2025/up-to-3-million-individuals-may-need-to-comply-with-mtd)
- [ONS — Self-employment jobs by industry (JOBS04)](https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/datasets/selfemploymentjobsbyindustryjobs04)
- [Sage UK — The hidden admin burden on small businesses](https://www.sage.com/en-gb/company/digital-newsroom/2025/05/09/the-hidden-admin-burden-on-small-businesses/)
- [6 Figure Bookkeeper — UK Pricing Report](https://www.6figurebookkeeper.com/pricing-report/)
- [Xero Central — Release notes for Just Ask Xero (JAX)](https://central.xero.com/s/article/Release-notes-for-Just-Ask-Xero-JAX)
- [Xero — Just Ask Xero (JAX) product page](https://www.xero.com/us/ai-in-accounting/jax/)
- [Ofcom — Online Nation Report 2025](https://www.ofcom.org.uk/siteassets/resources/documents/research-and-data/online-research/online-nation/2025/online-nations-report-2025.pdf)

*Two figures above (the exact 2027/2028 per-wave splits, and the "24 days/year" Sage stat's underlying
methodology) come from secondary reporting on primary sources rather than a page I could fetch and
quote directly — solid enough to say live, worth a caveat if a judge asks to see the underlying page.*
