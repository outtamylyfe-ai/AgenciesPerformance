import streamlit as st
import pandas as pd
import numpy as np
import re

# ------------------------------------------------------------
# 1. Strict Filtering: drop summary/subtotal/footer rows
# ------------------------------------------------------------
def filter_summary_rows(df):
    """Remove rows where the first column is null or contains TOTAL/SUB/SUM."""
    if df.empty:
        return df
    first_col = df.columns[0]
    # Drop rows where first column is missing
    mask = df[first_col].notna()
    # Drop rows where first column contains 'total', 'sub', 'sum' (case-insensitive)
    mask = mask & ~df[first_col].astype(str).str.contains('total|sub|sum', case=False, na=False)
    # Drop rows where first column is empty string
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
    # add any other types you encounter
}

def categorize_lot_type(lot_type):
    if pd.isna(lot_type):
        return 'Unknown'
    lot_type = str(lot_type).strip().upper()
    return LOT_TYPE_MAP.get(lot_type, 'Special')  # fallback

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
# 4. Sheet‑specific summarisers
# ------------------------------------------------------------

def summarize_cck_tablet(df):
    """Return DataFrame: Block, Total, Balance, Balance%, Value."""
    df = filter_summary_rows(df)
    # Find necessary columns
    total_col = find_column(df, 'total')
    sold_col = find_column(df, 'total sold')
    balance_col = find_column(df, 'balance')          # units
    value_col = find_column(df, "balance $ '000 (nett)")  # nett value in thousands
    block_col = df.columns[0]  # 'BLOCK'

    if not total_col or not balance_col or not value_col:
        st.error("CCK-TABLET: Missing required columns (TOTAL, BALANCE, BALANCE $ '000 (NETT)).")
        return pd.DataFrame()

    # Convert to numeric
    for col in [total_col, sold_col, balance_col, value_col]:
        if col:
            df = safe_numeric(df, col)

    # Group by BLOCK (first column)
    grouped = df.groupby(block_col).agg({
        total_col: 'sum',
        balance_col: 'sum',
        value_col: 'sum'
    }).reset_index()

    # Compute Balance%
    grouped['Balance %'] = (grouped[balance_col] / grouped[total_col] * 100).round(2)

    # Rename columns
    grouped.rename(columns={
        block_col: 'Block',
        total_col: 'Total',
        balance_col: 'Balance',
        value_col: 'Value ($)'
    }, inplace=True)

    # Add Total row
    total_row = grouped[['Total', 'Balance', 'Value ($)']].sum()
    total_row['Block'] = 'Total'
    total_row['Balance %'] = (total_row['Balance'] / total_row['Total'] * 100).round(2)
    grouped = pd.concat([grouped, pd.DataFrame([total_row])], ignore_index=True)

    # Value in dollars (thousands * 1000)
    grouped['Value ($)'] = grouped['Value ($)'] * 1000

    return grouped[['Block', 'Total', 'Balance', 'Balance %', 'Value ($)']]

def summarize_cck_niche(df):
    """Return DataFrame with categories: Single, Double, Family, Buddha, Tower, Special."""
    df = filter_summary_rows(df)
    # Find columns
    total_col = find_column(df, 'total')
    sold_col = find_column(df, 'total sold')
    balance_col = find_column(df, 'balance')
    value_col = find_column(df, "balance $ '000 (nett)")
    lot_type_col = find_column(df, 'lot type')

    if not total_col or not sold_col or not balance_col or not value_col or not lot_type_col:
        st.error("CCK-NICHE: Missing required columns.")
        return pd.DataFrame()

    # Convert numeric
    for col in [total_col, sold_col, balance_col, value_col]:
        df = safe_numeric(df, col)

    # Map LOT TYPE
    df['Category'] = df[lot_type_col].apply(categorize_lot_type)

    # Group by Category
    grouped = df.groupby('Category').agg({
        total_col: 'sum',
        sold_col: 'sum',
        balance_col: 'sum',
        value_col: 'sum'
    }).reset_index()

    # Compute percentages
    grouped['Balance %'] = (grouped[balance_col] / grouped[total_col] * 100).round(2)
    grouped['Sold %'] = (grouped[sold_col] / grouped[total_col] * 100).round(2)

    # Rename
    grouped.rename(columns={
        'Category': 'Lot Type',
        total_col: 'Total',
        sold_col: 'Sold',
        balance_col: 'Balance',
        value_col: 'Value ($)'
    }, inplace=True)

    # Reorder categories to match expected order
    category_order = ['Single', 'Double', 'Family', 'Buddha', 'Tower', 'Special']
    grouped['Lot Type'] = pd.Categorical(grouped['Lot Type'], categories=category_order, ordered=True)
    grouped = grouped.sort_values('Lot Type').reset_index(drop=True)

    # Add Total row
    total_row = grouped[['Total', 'Sold', 'Balance', 'Value ($)']].sum()
    total_row['Lot Type'] = 'Total'
    total_row['Balance %'] = (total_row['Balance'] / total_row['Total'] * 100).round(2)
    total_row['Sold %'] = (total_row['Sold'] / total_row['Total'] * 100).round(2)
    grouped = pd.concat([grouped, pd.DataFrame([total_row])], ignore_index=True)

    # Value in dollars
    grouped['Value ($)'] = grouped['Value ($)'] * 1000

    return grouped[['Lot Type', 'Total', 'Balance', 'Sold', 'Balance %', 'Sold %', 'Value ($)']]

