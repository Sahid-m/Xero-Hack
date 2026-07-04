# Voca (working title)
### "Xero without ever opening Xero" — voice-first setup & operation agent
### Xero Encode Hackathon — Bounty 01: Small Business Productivity Powerhouse

---

## 1. One-liner

A voice agent that onboards a non-technical business owner onto Xero through a 90-second conversation, then lets them run their books entirely by talking — invoices, expenses, questions — while perfect, compliant records build in Xero in the background.

**Founder-felt origin story (use verbatim in pitch):** "I'm a CS student who's won 11 hackathons. I opened Xero, spent 10 minutes, and couldn't work out where to start. If I bounced off it, what chance does a plumber have?"

## 2. The numbers (the pitch's backbone)

### The regulatory freight train: Making Tax Digital for Income Tax
- **April 2026 (already live):** sole traders & landlords with gross income over £50,000 must keep digital records and report quarterly via MTD-recognised software. First wave identified from 2024/25 self-assessment returns.
- **April 2027:** threshold drops to **£30,000**. **April 2028:** drops to **£20,000** — pulling most sole traders into scope.
- Quarterly digital updates replace the single annual return; late submissions accrue penalty points with a **£200 fine at 4 points**.
- Paper records and bare spreadsheets are no longer sufficient — software (or bridging software) is mandatory.

**Pitch framing:** millions of people who have *never used accounting software* are being legally forced onto it in three annual waves, starting now. They are precisely the users who bounce off Xero's UI. The onboarding cliff is about to become a national problem — and Xero's biggest growth bottleneck.

### The market
- **~5.6 million** UK private sector businesses; **4.1 million** are sole proprietorships/partnerships with **no employees** — the exact "will never learn a chart of accounts" demographic.
- Sole traders spend **31% of their working time on financial admin** (micro businesses: ~15 hours/week, per a Starling study); **32%** of micro business leaders call accounting the **most stressful part** of running their business.
- The human alternative: UK bookkeepers charge **£20–40/hour**; sole traders typically pay **£100–200/month** just for basic compliance.
- Xero's own benchmark: businesses using its automated actions save an average of **22 hours/month** — cite this, then position Voca as extending that saving to people who can't get past the setup screen.

### The value equation (one slide)
"31% of a sole trader's time, or £150/month for a bookkeeper — versus a conversation. MTD just made this mandatory for 4 million people. Voice is the only interface they already know how to use."

## 3. Positioning (the JAX defense)

Judges will say: "JAX already does conversational Xero." The inversion:

| | JAX | Voca |
|---|---|---|
| Lives | Inside Xero's UI | Phone / no UI at all |
| User | Existing Xero users | People who will never learn Xero |
| Job | Copilot for the software | **Replacement for the interface** |
| Moment | While doing bookkeeping | While driving the van / closing the café |

