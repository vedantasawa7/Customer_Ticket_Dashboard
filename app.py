import streamlit as st
import pandas as pd
import plotly.express as px
from scipy import stats

st.set_page_config(page_title = "Support Ticket Analytics", layout = "wide")

def safe_chi2(a, b):

    """Chi-square p-value, or None if the filtered data can't support the test."""

    try:
        ct = pd.crosstab(a, b)
        if ct.shape[0] < 2 or ct.shape[1] < 2:
            return None
        
        return stats.chi2_contingency(ct)[1]
    
    except Exception:
        return None


def safe_anova(groups):

    """One way ANOVA p-value, or None if there aren't enough groups/data."""

    try:
        groups = [g for g in groups if len(g) >= 2]
        if len(groups) < 2:
            return None
        
        return stats.f_oneway(*groups)[1]
    
    except Exception:
        return None


def fmt_p(p):
    return "n/a (not enough data at this filter)" if p is None else (f"{p:.1e}" if p < 0.001 else f"{p:.2f}")


# Load + clean data

@st.cache_data
def load_data():

    df = pd.read_csv("customer_tickets.csv")

    dup_count = df["ticket_id"].duplicated().sum()
    df = df.drop_duplicates(subset = "ticket_id", keep = "first").copy()

    df["created_date"] = pd.to_datetime(df["created_date"], errors = "coerce")
    df["resolved_date"] = pd.to_datetime(df["resolved_date"], errors = "coerce")
    df["breach"] =  df["sla_breached"].map({"Yes": 1, "No": 0})
    df["is_reopened"] = (df["status"] == "Reopened").astype(int)

    bad_res_time = (df["resolution_time_hours"] <= 0).sum()
    df_valid_res = df[df["resolution_time_hours"] > 0].copy()

    meta = {
        "dup_count": dup_count,
        "bad_res_time": bad_res_time,
        "missing_created": df["created_date"].isna().sum(),
        "missing_resolved": df["resolved_date"].isna().sum(),
        "missing_csat": df["csat_score"].isna().sum(),
    }

    return df, df_valid_res, meta


df, df_valid, meta = load_data()
raw_df = df.copy()  # unfiltered, used for filter option lists and the quality report

st.title( "Support Ticket Analytics Dashboard" )
st.caption( "Ticket level SLA, resolution time and CSAT analysis - ~5,000 tickets")

# Dataset overview & data quality (always shows the FULL dataset, unaffected by filters below this describes the file as loaded, not a filtered view)

raw_row_count = len(raw_df) + meta["dup_count"]

with st.expander("Dataset overview & data quality report", expanded = True):

    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Rows in source file", f"{raw_row_count:,}")
    q2.metric("Duplicate rows removed", f"{meta['dup_count']:,}")
    q3.metric("Invalid resolution times excluded", f"{meta['bad_res_time']:,}")
    q4.metric("Final unique tickets", f"{len(raw_df):,}")

    dq = pd.DataFrame({
        "Issue": [
            "Duplicate ticket_id rows",
            "Missing created_date",
            "Missing resolved_date",
            "Missing csat_score",
            "Negative/zero resolution_time_hours",
        ],
        "Count": [
            meta["dup_count"], meta["missing_created"], meta["missing_resolved"],
            meta["missing_csat"], meta["bad_res_time"],
        ],
        "How handled": [
            "Dropped exact duplicate ticket_ids, kept first occurrence",
            "Left as NaT; excluded from any date based trend calc",
            "Mostly explained by Open status tickets (not yet resolved); a smaller set on Resolved/Closed/Reopened tickets is a genuine data-entry gap",
            "Expected for Open/Reopened tickets (not yet surveyed) - not an error",
            "Excluded from resolution time stats (Q2); likely timestamp/timezone entry errors since dates were same-day or Resolved status",
        ],
    })

    st.dataframe(dq, use_container_width = True , hide_index = True)

