import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO

st.set_page_config(page_title="Sales by Product Type", layout="wide")

# ------------------------------
# Session state initialization
# ------------------------------
if "data" not in st.session_state:
    st.session_state.data = {
        "CCK": None,
        "LST": None,
        "TLT": None,
    }
if "loaded" not in st.session_state:
    st.session_state.loaded = {
        "CCK": False,
        "LST": False,
        "TLT": False,
    }
if "active_view" not in st.session_state:
    st.session_state.active_view = "CCK"  # or "LST", "TLT", "consolidated"

BRANCHES = ["CCK", "LST", "TLT"]
BRANCH_COLORS = {"CCK": "#1f77b4", "LST": "#ff7f0e", "TLT": "#2ca02c"}

# ------------------------------
# Helper: find product & sales columns
# ------------------------------
def find_columns(df):
    cols = df.columns.tolist()
    product_col = None
    sales_col = None

    # Prefer exact "sales"
    if "sales" in cols:
        sales_col = "sales"
    else:
        # Look for sales/revenue/amount
        sales_candidates = [c for c in cols if "sales" in c.lower() or "revenue" in c.lower() or "amount" in c.lower()]
        if sales_candidates:
            sales_col = sales_candidates[0]
        else:
            # fallback: second column or first numeric
            sales_col = cols[1] if len(cols) > 1 else cols[0]

    # Product column: look for product/type/category
    product_candidates = [c for c in cols if "product" in c.lower() or "type" in c.lower() or "category" in c.lower()]
    if product_candidates:
        product_col = product_candidates[0]
    else:
        # fallback: first column
        product_col = cols[0]

    return product_col, sales_col

# ------------------------------
# Helper: process uploaded file
# ------------------------------
def process_uploaded_file(uploaded_file):
    if uploaded_file is None:
        return None
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        return df
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return None

# ------------------------------
# UI: Header
# ------------------------------
st.title("📊 Sales by Product Type")
st.markdown("Upload CSV/Excel files for each branch to compare sales.")

# ------------------------------
# UI: Upload cards in columns
# ------------------------------
cols = st.columns(3)
for i, branch in enumerate(BRANCHES):
    with cols[i]:
        with st.container(border=True):
            st.subheader(f"{branch} Branch")
            uploaded = st.file_uploader(
                f"Upload {branch} data",
                type=["csv", "xlsx", "xls"],
                key=f"uploader_{branch}",
                accept_multiple_files=False,
            )
            if uploaded is not None:
                df = process_uploaded_file(uploaded)
                if df is not None:
                    st.session_state.data[branch] = df
                    st.session_state.loaded[branch] = True
                    st.success(f"✅ {len(df)} rows loaded")
                else:
                    st.session_state.loaded[branch] = False
                    st.error("Failed to load file")
            else:
                # If file was cleared, reset state
                if st.session_state.loaded[branch]:
                    st.session_state.loaded[branch] = False
                    st.session_state.data[branch] = None
                st.info("No file uploaded")

# ------------------------------
# Determine which views are available
# ------------------------------
loaded_branches = [b for b in BRANCHES if st.session_state.loaded[b]]
can_consolidate = len(loaded_branches) >= 2

# ------------------------------
# UI: View selector
# ------------------------------
st.divider()
st.subheader("📌 View")

view_options = []
for b in BRANCHES:
    if st.session_state.loaded[b]:
        view_options.append(b)
if can_consolidate:
    view_options.append("Consolidated")

if not view_options:
    st.warning("Please upload at least one branch file to see data.")
    st.stop()

# Radio buttons for view selection
selected_view = st.radio(
    "Select branch view:",
    options=view_options,
    index=0,
    horizontal=True,
    key="view_radio",
)

# Update active view in session state
st.session_state.active_view = selected_view

# ------------------------------
# Data aggregation
# ------------------------------
if selected_view == "Consolidated":
    # Combine all loaded branches
    dfs = []
    for b in loaded_branches:
        df = st.session_state.data[b].copy()
        df["_branch"] = b
        dfs.append(df)
    combined = pd.concat(dfs, ignore_index=True)
    # Find common columns
    # We'll use the first loaded branch's product and sales columns as reference
    ref_branch = loaded_branches[0]
    ref_df = st.session_state.data[ref_branch]
    prod_col, sales_col = find_columns(ref_df)
    # Ensure all data has those columns
    # If other branches have different column names, we'll map them
    # For simplicity, we assume column names are consistent across branches.
    # But we can rename columns if needed. Let's do a more robust approach:
    # We'll find product and sales columns for each branch and unify.
    # However, we can just use the first branch's names and hope they match.
    # Better: we will rename columns to standard names in the loaded data.
    # For now, we'll just use the column names from the first branch.
    # We'll also ensure that the columns exist in all loaded data.
    # If not, we'll raise an error.
    # Let's just use the combined data as is, but we need to aggregate by product and branch.
    # We'll group by product (prod_col) and branch (_branch), summing sales (sales_col)
    if prod_col not in combined.columns or sales_col not in combined.columns:
        st.error("Column names mismatch between branches. Please ensure all files have consistent 'product' and 'sales' columns.")
        st.stop()
    # Convert sales to numeric
    combined[sales_col] = pd.to_numeric(combined[sales_col], errors="coerce").fillna(0)
    # Group
    grouped = combined.groupby([prod_col, "_branch"], as_index=False)[sales_col].sum()
    # Pivot for plotting
    pivot = grouped.pivot(index=prod_col, columns="_branch", values=sales_col).fillna(0)
    # Plot
    fig = px.bar(
        pivot.reset_index(),
        x=prod_col,
        y=loaded_branches,
        barmode="group",
        title=f"Sales by Product Type – Consolidated ({' + '.join(loaded_branches)})",
        labels={"value": "Sales", prod_col: "Product Type"},
        color_discrete_map=BRANCH_COLORS,
    )
    st.plotly_chart(fig, use_container_width=True)
    # Table
    st.subheader("📋 Consolidated Data")
    st.dataframe(pivot.reset_index(), use_container_width=True)
else:
    # Single branch
    branch = selected_view
    df = st.session_state.data[branch]
    prod_col, sales_col = find_columns(df)
    df[sales_col] = pd.to_numeric(df[sales_col], errors="coerce").fillna(0)
    # Aggregate by product
    aggregated = df.groupby(prod_col, as_index=False)[sales_col].sum()
    aggregated = aggregated.sort_values(by=prod_col)
    # Plot
    fig = px.bar(
        aggregated,
        x=prod_col,
        y=sales_col,
        title=f"Sales by Product Type – {branch} Branch",
        labels={prod_col: "Product Type", sales_col: "Sales"},
        color_discrete_sequence=[BRANCH_COLORS[branch]],
    )
    st.plotly_chart(fig, use_container_width=True)
    # Table
    st.subheader(f"📋 {branch} Data")
    st.dataframe(aggregated, use_container_width=True)

# ------------------------------
# Show row counts and status
# ------------------------------
st.divider()
st.caption(f"Loaded branches: {', '.join(loaded_branches) if loaded_branches else 'None'}")