JAX makes Xero easier. Voca makes Xero *invisible*. Different user, different moment, complementary — Voca feeds perfectly clean data into the org that JAX then operates on. (Say this: it positions you as extending Xero's strategy, not competing with their flagship.)

## 4. Product scope — setup + three verbs (resist everything else)

### A. The Setup Interview (the wedge, the killer demo)
A 90-second spoken onboarding. Agent asks; API configures in real time:

| Agent asks | Xero API action |
|---|---|
| "What kind of business?" → "a café" | Trim chart of accounts to sector-relevant codes (archive irrelevant defaults, add COGS/food & bev accounts) |
| "Sole trader or limited company?" | Set organisation financial settings / defaults |
| "Are you VAT registered?" → "yes, standard" | Configure tax rates + defaults on accounts |
| "Who are your regular suppliers?" | Create supplier contacts |
| "Who do you invoice, and what are your usual rates?" | Create customer contacts + item/service codes with prices |
| "How do you want invoices to look/behave?" | Branding theme basics + payment terms defaults |

⚠️ **Technical honesty (do not claim otherwise on stage):** the Xero API cannot create an organisation from nothing — orgs are created in Xero itself. Voca configures a fresh org. Demo framing: "You click Start Trial. That is the last time you ever touch this screen."

### B. Three daily verbs (prove the ongoing life)
1. **Invoice by voice:** "Bill the Hendersons — two hours' labour plus forty quid in parts." → Contact matched (fuzzy), line items built from stored rates, VAT applied, invoice drafted → agent reads it back → "send it" → sent via Xero.
2. **Expense by photo + voice:** Snap a receipt, say "materials for the Henderson job." → OCR + classification → bill/expense created, correctly coded, VAT extracted.
3. **Ask the books:** "How much am I owed right now?" / "Was last month better than the one before?" → Aged receivables / P&L via API, answered in plain speech.

### C. Explicitly roadmap-only (mention, don't build)
Payroll, bank feed reconciliation, MTD quarterly submission filing, multi-currency. One line: "Same architecture, more verbs."

### The trust layer — "audible accountable intelligence"
After every action, the agent states what it did *in accounting terms*: "Logged £40 to Materials, £8 VAT reclaimable, attached to the Henderson job." Xero's AI philosophy is that agents must show their work — Voca makes the audit trail *audible*. Every action also lands in Xero's own history/notes, so an accountant can review everything later. Use the phrase "accountable intelligence" in the pitch; it's Xero's own language.

## 5. Architecture

```
[Phone / mic]
   ↕ speech
[ElevenLabs Conversational AI]  ← proven stack (VaultMind / Pop the Bubble)
   ↕ intents + entities
[Claude — the brain]  ← Vercel AI SDK for Python (`ai` package)
   • conversation state machine (setup interview / operations mode)
   • entity resolution (fuzzy contact match, rate lookup, VAT logic)
   • drafts everything; confirms verbally before any write (require_approval hooks)
   ↕ tool calls
[Xero MCP server / Accounting API]  — Custom Connection app, Demo Company target
   • Organisation, Accounts (chart), TaxRates, Contacts, Items,
     Invoices, Bills/BankTransactions, Attachments (receipt image),
     Reports (Aged Receivables, P&L)
[Neon / Postgres] — session state, learned rates/preferences, interview progress
[Python API — FastAPI + Vercel AI SDK] — orchestration, `/api/chat` streams UI protocol for Next.js
```

Design rules:
- **Confirm-before-write.** Every mutating action is read back and confirmed verbally. (Also your answer to "what if it mishears £400 as £40?")
- **LLM drafts, deterministic layer validates.** VAT math and account codes are code-checked before posting — same "AI reads, code decides" split as Found Money.
- **Latency budget:** voice demos die on lag. Keep tool calls parallel where possible; target < 2s from utterance-end to spoken confirmation for the three verbs.

## 6. Demo spec (3 minutes, zero keyboard)

**Staging:** phone in hand with wired mic or push-to-talk (never open mic in a noisy hall), Xero on the projector behind you. Rehearse in the actual room. **Record a flawless backup video** — non-negotiable.

1. **Cold open (20s).** "I bounced off this screen in 10 minutes. From April, millions of sole traders are legally required to use it. Watch how they actually will." Show the untouched, confusing default Xero org.
2. **The interview (75s).** Live conversation: café, sole trader, VAT registered, two suppliers, usual customers and rates. Projector shows Xero populating in real time — chart trimming, contacts appearing. End: "You're set up. Tell me when you make your first sale."
3. **The three verbs (60s).** Invoice by voice (send it live) → receipt photo + one sentence → "how much am I owed?" answered aloud. Each action followed by the audible audit line.
4. **The flip (15s).** Show Xero one final time: clean org, correct codes, sent invoice, attached receipt. "She never opened this. Her accountant will love her anyway."
5. **The market close (10s).** "£50k threshold this year. £30k next. £20k after. Four million people are about to need this conversation."

**Failure drills:** if speech recognition stumbles live, the agent's confirm-before-write loop *is* the recovery ("Did you say forty or four hundred?") — rehearse one deliberate correction so the safety mechanism becomes a demo feature, not a bug.

## 7. Judge Q&A prep

| Question | Answer |
|---|---|
| "Isn't this just JAX?" | JAX is a copilot inside the UI for existing users. Voca removes the UI for people who'll never learn it. Different user, different moment — and Voca's clean data feeds JAX. |
| "Mishearing money amounts?" | Confirm-before-write on every mutation, deterministic validation of VAT/codes, full audit trail in Xero. Demo includes a live correction. |
| "Why voice, not a simpler app?" | The user is driving a van or running a till. Hands and eyes are taken. Voice is the only interface with zero learning curve — and 31% of their time is the prize. |
| "Accents / noisy environments?" | ElevenLabs ASR + constrained-domain prompting; push-to-talk pattern; and every action is confirmable/undoable. Honest answer: this is the hard engineering, which is why it's defensible. |
| "Business model?" | Per-seat subscription undercutting a £150/mo bookkeeper; distribution via accountants who want cleaner client data, and via MTD panic-wave marketing. |
| "Why won't Xero build it?" | They might — the App Store and XeroForce are exactly where this plugs in. That's the acquisition/partnership story, not a weakness. |

## 8. Build plan (hackathon weekend)

**Hour 0–2:** Custom Connection app + Demo Company; verify MCP/API writes (create a contact, an invoice) from a script.
**Day 1 AM:** Setup-interview state machine in Claude + the 6 configuration actions against the API.
**Day 1 PM:** ElevenLabs conversational loop wired to the orchestrator; interview working end-to-end by voice.
**Day 1 eve:** Verb 1 (invoice by voice) with fuzzy contact matching + confirm-before-write.
**Day 2 AM:** Verb 2 (receipt photo + voice) and Verb 3 (ask the books).
**Day 2 PM:** Audible audit lines, latency tuning, projector view polish. Rehearse ×3 with planted correction. Record backup video.

**Cut-line if time collapses (in order):** Verb 2 (receipt OCR) → Verb 3 → invoice *sending* (draft-only is fine). The minimum winning demo is: interview + one voice invoice + one live correction.

## 9. Voca vs Found Money — the portfolio view

- Different bounties (01 vs 03) → **separately winnable**, $6k combined ceiling.
- Shared plumbing: same Custom Connection, same Demo Company, same Python API / Neon / Claude orchestration layer.
- Solo: build Found Money (data-pipeline moat, lower demo risk). With a teammate who owns voice/frontend (the Oxford formula): run both.
- They even compose: Voca's onboarding interview could *end* with "…and by the way, you're eligible for £10,500 of Employment Allowance." One sentence connects the two products and doubles the wow.
