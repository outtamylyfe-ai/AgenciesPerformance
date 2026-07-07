import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.io as pio
from fpdf import FPDF
import tempfile
import os

# Configure dashboard workspace layout
st.set_page_config(page_title="Multi-Month Sales Report Dashboard", layout="wide")
st.title("📊 Multi-Month Closed Sales Report Dashboard")

# --- 1. DYNAMIC MULTI-FILE UPLOADER ENGINE ---
uploaded_files = st.file_uploader(
    "📂 Upload Closed Sales Report Excel Sheets (Select single or multiple months)", 
    type=["xlsx"], 
    accept_multiple_files=True
)

if uploaded_files:
    all_months_data = []
    
    # Process each uploaded file
    for uploaded_file in uploaded_files:
        # Read the sheet, starting headers at row index 4 (5th row)
        df_month = pd.read_excel(uploaded_file, sheet_name=0, header=4)
        df_month.columns = [str(c).strip() for c in df_month.columns]
        
        # Deduce Month name from file name (e.g., "Jan closed sales.xlsx" -> "Jan")
        file_name = uploaded_file.name
        detected_month = file_name.split()[0].title() if " " in file_name else file_name.split(".")[0].title()
        df_month['Report_Month'] = detected_month
        
        all_months_data.append(df_month)
        
    # Combine all uploaded data into a single master frame
    df_master = pd.concat(all_months_data, ignore_index=True)

    # 🎯 Dynamically find the correct column header for Sales
    target_value_col = None
    for col in df_master.columns:
        if 'net' in col.lower() and 'main' in col.lower():
            target_value_col = col
            break

    if not target_value_col:
        target_value_col = 'Net main product'

    # 2. 🎯 CRITICAL RE-INCLUSION: Only preserve rows with 'CONFIRM' status and exclude 'BOOK'
    df_confirm = df_master[df_master['STATUS'] == 'CONFIRM'].copy()

    # 3. Official Agency Mapping reflecting individual breakdown requirements
    def classify_agency_official(row):
        cbdd_name_col = 'CBDD_NAME' if 'CBDD_NAME' in row.index else ('CBDD' if 'CBDD' in row.index else '')
        cbdd_val = str(row[cbdd_name_col]).strip().upper() if cbdd_name_col and pd.notna(row[cbdd_name_col]) else ""
        bdd_name = str(row['BDD_NAME']).strip().upper() if pd.notna(row['BDD_NAME']) else ""
        
        if "C117" in cbdd_val or "FU GUI" in cbdd_val:
            return "Fu Gui Services"
        elif "C728" in cbdd_val or "APG ADVISORY" in cbdd_val:
            return "APG Advisory"
        elif "C918" in cbdd_val or "ZENBOX" in cbdd_val:
            return "Zenbox"
        elif "JF LIFE" in bdd_name:
            return "JF Life"
        elif "SINGAPORE LIFESTYLE" in bdd_name or "SLA" in bdd_name:
            return "Singapore Lifestyle Associates"
        elif "DIRECT" in cbdd_val:
            return "Direct BDD"
        else:
            return "Others"

    # 4. Product Consolidation Logic
    def map_product(prod):
        p = str(prod).strip().upper() if pd.notna(prod) else "UNKNOWN"
        if p in ['P', 'F']: return 'FSP'
        elif p == 'UN': return 'Urn'
        elif p in ['URN', 'LOT']: return 'Lot'
        elif p == 'B': return 'Buddha'
        elif p == 'TABLET': return 'Tablet'
        else: return p.title()

    df_confirm['Agency_Class'] = df_confirm.apply(classify_agency_official, axis=1)
    df_confirm['Product_Class'] = df_confirm['PRODUCT_CODE'].apply(map_product)

    # --- HELPER FUNCTIONS FOR CALCULATIONS ---
    def get_agency_matrix(data_frame):
        if data_frame.empty:
            return pd.DataFrame()
        pivot = data_frame.pivot_table(
            index=['Agency_Class', 'BRANCH'], 
            columns='Product_Class', 
            values=target_value_col, 
            aggfunc='sum', 
            fill_value=0
        )
        for c in ['FSP', 'Buddha', 'Tablet', 'Urn', 'Lot']:
            if c not in pivot.columns:
                pivot[c] = 0.0
        product_cols = ['FSP', 'Buddha', 'Tablet', 'Urn', 'Lot']
        other_cols = [c for c in pivot.columns if c not in product_cols]
        pivot = pivot[product_cols + other_cols]
        pivot['Total Sales'] = pivot.sum(axis=1)
        
        pivot_display = pivot.copy().reset_index()
        total_row = pivot.sum(numeric_only=True)
        new_total_line = {'Agency_Class': 'GRAND TOTAL', 'BRANCH': ''}
        for col in pivot.columns:
            new_total_line[col] = total_row[col]
            
        pivot_display = pd.concat([pivot_display, pd.DataFrame([new_total_line])], ignore_index=True)
        return pivot_display

    def get_product_summary(data_frame):
        if data_frame.empty:
            return pd.DataFrame()
        product_summary = data_frame.groupby('Product_Class')[target_value_col].sum().reset_index()
        product_summary.columns = ['Product Type', 'Total Sales']
        
        fsp_val = product_summary.loc[product_summary['Product Type'] == 'FSP', 'Total Sales'].sum()
        non_fsp_total_val = product_summary[product_summary['Product Type'] != 'FSP']['Total Sales'].sum()
        grand_total_val = fsp_val + non_fsp_total_val
        
        summary_rows = []
        for _, row in product_summary.sort_values(by='Total Sales', ascending=False).iterrows():
            summary_rows.append({'Product Type': row['Product Type'], 'Total Sales': row['Total Sales']})
            
        summary_rows.append({'Product Type': 'Non-FSP Total', 'Total Sales': non_fsp_total_val})
        summary_rows.append({'Product Type': 'Grand Total', 'Total Sales': grand_total_val})
        return pd.DataFrame(summary_rows).set_index('Product Type')

    # --- DYNAMIC MULTI-MONTH PDF GENERATION ENGINE ---
    def generate_consolidated_pdf(base_df, selected_months):
        pdf = FPDF()
        color_palette = px.colors.qualitative.Safe
        
        for current_month in selected_months:
            month_df = base_df[base_df['Report_Month'] == current_month]
            if month_df.empty:
                continue
                
            def add_matrix_page(title_text, branch_filter):
                pdf.add_page()
                pdf.set_font("Helvetica", "B", 14)
                pdf.cell(0, 10, f"{current_month.upper()} - {title_text}", ln=True, align="C")
                pdf.ln(3)
                
                sub_df = month_df.copy()
                if branch_filter != 'ALL':
                    sub_df = sub_df[sub_df['BRANCH'] == branch_filter]
                    
                matrix_df = get_agency_matrix(sub_df)
                if matrix_df.empty: return
                
                # Table Headers
                pdf.set_font("Helvetica", "B", 8)
                pdf.cell(40, 8, "Agency Class", border=1)
                pdf.cell(12, 8, "Branch", border=1)
                pdf.cell(23, 8, "FSP", border=1)
                pdf.cell(23, 8, "Buddha", border=1)
                pdf.cell(23, 8, "Tablet", border=1)
                pdf.cell(23, 8, "Urn", border=1)
                pdf.cell(23, 8, "Lot", border=1)
                pdf.cell(25, 8, "Total Sales", border=1, ln=True)
                
                # Table Body
                pdf.set_font("Helvetica", "", 8)
                for _, r in matrix_df.iterrows():
                    if r['Agency_Class'] == 'GRAND TOTAL':
                        pdf.set_font("Helvetica", "B", 8)
                    pdf.cell(40, 7, str(r['Agency_Class']), border=1)
                    pdf.cell(12, 7, str(r['BRANCH']), border=1)
                    pdf.cell(23, 7, f"${r['FSP']:,.2f}", border=1)
                    pdf.cell(23, 7, f"${r['Buddha']:,.2f}", border=1)
                    pdf.cell(23, 7, f"${r['Tablet']:,.2f}", border=1)
                    pdf.cell(23, 7, f"${r['Urn']:,.2f}", border=1)
                    pdf.cell(23, 7, f"${r['Lot']:,.2f}", border=1)
                    pdf.cell(25, 7, f"${r['Total Sales']:,.2f}", border=1, ln=True)
                
                # Generate Bar Chart image bytes
                chart_df = sub_df.groupby(['Agency_Class', 'Product_Class'])[target_value_col].sum().reset_index()
                fig = px.bar(
                    chart_df, x="Agency_Class", y=target_value_col, color="Product_Class", 
                    barmode="stack", template="plotly_white", color_discrete_sequence=color_palette
                )
                fig.update_layout(width=700, height=300, margin=dict(t=15, b=15, l=15, r=15))
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
                    pio.write_image(fig, tmpfile.name, format="png")
                    pdf.ln(5)
                    pdf.image(tmpfile.name, x=10, w=190)
                os.unlink(tmpfile.name)
                    
            def add_summary_page(title_text, branch_filter):
                pdf.add_page()
                pdf.set_font("Helvetica", "B", 14)
                pdf.cell(0, 10, f"{current_month.upper()} - {title_text}", ln=True, align="C")
                pdf.ln(5)
                
                sub_df = month_df.copy()
                if branch_filter != 'ALL':
                    sub_df = sub_df[sub_df['BRANCH'] == branch_filter]
                    
                summary_df = get_product_summary(sub_df).reset_index()
                if summary_df.empty: return
                
                # Table Headers
                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(90, 8, "Product Type", border=1)
                pdf.cell(60, 8, "Total Sales", border=1, ln=True)
                
                # Table Body
                pdf.set_font("Helvetica", "", 11)
                for _, r in summary_df.iterrows():
                    p_type = r['Product Type']
                    if p_type in ['Non-FSP Total', 'Grand Total']:
                        pdf.set_font("Helvetica", "B", 11)
                    pdf.cell(90, 8, str(p_type), border=1)
                    pdf.cell(60, 8, f"${r['Total Sales']:,.2f}", border=1, ln=True)

                # Generate Donut Chart image bytes
                product_summary_chart = sub_df.groupby('Product_Class')[target_value_col].sum().reset_index()
                product_summary_chart.columns = ['Product Type', 'Total Sales']
                fig = px.pie(
                    product_summary_chart, values='Total Sales', names='Product Type', 
                    hole=0.4, template="plotly_white", color_discrete_sequence=color_palette
                )
                fig.update_layout(width=500, height=300, margin=dict(t=15, b=15, l=15, r=15))
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
                    pio.write_image(fig, tmpfile.name, format="png")
                    pdf.ln(5)
                    pdf.image(tmpfile.name, x=45, w=120)
                os.unlink(tmpfile.name)
            
            # Append pages sequentially per month
            add_matrix_page("Agency Performance Matrix (CCK Branch)", "CCK")
            add_summary_page("Product Performance Summary (CCK Branch)", "CCK")
            add_matrix_page("Agency Performance Matrix (LST Branch)", "LST")
            add_summary_page("Product Performance Summary (LST Branch)", "LST")
            add_matrix_page("Agency Performance Matrix (Both Branches)", "ALL")
            add_summary_page("Product Performance Summary (Both Branches)", "ALL")
            
        return pdf.output()

    # --- GLOBAL WORKSPACE NAVIGATION CONTROL ---
    st.sidebar.header("Global Filters")
    
    available_months = sorted(list(df_confirm['Report_Month'].unique()))
    month_toggle = st.sidebar.multiselect("📅 Select Month(s) to View:", options=available_months, default=available_months)
    
    branch_toggle = st.sidebar.selectbox("📍 Select Branch View:", options=['ALL', 'CCK', 'LST'])

    available_agencies = ["Fu Gui Services", "APG Advisory", "Zenbox", "Singapore Lifestyle Associates", "JF Life", "Direct BDD", "Others"]
    agency_toggle = st.sidebar.multiselect("🏢 Select Agencies:", options=available_agencies, default=available_agencies)

    # Apply interactive cross filters based on selection maps
    filtered_df = df_confirm.copy()
    filtered_df = filtered_df[filtered_df['Report_Month'].isin(month_toggle)]
    if branch_toggle != 'ALL':
        filtered_df = filtered_df[filtered_df['BRANCH'] == branch_toggle]
    filtered_df = filtered_df[filtered_df['Agency_Class'].isin(agency_toggle)]

    # --- RENDER ANALYSIS VIEWS ---
    if not filtered_df.empty:
        if target_value_col in filtered_df.columns:
            total_sales = filtered_df[target_value_col].sum()
            
            # Overview Performance Rows
            top_col1, top_col2 = st.columns([3, 1])
            with top_col1:
                st.metric(label=f"Total Aggregated Sales ({branch_toggle} View)", value=f"${total_sales:,.2f}")
            with top_col2:
                st.write(" ")
                with st.spinner("Compiling Comprehensive PDF..."):
                    consolidated_pdf_bytes = generate_consolidated_pdf(df_confirm, month_toggle)
                st.download_button(
                    label="📥 Download Consolidated Multi-Month PDF",
                    data=bytes(consolidated_pdf_bytes),
                    file_name="Consolidated_Confirm_Sales_Report.pdf",
                    mime="application/pdf"
                )
                
            # Workspace Presentation Layer Tabs
            tab1, tab2 = st.tabs(["🏢 Agency Performance Workspace", "📦 Product Performance Summary"])
            
            with tab1:
                st.subheader("📋 Agency Performance Breakdown by Product Type")
                pivot_display = get_agency_matrix(filtered_df)
                
                if not pivot_display.empty:
                    pivot_display = pivot_display.set_index(['Agency_Class', 'BRANCH'])
                    
                    multi_columns = []
                    for col in pivot_display.columns:
                        if col == 'FSP':
                            multi_columns.append(('FSP', ''))
                        elif col in ['Buddha', 'Tablet', 'Urn', 'Lot']:
                            multi_columns.append(('Non - FSP', col))
                        elif col == 'Total Sales':
                            multi_columns.append(('Total Sales', '')) 
                        else:
                            multi_columns.append(('Other', col))
                            
                    pivot_display.columns = pd.MultiIndex.from_tuples(multi_columns)
                    
                    col1, col2 = st.columns([4, 3])
                    with col1:
                        st.dataframe(pivot_display.style.format("${:,.2f}"), width="stretch")
                    with col2:
                        chart_df = filtered_df.groupby(['Report_Month', 'Agency_Class', 'Product_Class'])[target_value_col].sum().reset_index()
                        
                        # Fluid Axis Configuration
                        x_axis_var = "Agency_Class" if len(month_toggle) <= 1 else "Report_Month"
                        facet_var = None if len(month_toggle) <= 1 else "Agency_Class"
                        
                        fig_bar = px.bar(
                            chart_df, x=x_axis_var, y=target_value_col, color="Product_Class",
                            facet_col=facet_var, facet_col_wrap=2,
                            title="Month-on-Month Revenue Mix", 
                            labels={target_value_col: "Sales ($)", "Agency_Class": "Agency", "Report_Month": "Month"},
                            barmode="stack", template="plotly_white"
                        )
                        fig_bar.update_layout(height=380, margin=dict(t=30, b=10, l=10, r=10))
                        st.plotly_chart(fig_bar, width="stretch")
                    
            with tab2:
                st.subheader("📦 Total Performance by Product Type Only")
                final_summary_df = get_product_summary(filtered_df)
                
                if not final_summary_df.empty:
                    col3, col4 = st.columns([3, 2])
                    with col3:
                        st.dataframe(
                            final_summary_df.style.format("${:,.2f}")
                            .set_properties(**{'font-weight': 'bold'}, subset=pd.IndexSlice[['Non-FSP Total', 'Grand Total'], :]),
                            width="stretch"
                        )
                    with col4:
                        product_summary_chart = filtered_df.groupby('Product_Class')[target_value_col].sum().reset_index()
                        product_summary_chart.columns = ['Product Type', 'Total Sales']
                        fig_donut = px.pie(
                            product_summary_chart, values='Total Sales', names='Product Type', 
                            hole=0.4, title="Product Category Share", template="plotly_white"
                        )
                        fig_donut.update_layout(height=300, margin=dict(t=30, b=10, l=10, r=10))
                        st.plotly_chart(fig_donut, width="stretch")
        else:
            st.error(f"⚠️ Target sales values column header not identified in the uploaded schema.")
    else:
        st.warning("No records found matching your selected configuration criteria.")
else:
    st.info("💡 Welcome! Please upload your monthly 'Closed Sales Report' Excel files above to begin analysis.")
