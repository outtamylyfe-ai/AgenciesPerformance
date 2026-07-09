import streamlit as st
import pandas as pd
import numpy as np

# Page Configuration
st.set_page_config(page_title="Branch Sales & Inventory Dashboard", page_icon="📊", layout="wide")

st.title("📊 Branch Sales & Inventory Analytics")
st.markdown("---")

# ==========================================
# 🛠️ DATA PROCESSING PIPELINE
# ==========================================
@st.cache_data(ttl=3600)
def process_uploaded_excel(uploaded_file):
    xls = pd.ExcelFile(uploaded_file)
    processed_data = {}
    
    def format_summary_matrix(matrix_df):
        total_row = pd.DataFrame([{
            'Category': 'Total',
            'Total Units': matrix_df['Total Units'].sum(),
            'Sold Units': matrix_df['Sold Units'].sum(),
            'Balance Units': matrix_df['Balance Units'].sum(),
            'Value of Balance': matrix_df['Value of Balance'].sum()
        }]).set_index('Category')
        
        out_df = pd.concat([matrix_df, total_row])
        out_df['Sold (%)'] = (out_df['Sold Units'] / out_df['Total Units']).map('{:.2%}'.format)
        out_df['Balance (%)'] = (out_df['Balance Units'] / out_df['Total Units']).map('{:.2%}'.format)
        
        for col in ['Total Units', 'Sold Units', 'Balance Units', 'Value of Balance']:
            out_df[col] = out_df[col].astype(object)
            
        for idx in out_df.index:
            out_df.at[idx, 'Total Units'] = f"{int(float(out_df.at[idx, 'Total Units'])):,}"
            out_df.at[idx, 'Sold Units'] = f"{int(float(out_df.at[idx, 'Sold Units'])):,}"
            out_df.at[idx, 'Balance Units'] = f"{int(float(out_df.at[idx, 'Balance Units'])):,}"
            out_df.at[idx, 'Value of Balance'] = f"$ {float(out_df.at[idx, 'Value of Balance']):,.2f}"
            
        return out_df[['Total Units', 'Sold Units', 'Sold (%)', 'Balance Units', 'Balance (%)', 'Value of Balance']]

    # ==========================================
    # 1. CCK BRANCH PARSING (with Enhanced Filtering)
    # ==========================================
    if 'CCK-NICHE' in xls.sheet_names:
        df_cck_niche = pd.read_excel(xls, sheet_name='CCK-NICHE', header=1)
        df_cck_niche.columns = df_cck_niche.columns.astype(str).str.strip()
        
        # --- GLOBAL EXCLUSION FILTER ---
        # Excludes any row where BLOCK, LOT TYPE, or PRODUCT contains "TOTAL"
        mask = (
            (~df_cck_niche['BLOCK'].astype(str).str.contains('TOTAL', case=False, na=False)) &
            (~df_cck_niche['LOT TYPE'].astype(str).str.contains('TOTAL', case=False, na=False))
        )
        df_niche_clean = df_cck_niche[mask & df_cck_niche['LOT TYPE'].notna()].copy()
        
        df_niche_clean['TOTAL_num'] = pd.to_numeric(df_niche_clean['TOTAL'], errors='coerce').fillna(0)
        df_niche_clean['SOLD_num'] = pd.to_numeric(df_niche_clean['TOTAL SOLD'], errors='coerce').fillna(0)
        df_niche_clean['BALANCE_num'] = pd.to_numeric(df_niche_clean['BALANCE'], errors='coerce').fillna(0)
        df_niche_clean['AVG_PO_num'] = pd.to_numeric(df_niche_clean['AVG PO PRICE'], errors='coerce').fillna(0)
        df_niche_clean['Value'] = df_niche_clean['BALANCE_num'] * df_niche_clean['AVG_PO_num']
        
        def classify_niche_type(val):
            val = str(val).strip().upper()
            mapping = {'SINGLE': 'Niche - Single', 'SG': 'Niche - Single', 'DOUBLE': 'Niche - Double', 'DB': 'Niche - Double', 'BUDDHA': 'Niche - Buddha'}
            return mapping.get(val, 'Niche - Others')
            
        df_niche_clean['Custom_Cat'] = df_niche_clean['LOT TYPE'].apply(classify_niche_type)
        niche_aggs = df_niche_clean.groupby('Custom_Cat').agg(
            Total_Units=('TOTAL_num', 'sum'), Sold_Units=('SOLD_num', 'sum'),
            Balance_Units=('BALANCE_num', 'sum'), Value_of_Balance=('Value', 'sum')
        ).rename(columns={'Total_Units': 'Total Units', 'Sold_Units': 'Sold Units', 'Balance_Units': 'Balance Units', 'Value_of_Balance': 'Value of Balance'})
        
        processed_data['CCK_Niche'] = format_summary_matrix(niche_aggs.reindex(['Niche - Single', 'Niche - Double', 'Niche - Buddha', 'Niche - Others']).fillna(0))

    # ==========================================
    # 2. LST & TLT BRANCHES PARSING
    # ==========================================
    for sheet_name, save_key in [('LST-TABLE & NICHE', 'LST'), ('TLT-TABLE & NICHE', 'TLT')]:
        if sheet_name in xls.sheet_names:
            df_raw = pd.read_excel(xls, sheet_name=sheet_name, header=None)
            cols = df_raw.iloc[1].fillna('').astype(str).str.strip().tolist()
            df_raw.columns = cols
            df_branch = df_raw.iloc[2:].copy()
            
            # --- GLOBAL EXCLUSION FILTER ---
            # Remove any rows that contain "TOTAL" in the PRODUCT column
            prod_col = next((c for c in cols if 'PRODUCT' in c.upper()), cols[0])
            df_branch = df_branch[~df_branch[prod_col].astype(str).str.contains('TOTAL', case=False, na=False)]
            
            # Cleaning logic
            df_branch['PRODUCT_filled'] = df_branch[prod_col].ffill().fillna('').apply(str).str.strip().str.upper()
            df_branch['TOTAL_num'] = pd.to_numeric(df_branch['TOTAL'], errors='coerce').fillna(0)
            df_branch['SOLD_num'] = pd.to_numeric(df_branch['TOTAL SOLD'], errors='coerce').fillna(0)
            df_branch['BALANCE_num'] = pd.to_numeric(df_branch['BALANCE'], errors='coerce').fillna(0)
            df_branch['AVG_PO_num'] = pd.to_numeric(df_branch['AVG PO PRICE'], errors='coerce').fillna(0)
            df_branch['Value'] = df_branch['BALANCE_num'] * df_branch['AVG_PO_num']
            
            def classify_branch(row):
                prod = str(row['PRODUCT_filled']).upper()
                lot = str(row.get('LOT TYPE', '')).strip().upper()
                if 'NICHE' in prod:
                    if lot in ['SINGLE', 'SG']: return 'Niche - Single'
                    if lot in ['DOUBLE', 'DB']: return 'Niche - Double'
                return None
                
            df_branch['Custom_Cat'] = df_branch.apply(classify_branch, axis=1)
            branch_aggs = df_branch[df_branch['Custom_Cat'].notna()].groupby('Custom_Cat').agg(
                Total_Units=('TOTAL_num', 'sum'), Sold_Units=('SOLD_num', 'sum'),
                Balance_Units=('BALANCE_num', 'sum'), Value_of_Balance=('Value', 'sum')
            ).rename(columns={'Total_Units': 'Total Units', 'Sold_Units': 'Sold Units', 'Balance_Units': 'Balance Units', 'Value_of_Balance': 'Value of Balance'})
            
            processed_data[save_key] = format_summary_matrix(branch_aggs)
            
    return processed_data

# --- UI ---
uploaded_file = st.sidebar.file_uploader("Upload Master Spreadsheet", type=["xlsx", "xls"])
if uploaded_file:
    data_package = process_uploaded_excel(uploaded_file)
    branch = st.sidebar.radio("Select Branch:", ["CCK Branch", "LST Branch", "TLT Branch"])
    if branch == "CCK Branch" and 'CCK_Niche' in data_package: st.dataframe(data_package['CCK_Niche'], use_container_width=True)
    elif branch in ["LST Branch", "TLT Branch"]:
        k = 'LST' if branch == "LST Branch" else 'TLT'
        if k in data_package: st.dataframe(data_package[k], use_container_width=True)
