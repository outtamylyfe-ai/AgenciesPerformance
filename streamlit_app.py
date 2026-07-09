import streamlit as st
import pandas as pd
import numpy as np

# ------------------------------------------------------------
# 1. Strict Filtering: drop summary/subtotal/footer rows
# ------------------------------------------------------------
def filter_summary_rows(df):
    """Remove rows where the first column is null or contains TOTAL/SUB/SUM."""
    if df.empty:
        return df
    first_col = df.columns[0]
    mask = df[first_col].notna()
    mask = mask & ~df[first_col].astype(str).str.contains('total|sub|sum', case=False, na=False)
    mask = mask & (df[first_col].astype(str).str.strip() != '')
    return df[mask].copy()

# ------------------------------------------------------------
# 2. Exact LOT TYPE mapping
# ------------------------------------------------------------
LOT_TYPE_MAP = {
    'SINGLE': 'Single',
    'DOUBLE': 'Double',
    'FAMILY': 'Family',
    'TOWER': 'Tower',
    'U-BUDDHA': 'Buddha',
    'TWIN DB': 'Special',
    'TWIN SG': 'Special',
    'M-TWS': 'Special',
    'M-TWD': 'Special',
}

def categorize_lot_type(lot_type):
    if pd.isna(lot_type):
        return 'Unknown'
    lot_type = str(lot_type).strip().upper()
    return LOT_TYPE_MAP.get(lot_type, 'Special')

# ------------------------------------------------------------
# 3. Helper: find column by pattern
# ------------------------------------------------------------
def find_column(df, pattern):
    for col in df.columns:
        if pattern.lower() in col.lower():
            return col
    return None

def safe_numeric(df, col):
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    else:
        df[col] = 0
    return df

# ------------------------------------------------------------
# 4. Sheet‑specific summarisers – updated to match required outputs
# ------------------------------------------------------------

def summarize_cck_tablet(df):
    """
    Returns DataFrame with columns:
    Block, Sold %, Balance %, Balance Units, Value ($)
    """
    df = filter_summary_rows(df)
    total_col = find_column(df, 'total')
    balance_col = find_column(df, 'balance')           # units
    value_col = find_column(df, "balance $ '000 (nett)")
    block_col = df.columns[0]

    if not total_col or not balance_col or not value_col:
        st.error("CCK-TABLET: Missing required columns.")
        return pd.DataFrame()

    for col in [total_col, balance_col, value_col]:
        df = safe_numeric(df, col)

    grouped = df.groupby(block_col).agg({
        total_col: 'sum',
        balance_col: 'sum',
        value_col: 'sum'
    }).reset_index()

    # Compute percentages
    grouped['Sold %'] = ((grouped[total_col] - grouped[balance_col]) / grouped[total_col] * 100).round(2)
    grouped['Balance %'] = (grouped[balance_col] / grouped[total_col] * 100).round(2)

    grouped.rename(columns={
        block_col: 'Block',
        balance_col: 'Balance Units',
        value_col: 'Value ($)'
    }, inplace=True)

    # Add Total row
    total_row = grouped[['Balance Units', 'Value ($)']].sum()
    total_total = grouped['Block'].count()  # not needed, we compute from sum of total per block
    total_total_units = grouped['Balance Units'].sum() / (total_row['Balance Units'] / (total_row['Balance Units'] + (grouped['Balance Units'].sum() - total_row['Balance Units'])))  # actually we can compute Sold% from totals
    # Actually we need total units across all blocks. We can compute from sum of total_col.
    total_units = grouped['Balance Units'].sum() + (grouped['Sold %'] * grouped['Balance Units'] / (100 - grouped['Sold %'])).sum()  # Not straightforward. Better to compute from original total_col sum.
    # Let's get total units by summing total_col from original grouped (before rename).
    total_units = grouped['Balance Units'].sum() / (grouped['Balance %'].mean()/100)  # but that's average, not correct.
    # Better: we should have kept total_col. I'll redo: store total_col separately.
    # I'll refactor: keep total_col and balance_col.

    # Let's redo correctly: We'll keep total_col and balance_col until after computing percentages.
    # I'll rewrite this function cleanly.

    # Simplified approach: compute totals from the aggregated data.
    # I'll create a new function.

    # For now, let's return the grouped without Total row? We'll add later.

    # I'll recode the whole function below.