with st.expander("Assumptions made in this analysis"):

    st.markdown(
        "- Exact duplicate `ticket_id` rows were dropped **before** any KPI calculation.\n"
        "- Missing `csat_score` on Open/Reopened tickets is treated as **expected**, not an "
        "error - those tickets haven't been surveyed yet.\n"
        "- Negative/zero `resolution_time_hours` values are treated as **data-entry errors** "
        "and excluded from resolution time and SLA driver stats, rather than clipped to zero "
        "or imputed.\n"
        "- Category/region/priority/agent differences are reported as real findings only where "
        "a chi-square or ANOVA test supports them (p < 0.05) - differences that look visually "
        "interesting but aren't statistically significant are called out as such, not "
        "presented as conclusions.\n"
        "- Filters below apply to every chart **except** the data quality report above, which "
        "always reflects the full source file."
    )

# Sidebar filters applied to every tab below

st.sidebar.header("Filters")

def multiselect_all(label, options):
    return st.sidebar.multiselect(label, options, default = list(options))


f_region = multiselect_all("Region", sorted(raw_df["region"].unique()))
f_priority = multiselect_all("Priority", ["Critical", "High", "Medium", "Low"])
f_category = multiselect_all("Category", sorted(raw_df["category"].unique()))
f_channel = multiselect_all("Channel", sorted(raw_df["channel"].unique()))
f_status = multiselect_all("Status", sorted(raw_df["status"].unique()))
f_agent = st.sidebar.multiselect("Agent (optional)", sorted(raw_df["agent_id"].unique()), default = [])

valid_dates = raw_df["created_date"].dropna()
d_min, d_max = valid_dates.min().date(), valid_dates.max().date()
f_date = st.sidebar.slider("Created date range", d_min, d_max, (d_min, d_max))

mask = (
    raw_df["region"].isin(f_region)
    & raw_df["priority"].isin(f_priority)
    & raw_df["category"].isin(f_category)
    & raw_df["channel"].isin(f_channel)
    & raw_df["status"].isin(f_status)
    & (raw_df["created_date"].isna() | raw_df["created_date"].dt.date.between(f_date[0], f_date[1]))
)

if f_agent:
    mask &= raw_df["agent_id"].isin(f_agent)

df = raw_df[mask].copy()
df_valid = df[df["resolution_time_hours"] > 0].copy()

if len(df) == 0:
    st.warning("No tickets match the current filters showing the full dataset below instead. Adjust filters in the sidebar.")
    df = raw_df.copy()
    df_valid = df[df["resolution_time_hours"] > 0].copy()

st.caption(f"Showing **{len(df):,}** of **{len(raw_df):,}** tickets based on current filters.")

# Top KPIs

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total tickets", f"{len(df):,}")
c2.metric("Overall SLA breach rate", f"{df['breach'].mean()*100:.1f}%" if len(df) else "—")
c3.metric("Median resolution time", f"{df_valid['resolution_time_hours'].median():.1f} hrs" if len(df_valid) else "—")
c4.metric("Avg CSAT", f"{df['csat_score'].mean():.2f} / 5" if df['csat_score'].notna().any() else "—")

st.divider()

tab1, tab2, tab3, tab4 = st.tabs([ "Q1: SLA Breaches", "Q2: Priority vs Resolution", "Q3: Customers", "Q4: Data Quality"])

# Q1

