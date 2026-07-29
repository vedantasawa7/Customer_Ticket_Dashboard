# Business Answers

Candidate name: Vedant Nandkishor Asawa

---

## Q1. Which category or region has the worst SLA breach rate, and what's actually driving it?

**Answer:**

Nothing stands out at the category or region level on its own breach rates
are tightly clustered: category ranges 63.8% (Other) to 66.9% (Account
Access), and region ranges 62.6% (East) to 66.6% (West). A 3 point spread
across 5 categories / 5 regions is noise, not a signal, given ~700-1,600
tickets per category and ~1,000 per region.

The real drivers are two things that cut across category/region:

1. **Priority.** Critical tickets breach SLA 74% of the time vs. 62% for Low
   priority - a real, consistent gradient (Critical 74% → High 69% →
   Medium 63% → Low 62%).
2. **One agent.** AGENT_07 breaches SLA 92% of the time, vs. 60-66% for every
   other agent. That's the single biggest lever in this dataset - an agent
   issue, not a category or region issue.

Confirmed with chi-square tests rather than just eyeballing the spread:
category vs. breach → p=0.58, region vs. breach → p = 0.33 (not significant,
i.e. genuinely flat), while priority vs. breach → p < 0.0001 and agent vs.
breach → p < 0.0001 (both highly significant). I also checked whether
AGENT_07 is simply handed a harder mix of tickets (more Critical/complex
categories) - their priority mix ( 10.7% Critical, 21.4% High ) and category
mix are nearly identical to everyone else's, so the 92% breach rate isn't
explained by ticket difficulty; it's a real agent level effect.

**How you checked it (query/method):**

`df.groupby('category')['breach'].mean()`, same for `region`, `priority`,
and `agent_id`, on `sla_breached` mapped to 0/1, after de-duplicating on
`ticket_id`; `scipy.stats.chi2_contingency` on each factor vs. breach to
confirm which differences are statistically real; cross-tab of AGENT_07's
priority/category mix vs. everyone else's to rule out a confound.

---

## Q2. Is there a relationship between priority and resolution time? Which agent(s) deviate, and by how much?

**Answer:**

Yes, a clear and expected inverse relationship: median resolution time is
5.5 hrs for Critical, 18.3 hrs for High, 51.1 hrs for Medium, and 98.5 hrs
for Low. Higher urgency tickets get resolved faster, as intended.

**AGENT_07 breaks this pattern badly** - at every single priority level
their median resolution time is 8-10x the team median:

| Priority | Team median (hrs) | AGENT_07 median (hrs) | Multiple |
|---|---|---|---|
| Critical | 5.5 | 48.0 | ~8.7x |
| High | 18.3 | 171.6 | ~9.4x |
| Medium | 51.1 | 458.5 | ~9.0x |
| Low | 98.5 | 841.9 | ~8.5x |

No other agent deviates by more than ~15 hours from the team median at any
priority level - AGENT_07 is an isolated, extreme outlier, not part of a
broader trend.

**How you checked it (query/method):**

Filtered out non-positive `resolution_time_hours` (data errors, see Q4),
then `groupby(['agent_id','priority'])['resolution_time_hours'].median()`
compared against the team wide median per priority.

---

## Q3. Which customer(s) show frequent reopened tickets or low CSAT scores? Is that agent-driven, category-driven, or something else?

**Answer:**

Individual customers do show a spread e.g. CUST_089 averages 3.36 CSAT,
CUST_084 has 9 reopened tickets but when tested properly, **none of it is
agent-driven or category-driven**: a chi-square test of agent vs. reopen
status gives p=0.49, category vs. reopen gives p=0.78, and an ANOVA of CSAT
across agents gives p=0.36, across categories p=0.58 none of these are
close to significant. I also checked whether it was a volume effect (do
high-ticket-count customers just rack up more low scores by exposure?) -
the correlation between a customer's ticket count and their average CSAT is
only -0.09, essentially zero.

The honest answer is: **there's no systemic driver in this data.** The
customer level CSAT spread (std ≈0.22 around a mean of ~4.0, for customers
with 5+ tickets) looks like ordinary ticket to ticket randomness averaging
out slightly differently per customer, not a pattern tied to who served
them, what category it was, or how many tickets they filed. The specific
customers flagging worst (CUST_089, CUST_037, CUST_012, CUST_084, CUST_133)
are worth a manual look in case there's a real complaint behind the number,
but statistically they don't point to a fixable process issue the way
AGENT_07 does in Q1/Q2.

**How you checked it (query/method):**

`groupby('customer_id')` on reopen count and average CSAT to find the worst
individuals; then chi-square tests (`scipy.stats.chi2_contingency`) for
agent-vs-reopen and category-vs-reopen, one-way ANOVA
(`scipy.stats.f_oneway`) for CSAT across agents and across categories, and
a Pearson correlation between per-customer ticket volume and average CSAT.

---

## Q4. What data quality issues did you find, and how did you handle them?

**Answer:**

- **15 duplicate `ticket_id` rows** (exact duplicates). Dropped, keeping the
  first occurrence.
- **1,038 missing `resolved_date`** - mostly explained by the 511 tickets
  still `Open` (correct, not yet resolved), but ~527 rows on
  Resolved/Closed/Reopened tickets are missing a resolved date, which is a
  genuine data entry gap. Left as null and excluded from date based
  calculations rather than guessing a value.
- **1,021 missing `csat_score`** - fully explained by ticket status: it's
  missing exactly on the 511 `Open` and 510 `Reopened` tickets, which
  haven't been surveyed yet. Not an error, just expected missingness.
- **88 rows with negative or zero `resolution_time_hours`** - e.g. a ticket
  created and resolved the same day showing -18.2 hours. Almost certainly a
  timestamp/timezone calculation error upstream. Excluded these from all
  resolution time statistics (Q2) rather than including or clipping them,
  since the sign is unreliable, not just the magnitude.
- **72 missing `created_date`.** Left null; excluded from any date-based
  trend analysis.

**No** negative/invalid values were found in `first_response_time_hours`,
and no `resolved_date` was earlier than `created_date` once the negative
resolution time rows were set aside.

---

## Q5. If you could track exactly one metric weekly to catch support problems early, what would it be and why?

**Answer:**

**SLA breach rate by agent, weekly**, rather than an aggregate/company wide
number. The aggregate breach rate (65.2%) barely moves week to week and
would have hidden AGENT_07's 92% breach rate inside a normal looking overall
average - this dataset is a good example of how a single bad fit agent can
silently drag down outcomes for a chunk of customers while the topline
metric looks stable. An agent level weekly breakdown surfaces an outlier
like this within a week or two instead of it taking a quarter's worth of
data (and a one off audit) to notice.

---

## Anything else you'd flag if this were a real dataset at FreightFox?

**Answer:**

I'd want to understand why AGENT_07 is such an outlier before treating it
as purely a performance issue  it could be a new agent, someone
consistently assigned the hardest/most complex tickets, or someone with a
data logging problem (e.g. timestamps not updating until manual close). The
number itself (92% breach, 8-10x resolution time) is too extreme to be
"just a slower agent" it's worth checking ticket assignment logic and
timestamp capture for that agent specifically before acting on it.
