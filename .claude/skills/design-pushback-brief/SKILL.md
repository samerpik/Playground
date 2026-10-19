---
name: design-pushback-brief
description: Write a short, evidence-based brief that pushes back on a risky design request from a stakeholder (PM, exec, client, engineering lead) and proposes a better path. Use whenever the user wants to push back on, say no to, challenge, or talk someone out of a design change, or asks "how do I convince my PM/boss/client not to..." — e.g. adding friction or extra form fields, dark patterns, cramming in features, copying a competitor, skipping research, last-minute scope changes, removing accessibility or safety steps, or a redesign driven by one person's taste. Also use when the user pastes a stakeholder message and is annoyed or unsure how to respond. Not for critiquing a mockup's visual quality (use design-critique) or writing a spec.
---

# Design Pushback Brief

Turn "I think this request is a mistake" into a one-screen brief a stakeholder will actually read, and that ends in a decision instead of an argument.

The goal is a better decision, not winning. A good brief makes it easy for the stakeholder to say yes to a better option — or to knowingly accept the risk of their original request.

## Step 1: Decide whether to push back at all

Pushback spends trust. Before drafting anything, check whether the request would materially hurt at least one of: users, revenue, reliability, security/legal/accessibility, or the product's main goal.

- **No material harm** (taste, minor polish, reversible tweak): tell the user plainly that it isn't worth pushing back on, and suggest how to do the request well or run it as a cheap test. Stop there unless they insist.
- **Material harm**: continue.

Saying "don't fight this one" is a valid and often the most useful output.

## Step 2: Gather what you need

Work from what's already in the conversation. Ask only for what's missing and would change the brief — at most three questions, in one message. If the user wants speed, proceed with stated assumptions instead.

- The request, ideally in the stakeholder's own words
- Who asked, and what they're measured on (their goal or metric)
- Why the user thinks it's risky
- Evidence available: product data, research findings, support tickets, past incidents, standards (e.g. WCAG)
- Constraints: deadline, how committed the stakeholder already is, who makes the final call

## Step 3: Build the argument

**Steelman the request.** Identify the real goal behind it ("more qualified leads", "look as modern as competitor X", "hit the launch date"). State it in the stakeholder's terms. People accept pushback when they can see their goal was understood — and often the goal is fine and only the proposed solution is the problem.

**Name the risk concretely.** One to three specific consequences, not "users will hate it". Tag every claim with its evidence strength so the reader can weigh it:
- `[data]` — numbers from this product
- `[research]` — user research or tests run here
- `[standard]` — an external standard or regulation
- `[judgment]` — the designer's professional opinion

Never invent statistics or studies. If the argument rests on judgment, say so and propose a way to get real evidence. An honest `[judgment]` plus a cheap test is more persuasive than a made-up number that gets challenged.

**Offer options, not a veto.** Two or three, always including:
1. **The request as-is**, with the risk stated and explicitly accepted by the decision owner
2. **An alternative** that hits their goal with less risk
3. **A cheap test** to settle it with evidence (A/B test, prototype test with five users, staged rollout), when one is feasible

Recommend one option and say why.

**End with a clear ask.** What decision is needed, from whom, by when. Make "yes to the original request" an acceptable outcome — the designer advises, the owner decides. The exception is anything illegal, unethical, or an accessibility regression that excludes users: recommend escalating rather than committing.

## Output

Write the brief first, then notes for the user. Keep the brief under ~250 words: stakeholders skim, and a long rebuttal reads as defensive.

```markdown
**Re: [request in a few words]**

**Recommendation:** [one sentence — the option you recommend]

**What you're going for:** [their goal, in their terms]

**The risk:**
- [specific consequence] [evidence tag]

**Options:**
| Option | Gets you | Costs / risk |
|---|---|---|
| A. As requested | ... | ... |
| B. [alternative] | ... | ... |
| C. [test] | ... | ... |

**What I need:** [decision] from [person] by [date].
```

Then, outside the brief, a short **Notes for you** section:
- The two most likely objections and a one-line response to each
- What to concede if pressed, and what not to
- Whether to send it async or raise it live (live is usually better when the stakeholder is senior or already committed)

Adapt the format to the medium. For a Slack or chat reply, compress it to 4–6 sentences with the same order: goal, risk, recommendation, ask. Match the reader's vocabulary: business outcomes for execs, cost and complexity for engineering leads, user impact for PMs. Avoid design jargon.

## Example

**Request:** "Add company size, role, and phone number to the signup form — sales needs better lead quality." (VP Sales)

**Re: Extra fields on signup**

**Recommendation:** Ask for these fields after activation, not at signup (Option B).

**What you're going for:** Better-qualified leads for sales without slowing growth.

**The risk:**
- Every added required field is another reason to abandon signup; we'd likely trade signups for lead data `[judgment]`
- Signup completion is currently [X]% `[data — fill in]`; even a few points lost compounds across every channel
- Phone as a required field tends to get fake entries, which hurts lead quality rather than improving it `[judgment]`

**Options:**
| Option | Gets you | Costs / risk |
|---|---|---|
| A. As requested | All fields on every lead, immediately | Lower signup completion, some fake data |
| B. Ask after activation | Same fields from engaged users | Data arrives a few days later |
| C. A/B test on 20% of traffic | A real number for the tradeoff | Two weeks before deciding |

**What I need:** Go/no-go on B (or C) from you by Friday, so it makes the next sprint.