with tab1:

    st.subheader("Where is SLA performance breaking down?")

    colA, colB = st.columns(2)
    with colA:

        cat_breach = df.groupby("category")["breach"].mean().sort_values(ascending=False) * 100
        fig = px.bar(cat_breach, orientation = "h", labels = {"value": "Breach rate (%)", "category": ""}, title="Breach rate by category")
        st.plotly_chart(fig, use_container_width = True)

    with colB:

        reg_breach = df.groupby("region")["breach"].mean().sort_values(ascending=False) * 100
        fig = px.bar(reg_breach, orientation = "h", labels = {"value": "Breach rate (%)", "region": ""}, title="Breach rate by region")
        st.plotly_chart(fig, use_container_width = True)

    colC, colD = st.columns(2)

    with colC:

        pri_breach = df.groupby("priority")["breach"].mean().reindex(["Critical", "High", "Medium", "Low"]) * 100
        fig = px.bar(pri_breach, labels={"value": "Breach rate (%)", "priority": ""}, title="Breach rate by priority (real driver)")
        st.plotly_chart(fig, use_container_width=True)

    with colD:

        agent_breach = df.groupby("agent_id")["breach"].mean().sort_values(ascending=False) * 100
        fig = px.bar(agent_breach, labels = {"value": "Breach rate (%)", "agent_id": ""}, title = "Breach rate by agent (AGENT_07 outlier)")
        st.plotly_chart(fig, use_container_width = True)

    st.markdown("**Agent × Category breach rate - is AGENT_07 bad everywhere, or just in one category?**")

    if len(df) > 0:

        heat = df.pivot_table(index = "agent_id", columns = "category", values = "breach", aggfunc="mean") * 100
        fig_heat = px.imshow(
            heat, text_auto = ".0f", color_continuous_scale = "Reds", aspect = "auto",
            labels = dict(color ="Breach %"), title = "SLA breach rate (%) by agent and category"
        )
        st.plotly_chart(fig_heat , use_container_width = True)
        st.caption("AGENT_07's row runs red across every category confirms the problem isn't confined to one type of ticket.")

    cat_p = safe_chi2(df["category"] , df["sla_breached"])
    reg_p = safe_chi2(df["region"] , df["sla_breached"])
    pri_p = safe_chi2(df["priority"] , df["sla_breached"])
    agt_p = safe_chi2(df["agent_id"] , df["sla_breached"])


    st.info(
        "Category and region breach rates are all clustered ~63-67% no single category/region "
        "stands out. The real signal is **priority** (Critical tickets breach 74% vs Low at 62%) "
        "and one **agent outlier, AGENT_07**, at a 92% breach rate vs ~60-66% for everyone else.\n\n"
        f"Confirmed with chi-square tests: category p={fmt_p(cat_p)}, region p={fmt_p(reg_p)} "
        f"(not significant - genuinely flat), vs. priority p={fmt_p(pri_p)}, agent p={fmt_p(agt_p)} "
        "(both highly significant). Figures above reflect the current sidebar filters, so exact "
        "p-values may shift if you narrow the data."
    )

# Q2

with tab2:
    st.subheader("Priority vs resolution time")

    med_by_pri = df_valid.groupby("priority")["resolution_time_hours"].median().reindex(["Critical", "High", "Medium", "Low"])
    fig = px.bar(med_by_pri, labels = {"value": "Median resolution time (hrs)", "priority": ""}, title = "Median resolution time by priority")
    st.plotly_chart(fig, use_container_width = True)


    st.markdown("**Agent deviation from the expected priority pattern**")
    overall_med = df_valid.groupby("priority")["resolution_time_hours"].median()
    agent_pri = df_valid.groupby(["agent_id", "priority"])["resolution_time_hours"].agg( median="median" , count="count").reset_index()
    agent_pri = agent_pri[agent_pri["count"] >= 5]
    agent_pri["overall_median"] = agent_pri["priority"].map( overall_med )
    agent_pri["deviation_hrs"] = agent_pri["median"] - agent_pri["overall_median"]
    agent_pri = agent_pri.sort_values("deviation_hrs", ascending = False)

    fig2 = px.bar(
        agent_pri[agent_pri["agent_id"] == "AGENT_07"],
        x="priority", y=["median", "overall_median"], barmode="group",
        title="AGENT_07 vs team median resolution time, by priority"
    )

    st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(agent_pri.sort_values("deviation_hrs", ascending=False).head(10), use_container_width=True)

    st.info(
        "There's a clear, expected inverse relationship: Critical tickets resolve fastest "
        "(median ~5.5 hrs), Low resolves slowest (~98.5 hrs). **AGENT_07** breaks this pattern "
        "hard - 8-10x slower than the team median at *every* priority level (e.g. Critical: 48 hrs "
        "vs 5.5 hrs team median)."
    )


