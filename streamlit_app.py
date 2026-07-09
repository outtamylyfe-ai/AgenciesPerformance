import streamlit as st
import pandas as pd
import numpy as np
import re

# ------------------------------------------------------------
# 1. Enhanced filtering: drops any row that is a summary/subtotal
# ------------------------------------------------------------
def filter_summary_rows(df):
    """
    Remove rows where the first column is empty, or where the first column
    or the 'NAME' column (if present) contains 'TOTAL', 'SUB', or 'SUM'
    as whole words (case‑insensitive).
    """
    if df.empty:
        return df
    
    first_col = df.columns[0]
    mask = df[first_col].notna() & (df[first_col].astype(str).str.strip() != '')
    
    # Drop if first column contains total/sub/sum as whole words
    pattern = r'\b(total|sub|sum)\b'
    mask = mask & ~df[first_col].astype(str).str.contains(pattern, case=False, na=False, regex=True)
    
    # Also check the 'NAME' column (if it exists) for same pattern
    name_col = None
    for col in df.columns:
        if col.lower() == 'name':
            name_col = col
            break
    if name_col is not None:
        mask = mask & ~df[name_col].astype(str).str.contains(pattern, case=False, na=False, regex=True)
    
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
# 3. Helpers
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
# 4. Sheet summarisers – updated for robust filtering
# ------------------------------------------------------------

def summarize_cck_tablet(df):
    """Returns: Block, Sold %, Balance %, Balance Units, Value ($)"""
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

    # Compute percentages
    grouped['Sold %'] = ((grouped[total_col] - grouped[balance_col]) / grouped[total_col] * 100).round(2)
    grouped['Balance %'] = (grouped[balance_col] / grouped[total_col] * 100).round(2)

    # Save total row data before dropping total_col
    total_units = grouped[total_col].sum()
    total_balance = grouped[balance_col].sum()
    total_value = grouped[value_col].sum()
    total_sold_pct = ((total_units - total_balance) / total_units * 100).round(2)
    total_balance_pct = (total_balance / total_units * 100).round(2)

    grouped.rename(columns={
        block_col: 'Block',
        balance_col: 'Balance Units',
        value_col: 'Value ($)'
    }, inplace=True)
    grouped.drop(columns=[total_col], inplace=True)

    # Total row
    total_row = pd.DataFrame({
        'Block': ['Total'],
        'Sold %': [total_sold_pct],
        'Balance %': [total_balance_pct],
        'Balance Units': [total_balance],
        'Value ($)': [total_value]
    })

    result = pd.concat([grouped, total_row], ignore_index=True)
    result['Value ($)'] = result['Value ($)'] * 1000
    return result[['Block', 'Sold %', 'Balance %', 'Balance Units', 'Value ($)']]

def summarize_cck_niche(df):
    """Wide‑format matrix: categories as columns, metrics as rows."""
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

    # CRUCIAL: drop rows where LOT TYPE is missing or contains 'total'/'sub'/'sum'
    df = df[df[lot_type_col].notna()]
    df = df[~df[lot_type_col].astype(str).str.contains(r'\b(total|sub|sum)\b', case=False, na=False, regex=True)]
    df = df[df[lot_type_col].astype(str).str.strip() != '']

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

    # Ensure all categories exist
    categories_order = ['Single', 'Double', 'Family', 'Buddha', 'Tower', 'Special']
    for cat in categories_order:
        if cat not in grouped['Category'].values:
            grouped = pd.concat([grouped, pd.DataFrame({
                'Category': [cat],
                total_col: [0],
                sold_col: [0],
                balance_col: [0],
                value_col: [0],
                'Balance %': [0],
                'Sold %': [0]
            })], ignore_index=True)

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
    metrics['Value'] = metrics['Value'] * 1000

    result_df = pd.DataFrame(metrics, index=categories_order).T
    result_df.columns = categories_order
    row_order = ['Total', 'Balance', 'Sold', 'Balance %', 'Sold %', 'Value']
    result_df = result_df.reindex(row_order)

    return result_df

# ------------------------------------------------------------
# LST and TLT summarisers (unchanged, but they use filter_summary_rows)
# ------------------------------------------------------------
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

    # Debug option – shows all rows that are classified as 'Single'
    debug = st.sidebar.checkbox("Debug: show rows classified as 'Single' (CCK-NICHE)")

    for sheet in selected_sheets:
        df = pd.read_excel(xls, sheet_name=sheet, header=0)
        st.subheader(f"📄 {sheet}")

        if sheet.upper().startswith("CCK-TABLET"):
            summary = summarize_cck_tablet(df)
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
                # Formatting: numbers with commas, percentages, currency
                fmt = {}
                for col in summary.columns:
                    if summary[col].dtype in ['int64', 'float64']:
                        if ' %' in col:
                            fmt[col] = '{:.2f}%'
                        elif col == 'Value':
                            fmt[col] = '${:,.2f}'
                        else:
                            fmt[col] = '{:,.0f}'
                st.dataframe(summary.style.format(fmt), use_container_width=True)
            else:
                st.warning("No data after filtering.")

            # Debug: show rows that ended up in 'Single'
            if debug and 'CCK-NICHE' in sheet:
                df_debug = pd.read_excel(xls, sheet_name='CCK-NICHE', header=0)
                df_debug = filter_summary_rows(df_debug)
                lot_col = find_column(df_debug, 'lot type')
                if lot_col:
                    # Apply same filters as in summary
                    df_debug = df_debug[df_debug[lot_col].notna()]
                    df_debug = df_debug[~df_debug[lot_col].astype(str).str.contains(r'\b(total|sub|sum)\b', case=False, na=False, regex=True)]
                    df_debug = df_debug[df_debug[lot_col].astype(str).str.strip() != '']
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