def summarize_lst(df):
    """Return dict with 'Tablet' and 'Niche' DataFrames."""
    df = filter_summary_rows(df)
    product_col = df.columns[0]  # 'PRODUCT'

    # Find columns
    total_col = find_column(df, 'total')
    sold_col = find_column(df, 'total sold')
    balance_col = find_column(df, 'balance')
    value_col = find_column(df, "balance $ '000 (nett)")
    suite_col = find_column(df, 'suite no.')
    lot_type_col = find_column(df, 'lot type')

    if not all([total_col, sold_col, balance_col, value_col, suite_col]):
        st.error("LST: Missing required columns.")
        return {}

    # Convert numeric
    for col in [total_col, sold_col, balance_col, value_col]:
        df = safe_numeric(df, col)

    # Separate products
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
        # For Niche, group by SUITE NO. (e.g., Dynasty 1, etc.)
        result['Niche'] = build_product_summary(niche_df, suite_col, 'Suite')
    return result

def summarize_tlt(df):
    """Return dict with 'Tablet' and 'Niche' DataFrames."""
    df = filter_summary_rows(df)
    product_col = df.columns[0]  # 'PRODUCT'

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
        # Tablet is a single row (or aggregated)
        if sub_df.empty:
            return pd.DataFrame()
        # Sum everything (should be one row anyway)
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
        # Group by LOT TYPE (Single, Double)
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
    # Read all sheets
    xls = pd.ExcelFile(uploaded_file)
    sheet_names = xls.sheet_names

    st.sidebar.header("Sheets available")
    selected_sheets = st.sidebar.multiselect("Select sheets to display", sheet_names, default=sheet_names)

    # Process each selected sheet
    for sheet in selected_sheets:
        df = pd.read_excel(xls, sheet_name=sheet, header=0)
        st.subheader(f"📄 {sheet}")

        # Identify sheet type by name
        if sheet.upper().startswith("CCK-TABLET"):
            summary = summarize_cck_tablet(df)
            if not summary.empty:
                st.dataframe(
                    summary.style.format({
                        'Total': '{:,.0f}',
                        'Balance': '{:,.0f}',
                        'Balance %': '{:.2f}%',
                        'Value ($)': '${:,.2f}'
                    }),
                    use_container_width=True
                )
            else:
                st.warning("No data after filtering.")

        elif sheet.upper().startswith("CCK-NICHE"):
            summary = summarize_cck_niche(df)
            if not summary.empty:
                st.dataframe(
                    summary.style.format({
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
                st.warning("No data after filtering.")

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

    # Optional debug print (if user wants to see which rows contributed to a category)
    # Uncomment to add a debug button
    if st.sidebar.checkbox("Debug: show rows for 'Niche - Single' category (CCK-NICHE only)"):
        # This will only work if CCK-NICHE sheet is loaded and we capture its dataframe
        # For simplicity, we'll re-read the sheet and show rows
        if 'CCK-NICHE' in sheet_names:
            df_debug = pd.read_excel(xls, sheet_name='CCK-NICHE', header=0)
            df_debug = filter_summary_rows(df_debug)
            lot_col = find_column(df_debug, 'lot type')
            if lot_col:
                df_debug['Category'] = df_debug[lot_col].apply(categorize_lot_type)
                single_rows = df_debug[df_debug['Category'] == 'Single']
                st.subheader("Debug: Rows classified as 'Single'")
                st.dataframe(single_rows)
        else:
            st.info("CCK-NICHE sheet not loaded.")
else:
    st.info("Please upload an Excel file to begin.")
