import os

import pandas as pd
import requests
import streamlit as st

# Set API_BASE in Render's environment settings; falls back to localhost for local runs.
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000/api/v1").rstrip("/")
# A free Render service can take ~60s to wake from sleep, so allow a long timeout.
REQUEST_TIMEOUT = 90

st.set_page_config(page_title="AI Revenue Recovery", layout="wide")
st.title("⚡ AI Revenue Recovery Agent")

if st.button("Refresh Data"):
    st.rerun()

try:
    analytics = requests.get(f"{API_BASE}/analytics", timeout=REQUEST_TIMEOUT).json()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Webhooks", analytics["total_transactions"])
    col2.metric("Revenue at Risk", f"₹{analytics['total_revenue_at_risk']:,}")
    col3.metric("Revenue Recovered", f"₹{analytics['total_revenue_recovered']:,}")
    col4.metric("Still Retrying", f"₹{analytics['total_revenue_recovering']:,}")
    col5.metric("True Recovery Rate", f"{analytics['recovery_rate_percentage']}%")

    st.divider()
    st.subheader("📋 Transactions")
    transactions = requests.get(f"{API_BASE}/transactions", timeout=REQUEST_TIMEOUT).json()

    if transactions:
        df = pd.DataFrame(transactions)
        display_df = df[["id", "transaction_id", "amount", "status", "retry_count", "failure_reason", "created_at"]]
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        st.subheader("🔍 Audit Trail")
        selected_id = st.number_input("Transaction ID", min_value=1, step=1, value=int(df["id"].iloc[0]))
        if st.button("View Audit Trail"):
            audit_resp = requests.get(f"{API_BASE}/transactions/{selected_id}/audit", timeout=REQUEST_TIMEOUT)
            if audit_resp.status_code == 200:
                audit_df = pd.DataFrame(audit_resp.json())
                st.dataframe(audit_df[["created_at", "action", "detail"]], use_container_width=True, hide_index=True)
            else:
                st.info("No audit trail found for that transaction ID.")
    else:
        st.info("No payment failures detected yet. Run the simulation script to populate data.")

except Exception as e:
    st.error(
        f"Cannot reach the backend at {API_BASE}. If it's a free Render service it may be "
        f"waking up (about 1 minute), so click Refresh. Error: {e}"
    )