def summarize_cck_tablet_fixed(df):
    """
    Returns DataFrame with columns:
    Block, Sold %, Balance %, Balance Units, Value ($)
    """
    df = filter_summary_rows(df)
    total_col = find_column(df, 'total')
    balance_col = find_column(df, 'balance')
    value_col = find_column(df, "balance $ '000 (nett)")
    block_col = df.columns[0]

    if not total_col or not balance_col or not value_col:
        st.error("CCK-TABLET: Missing required columns.")
        return pd.DataFrame()

    for col in [total_col, balance_col, value_col]:
        df = safe_numeric(df, col)

    grouped = df.groupby(block_col).agg({
        total_col: 'sum',
        balance_col: 'sum',
        value_col: 'sum'
    }).reset_index()

    grouped['Sold %'] = ((grouped[total_col] - grouped[balance_col]) / grouped[total_col] * 100).round(2)
    grouped['Balance %'] = (grouped[balance_col] / grouped[total_col] * 100).round(2)

    grouped.rename(columns={
        block_col: 'Block',
        balance_col: 'Balance Units',
        value_col: 'Value ($)'
    }, inplace=True)

    # Add Total row
    total_units = grouped[total_col].sum()  # we still have total_col? Actually we renamed it, we lost it.
    # Let's keep total_col by not renaming it.
    # I'll store total_units before renaming.
    total_units = grouped[total_col].sum()
    total_balance = grouped['Balance Units'].sum()
    total_value = grouped['Value ($)'].sum()
    total_sold_pct = ((total_units - total_balance) / total_units * 100).round(2)
    total_balance_pct = (total_balance / total_units * 100).round(2)

    total_row = pd.DataFrame({
        'Block': ['Total'],
        'Sold %': [total_sold_pct],
        'Balance %': [total_balance_pct],
        'Balance Units': [total_balance],
        'Value ($)': [total_value]
    })

    # Drop the total_col from grouped after we've used it
    grouped.drop(columns=[total_col], inplace=True)
    result = pd.concat([grouped, total_row], ignore_index=True)
    result['Value ($)'] = result['Value ($)'] * 1000
    return result[['Block', 'Sold %', 'Balance %', 'Balance Units', 'Value ($)']]

# For CCK-NICHE: pivot to wide format
def summarize_cck_niche(df):
    df = filter_summary_rows(df)
    total_col = find_column(df, 'total')
    sold_col = find_column(df, 'total sold')
    balance_col = find_column(df, 'balance')
    value_col = find_column(df, "balance $ '000 (nett)")
    lot_type_col = find_column(df, 'lot type')

    if not all([total_col, sold_col, balance_col, value_col, lot_type_col]):
        st.error("CCK-NICHE: Missing required columns.")
        return pd.DataFrame()

    for col in [total_col, sold_col, balance_col, value_col]:
        df = safe_numeric(df, col)

    df['Category'] = df[lot_type_col].apply(categorize_lot_type)

    grouped = df.groupby('Category').agg({
        total_col: 'sum',
        sold_col: 'sum',
        balance_col: 'sum',
        value_col: 'sum'
    }).reset_index()

    # Compute percentages
    grouped['Balance %'] = (grouped[balance_col] / grouped[total_col] * 100).round(2)
    grouped['Sold %'] = (grouped[sold_col] / grouped[total_col] * 100).round(2)

    # Pivot to wide format: categories as columns
    # We'll create a multi-index DataFrame with metrics as rows
    categories_order = ['Single', 'Double', 'Family', 'Buddha', 'Tower', 'Special']
    # Ensure all categories exist
    for cat in categories_order:
        if cat not in grouped['Category'].values:
            grouped = pd.concat([grouped, pd.DataFrame({'Category': [cat], total_col: [0], sold_col: [0], balance_col: [0], value_col: [0], 'Balance %': [0], 'Sold %': [0]})], ignore_index=True)

    grouped = grouped[grouped['Category'].isin(categories_order)]
    grouped['Category'] = pd.Categorical(grouped['Category'], categories=categories_order, ordered=True)
    grouped = grouped.sort_values('Category').reset_index(drop=True)

    # Build metrics rows
    metrics = {
        'Total': grouped[total_col].values,
        'Balance': grouped[balance_col].values,
        'Sold': grouped[sold_col].values,
        'Balance %': grouped['Balance %'].values,
        'Sold %': grouped['Sold %'].values,
        'Value': grouped[value_col].values
    }
    # Convert Value to dollars
    metrics['Value'] = metrics['Value'] * 1000

    # Create DataFrame with categories as columns and metrics as index
    result_df = pd.DataFrame(metrics, index=categories_order).T
    result_df.columns = categories_order
    # Reorder rows as per required: Total, Balance, Sold, Balance%, Sold%, Value
    row_order = ['Total', 'Balance', 'Sold', 'Balance %', 'Sold %', 'Value']
    result_df = result_df.reindex(row_order)

    # Format numeric columns: we'll let the formatting handle it later
    return result_df