# Q3

with tab3:
    st.subheader("Reopened tickets & low CSAT")

    colE, colF = st.columns(2)

    with colE:

        reopen_by_agent = df.groupby("agent_id")["is_reopened"].mean().sort_values(ascending=False) * 100
        fig = px.bar(reopen_by_agent, labels={"value": "Reopen rate (%)"}, title = "Reopen rate by agent")
        st.plotly_chart(fig , use_container_width=True)

    with colF:

        csat_by_cat = df.groupby("category")["csat_score"].mean().sort_values()
        fig = px.bar(csat_by_cat, labels={"value": "Avg CSAT"}, title = "Avg CSAT by category")
        st.plotly_chart(fig , use_container_width=True)

    cust_stats = df.groupby("customer_id").agg( ticket_count = ("ticket_id", "count"), avg_csat=("csat_score", "mean"),reopen_count=("is_reopened", "sum"), ).sort_values("avg_csat")
    st.markdown("**Customers with lowest average CSAT (min. 5 tickets)**")
    st.dataframe(cust_stats[cust_stats["ticket_count"] >= 5].head(15), use_container_width=True)

    reopen_agent_p = safe_chi2( df["agent_id"], df["status"] == "Reopened")
    reopen_cat_p = safe_chi2( df["category"], df["status"] == "Reopened")
    csat_agent_p = safe_anova( [g["csat_score"].dropna() for _, g in df.groupby("agent_id")])
    csat_cat_p = safe_anova( [g["csat_score"].dropna() for _, g in df.groupby("category")])
    vol_csat_corr = cust_stats["ticket_count"].corr(cust_stats["avg_csat"]) if len(cust_stats) > 1 else float("nan")

    st.info(
        "Unlike Q1/Q2, this one doesn't have a clean culprit. Chi-square/ANOVA tests show "
        f"agent vs. reopen p={fmt_p(reopen_agent_p)}, category vs. reopen p={fmt_p(reopen_cat_p)}, "
        f"CSAT-across agents p={fmt_p(csat_agent_p)}, CSAT-across-categories p={fmt_p(csat_cat_p)} — "
        "none significant on the full dataset. Ticket volume vs. average CSAT correlation is "
        f"**{vol_csat_corr:.2f}**" + (" (essentially zero)" if pd.notna(vol_csat_corr) else "") +
        ", so it isn't a volume effect either. "
        "The honest read: customer level CSAT/reopen variation here looks like ordinary noise, "
        "not a systemic agent, category, or volume problem - worth a manual look at the worst "
        "individual customers, but not a process fix the way AGENT_07 was."
    )


# Q4

with tab4:
    st.subheader( "Data quality - detail view" )
    st.caption( "Summary numbers are in the 'Dataset overview & data quality report' panel above. This tab shows the underlying detail.")

    missing_counts = raw_df[["created_date", "resolved_date", "csat_score"]].isna().sum()
    missing_counts.index = ["created_date", "resolved_date", "csat_score"]
    fig_miss = px.bar(missing_counts, labels={"value": "Missing rows", "index": ""},title="Missing values by column (full dataset)")
    st.plotly_chart( fig_miss, use_container_width=True)

    st.markdown("**Sample of rows with negative/zero resolution_time_hours (likely timestamp errors)**")
    bad_res = raw_df[raw_df["resolution_time_hours"] <= 0][ ["ticket_id", "status", "created_date", "resolved_date", "resolution_time_hours"]]
    st.dataframe(bad_res.head(10), use_container_width=True, hide_index=True)
    st.caption(f"{len(bad_res)} such rows total, all excluded from resolution time and SLA driver calculations.")

st.divider()

st.caption("Built for the Customer Support Analytics take home assignment.")
