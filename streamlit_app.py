import streamlit as st
import pandas as pd

# Page Configuration
st.set_page_config(page_title="Branch Sales & Inventory Dashboard", page_icon="📊", layout="wide")

st.title("📊 Branch Sales & Inventory Analytics")
st.markdown("---")

@st.cache_data(ttl=3600)
def process_uploaded_excel(uploaded_file):
    xls = pd.ExcelFile(uploaded_file)
    processed_data = {}
    
    # Helper to clean and format
    def format_summary_matrix(matrix_df):
        out_df = matrix_df.copy()
        out_df['Sold (%)'] = (out_df['Sold Units'] / out_df['Total Units']).map('{:.2%}'.format)
        out_df['Balance (%)'] = (out_df['Balance Units'] / out_df['Total Units']).map('{:.2%}'.format)
        
        # Formatting for readability
        for col in ['Total Units', 'Sold Units', 'Balance Units', 'Value of Balance']:
            out_df[col] = out_df[col].apply(lambda x: f"{int(x):,}" if 'Value' not in col else f"$ {x:,.2f}")
        return out_df

    # --- CCK BRANCH PROCESSING ---
    if 'CCK-NICHE' in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name='CCK-NICHE', header=1)
        df.columns = df.columns.astype(str).str.strip()
        
        # STRICT CLEANING: Only keep rows where BLOCK has a value (excludes footer/summary)
        df_clean = df.dropna(subset=['BLOCK']).copy()
        
        # Convert columns to numeric
        df_clean['TOTAL_num'] = pd.to_numeric(df_clean['TOTAL'], errors='coerce').fillna(0)
        df_clean['SOLD_num'] = pd.to_numeric(df_clean['TOTAL SOLD'], errors='coerce').fillna(0)
        df_clean['BAL_num'] = pd.to_numeric(df_clean['BALANCE'], errors='coerce').fillna(0)
        df_clean['AVG_PO_num'] = pd.to_numeric(df_clean['AVG PO PRICE'], errors='coerce').fillna(0)
        df_clean['Val_Bal'] = df_clean['BAL_num'] * df_clean['AVG_PO_num']
        
        # Mapping Lot Types
        def classify(val):
            v = str(val).strip().upper()
            if v in ['SINGLE', 'SG']: return 'Single'
            if v in ['DOUBLE', 'DB']: return 'Double'
            if 'BUDDHA' in v: return 'Buddha'
            return 'Others'
            
        df_clean['Cat'] = df_clean['LOT TYPE'].apply(classify)
        
        # Aggregate
        aggs = df_clean.groupby('Cat').agg(
            Total_Units=('TOTAL_num', 'sum'), Sold_Units=('SOLD_num', 'sum'),
            Balance_Units=('BAL_num', 'sum'), Value_of_Balance=('Val_Bal', 'sum')
        )
        processed_data['CCK_Niche'] = format_summary_matrix(aggs)

    # --- LST & TLT PROCESSING ---
    for sheet_name, key in [('LST-TABLE & NICHE', 'LST'), ('TLT-TABLE & NICHE', 'TLT')]:
        if sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name, header=1)
            df.columns = df.columns.astype(str).str.strip()
            
            # STRICT CLEANING: Drop rows with no Product/Block identifier
            df = df.dropna(subset=[df.columns[0]]).copy() 
            
            df['TOTAL_num'] = pd.to_numeric(df['TOTAL'], errors='coerce').fillna(0)
            df['SOLD_num'] = pd.to_numeric(df['TOTAL SOLD'], errors='coerce').fillna(0)
            df['BAL_num'] = pd.to_numeric(df['BALANCE'], errors='coerce').fillna(0)
            df['AVG_PO_num'] = pd.to_numeric(df['AVG PO PRICE'], errors='coerce').fillna(0)
            df['Val_Bal'] = df['BAL_num'] * df['AVG_PO_num']
            
            # Use similar classification
            df['Cat'] = df['LOT TYPE'].apply(classify) # Re-using same classify function
            aggs = df.groupby('Cat').agg(
                Total_Units=('TOTAL_num', 'sum'), Sold_Units=('SOLD_num', 'sum'),
                Balance_Units=('BAL_num', 'sum'), Value_of_Balance=('Val_Bal', 'sum')
            )
            processed_data[key] = format_summary_matrix(aggs)
            
    return processed_data

# UI Execution
uploaded_file = st.sidebar.file_uploader("Upload Master Spreadsheet", type=["xlsx", "xls"])
if uploaded_file:
    data = process_uploaded_excel(uploaded_file)
    branch = st.sidebar.radio("Branch:", ["CCK", "LST", "TLT"])
    key_map = {"CCK": "CCK_Niche", "LST": "LST", "TLT": "TLT"}
    if key_map[branch] in data:
        st.dataframe(data[key_map[branch]], use_container_width=True)