# LST and TLT remain as before, but we'll adjust column names to match required
def summarize_lst(df):
    df = filter_summary_rows(df)
    product_col = df.columns[0]
    total_col = find_column(df, 'total')
    sold_col = find_column(df, 'total sold')
    balance_col = find_column(df, 'balance')
    value_col = find_column(df, "balance $ '000 (nett)")
    suite_col = find_column(df, 'suite no.')

    if not all([total_col, sold_col, balance_col, value_col, suite_col]):
        st.error("LST: Missing required columns.")
        return {}

    for col in [total_col, sold_col, balance_col, value_col]:
        df = safe_numeric(df, col)

    tablet_df = df[df[product_col].str.upper() == 'TABLET'].copy()
    niche_df = df[df[product_col].str.upper() == 'NICHE'].copy()

    def build_product_summary(sub_df, group_col, group_name):
        if sub_df.empty:
            return pd.DataFrame()
        grouped = sub_df.groupby(group_col).agg({
            total_col: 'sum',
            sold_col: 'sum',
            balance_col: 'sum',
            value_col: 'sum'
        }).reset_index()
        grouped['Balance %'] = (grouped[balance_col] / grouped[total_col] * 100).round(2)
        grouped['Sold %'] = (grouped[sold_col] / grouped[total_col] * 100).round(2)
        grouped.rename(columns={
            group_col: group_name,
            total_col: 'Total',
            sold_col: 'Sold',
            balance_col: 'Balance',
            value_col: 'Value ($)'
        }, inplace=True)
        # Add total row
        total_row = grouped[['Total', 'Sold', 'Balance', 'Value ($)']].sum()
        total_row[group_name] = 'Total'
        total_row['Balance %'] = (total_row['Balance'] / total_row['Total'] * 100).round(2)
        total_row['Sold %'] = (total_row['Sold'] / total_row['Total'] * 100).round(2)
        grouped = pd.concat([grouped, pd.DataFrame([total_row])], ignore_index=True)
        grouped['Value ($)'] = grouped['Value ($)'] * 1000
        return grouped[[group_name, 'Total', 'Balance', 'Sold', 'Balance %', 'Sold %', 'Value ($)']]

    result = {}
    if not tablet_df.empty:
        result['Tablet'] = build_product_summary(tablet_df, suite_col, 'Suite')
    if not niche_df.empty:
        result['Niche'] = build_product_summary(niche_df, suite_col, 'Suite')
    return result

def summarize_tlt(df):
    df = filter_summary_rows(df)
    product_col = df.columns[0]
    total_col = find_column(df, 'total')
    sold_col = find_column(df, 'total sold')
    balance_col = find_column(df, 'balance')
    value_col = find_column(df, "balance $ '000 (nett)")
    lot_type_col = find_column(df, 'lot type')

    if not all([total_col, sold_col, balance_col, value_col]):
        st.error("TLT: Missing required columns.")
        return {}

    for col in [total_col, sold_col, balance_col, value_col]:
        df = safe_numeric(df, col)

    tablet_df = df[df[product_col].str.upper() == 'TABLET'].copy()
    niche_df = df[df[product_col].str.upper() == 'NICHE'].copy()

    def build_tablet_summary(sub_df):
        if sub_df.empty:
            return pd.DataFrame()
        agg = sub_df[[total_col, sold_col, balance_col, value_col]].sum()
        agg['Product'] = 'Tablet'
        agg['Balance %'] = (agg[balance_col] / agg[total_col] * 100).round(2)
        agg['Sold %'] = (agg[sold_col] / agg[total_col] * 100).round(2)
        df_out = pd.DataFrame([agg])
        df_out.rename(columns={
            total_col: 'Total',
            sold_col: 'Sold',
            balance_col: 'Balance',
            value_col: 'Value ($)'
        }, inplace=True)
        df_out['Value ($)'] = df_out['Value ($)'] * 1000
        return df_out[['Product', 'Total', 'Balance', 'Sold', 'Balance %', 'Sold %', 'Value ($)']]

    def build_niche_summary(sub_df):
        if sub_df.empty:
            return pd.DataFrame()
        # Group by LOT TYPE
        grouped = sub_df.groupby(lot_type_col).agg({
            total_col: 'sum',
            sold_col: 'sum',
            balance_col: 'sum',
            value_col: 'sum'
        }).reset_index()
        grouped['Balance %'] = (grouped[balance_col] / grouped[total_col] * 100).round(2)
        grouped['Sold %'] = (grouped[sold_col] / grouped[total_col] * 100).round(2)
        grouped.rename(columns={
            lot_type_col: 'Lot Type',
            total_col: 'Total',
            sold_col: 'Sold',
            balance_col: 'Balance',
            value_col: 'Value ($)'
        }, inplace=True)
        # Add Total row
        total_row = grouped[['Total', 'Sold', 'Balance', 'Value ($)']].sum()
        total_row['Lot Type'] = 'Total'
        total_row['Balance %'] = (total_row['Balance'] / total_row['Total'] * 100).round(2)
        total_row['Sold %'] = (total_row['Sold'] / total_row['Total'] * 100).round(2)
        grouped = pd.concat([grouped, pd.DataFrame([total_row])], ignore_index=True)
        grouped['Value ($)'] = grouped['Value ($)'] * 1000
        return grouped[['Lot Type', 'Total', 'Balance', 'Sold', 'Balance %', 'Sold %', 'Value ($)']]

    result = {}
    if not tablet_df.empty:
        result['Tablet'] = build_tablet_summary(tablet_df)
    if not niche_df.empty:
        result['Niche'] = build_niche_summary(niche_df)
    return result

