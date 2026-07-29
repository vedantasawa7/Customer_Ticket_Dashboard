# Customer Support Analytics Dashboard

A Streamlit dashboard analyzing ~5,000 customer support tickets to find where
SLA performance is breaking down and which agents/categories need attention.

## Live URL


## Setup (local)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the URL Streamlit prints (usually `http://localhost:8501`).

## Approach

1. Loaded `customer_tickets.csv` (5,015 rows) and did an initial data quality
   pass: found 15 duplicate `ticket_id` rows, 73 missing `created_date`
   values, 1,040 missing `resolved_date` values, 1,023 missing `csat_score`
   values, and 88 rows with negative/zero `resolution_time_hours`.
   Duplicates were dropped; missing dates/CSAT were mostly explained by
   ticket status (Open/Reopened tickets haven't been resolved or surveyed
   yet); negative resolution times were excluded from resolution time
   calculations as likely data entry errors.
2. Grouped and aggregated in pandas to compute SLA breach rate, resolution
   time, reopen rate, and CSAT across category, region, priority, and agent.
3. Ran chi-square tests (category/region/priority/agent vs. SLA breach and
   vs. reopens) and one way ANOVA (CSAT across agents/categories) rather than
   eyeballing which differences look real - this changed one conclusion
   (see Q3: an initial "volume-driven" read didn't survive testing and was
   replaced with the honest "no significant driver found" finding).
4. Built the dashboard in Streamlit (four tabs, one per business question)
   with Plotly charts, so the same numbers and significance tests behind
   `BUSINESS_ANSWERS.md` are visible and explorable. Added sidebar filters
   (region, priority, category, channel, status, agent, date range) so every
   chart is interactive rather than static, plus an Agent × Category
   breach-rate heatmap to visually confirm AGENT_07's issue isn't confined
   to one ticket type, and an upfront data-quality/assumptions panel.

## Key finding

SLA breach rate looks flat across category/region (~63-67%, no outlier), so
that's a dead end on its own. The real signal is **priority** (Critical
breaches at 74% vs Low at 62%) and one **agent outlier - AGENT_07** - who
breaches SLA 92% of the time and resolves tickets 8-10x slower than the team
median at every priority level. See `BUSINESS_ANSWERS.md` for full detail.

## Repo structure

```
.
├── app.py                 # Streamlit dashboard
├── customer_tickets.csv   # source data
├── requirements.txt
├── README.md
└── BUSINESS_ANSWERS.md
```