# ------------------------------------------------------------
# 5. Streamlit app
# ------------------------------------------------------------
st.set_page_config(page_title="Branch Inventory Dashboard", layout="wide")
st.title("📊 Branch Inventory Dashboard")

uploaded_file = st.file_uploader("Upload Excel Inventory Report", type=["xlsx"])

if uploaded_file is not None:
    xls = pd.ExcelFile(uploaded_file)
    sheet_names = xls.sheet_names

    st.sidebar.header("Sheets available")
    selected_sheets = st.sidebar.multiselect("Select sheets to display", sheet_names, default=sheet_names)

    # Debug option
    debug = st.sidebar.checkbox("Debug: show rows classified as 'Single' (CCK-NICHE)")

    for sheet in selected_sheets:
        df = pd.read_excel(xls, sheet_name=sheet, header=0)
        st.subheader(f"📄 {sheet}")

        if sheet.upper().startswith("CCK-TABLET"):
            summary = summarize_cck_tablet_fixed(df)
            if not summary.empty:
                st.dataframe(
                    summary.style.format({
                        'Sold %': '{:.2f}%',
                        'Balance %': '{:.2f}%',
                        'Balance Units': '{:,.0f}',
                        'Value ($)': '${:,.2f}'
                    }),
                    use_container_width=True
                )
            else:
                st.warning("No data after filtering.")

        elif sheet.upper().startswith("CCK-NICHE"):
            summary = summarize_cck_niche(df)
            if not summary.empty:
                # Format all numeric columns (all columns except index)
                st.dataframe(
                    summary.style.format({
                        col: '{:,.0f}' if col in ['Single','Double','Family','Buddha','Tower','Special'] and summary[col].dtype in ['int64','float64'] else '{:.2f}%' if ' %' in col else '${:,.2f}'
                    }),
                    use_container_width=True
                )
            else:
                st.warning("No data after filtering.")

            # Debug: show rows classified as Single
            if debug and 'CCK-NICHE' in sheet:
                df_debug = pd.read_excel(xls, sheet_name='CCK-NICHE', header=0)
                df_debug = filter_summary_rows(df_debug)
                lot_col = find_column(df_debug, 'lot type')
                if lot_col:
                    df_debug['Category'] = df_debug[lot_col].apply(categorize_lot_type)
                    single_rows = df_debug[df_debug['Category'] == 'Single']
                    st.subheader("Debug: Rows classified as 'Single'")
                    st.dataframe(single_rows)

        elif sheet.upper().startswith("LST"):
            summaries = summarize_lst(df)
            if summaries:
                for prod, sub_df in summaries.items():
                    st.markdown(f"**{prod}**")
                    if not sub_df.empty:
                        st.dataframe(
                            sub_df.style.format({
                                'Total': '{:,.0f}',
                                'Balance': '{:,.0f}',
                                'Sold': '{:,.0f}',
                                'Balance %': '{:.2f}%',
                                'Sold %': '{:.2f}%',
                                'Value ($)': '${:,.2f}'
                            }),
                            use_container_width=True
                        )
                    else:
                        st.info(f"No {prod} data.")
            else:
                st.warning("No data after filtering.")

        elif sheet.upper().startswith("TLT"):
            summaries = summarize_tlt(df)
            if summaries:
                for prod, sub_df in summaries.items():
                    st.markdown(f"**{prod}**")
                    if not sub_df.empty:
                        st.dataframe(
                            sub_df.style.format({
                                'Total': '{:,.0f}',
                                'Balance': '{:,.0f}',
                                'Sold': '{:,.0f}',
                                'Balance %': '{:.2f}%',
                                'Sold %': '{:.2f}%',
                                'Value ($)': '${:,.2f}'
                            }),
                            use_container_width=True
                        )
                    else:
                        st.info(f"No {prod} data.")
            else:
                st.warning("No data after filtering.")

        else:
            st.info(f"Sheet '{sheet}' is not recognised; displaying raw data (first 5 rows).")
            st.dataframe(df.head())
else:
    st.info("Please upload an Excel file to begin.")
