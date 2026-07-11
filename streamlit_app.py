import streamlit as st
import pandas as pd
import plotly.express as px
import io
import traceback
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

try:
    st.set_page_config(page_title="Multi-Branch Sales Dashboard", layout="wide")

    st.title("📊 Sales Dashboard - Multi-Branch Analysis")
    st.markdown("Upload Excel files for **CCK**, **LST**, and **TLT** branches to view individual and consolidated insights.")

    # Corporate Hierarchy sequence
    AGENCY_ORDER = ["FGY", "ZB", "APG", "SLA", "JFL"]

    # Color definitions
    agency_colours = {"FGY": "#808080", "ZB": "#800080", "APG": "#000080", "SLA": "#FF0000", "JFL": "#00FFFF"}
    product_colours = {"FSP": "#1f77b4", "Pedestal": "#ff7f0e", "Niche": "#2ca02c", "Others": "#d62728"}

    # Formats numbers to strings with commas and dollar signs for easy copy/pasting
    def format_currency(value):
        if pd.isna(value):
            return "$0.00"
        return f"${value:,.2f}"

    def format_currency_df(df, numeric_cols):
        df_display = df.copy()
        for col in numeric_cols:
            if col in df_display.columns:
                df_display[col] = df_display[col].apply(format_currency)
        return df_display

    # Formats chart text to compact million notation (e.g., $4.98m)
    def format_chart_label(value):
        if pd.isna(value) or value == 0:
            return ""
        if abs(value) >= 1e6:
            return f"${value/1e6:.2f}m"
        elif abs(value) >= 1e3:
            return f"${value/1e3:.1f}k"
        return f"${value:.2f}"

    def format_pct(value):
        if pd.isna(value):
            return "0.00%"
        return f"{value:,.2f}%"

    # Enforces explicit agency sequence hierarchy on dataframes
    def sort_by_corporate_hierarchy(df, agency_col="Agency"):
        df[agency_col] = pd.Categorical(df[agency_col], categories=AGENCY_ORDER, ordered=True)
        return df.sort_values(agency_col)

    # --- Processing Engine ---
    def process_branch_file(uploaded_file, branch_name):
        df_raw = pd.read_excel(uploaded_file, header=None)
        header_row_idx = None
        for idx, row in df_raw.iterrows():
            if row.astype(str).str.contains("FILE_NO").any():
                header_row_idx = idx
                break
        if header_row_idx is None:
            return None

        df = pd.read_excel(uploaded_file, header=header_row_idx)
        df.columns = df.columns.str.strip()

        required_cols = ["STATUS", "NETMAINPRODUCT", "CBDD_NAME", "BDD_NAME", "PRODUCT_CODE"]
        if any(col not in df.columns for col in required_cols):
            return None

        df["NETMAINPRODUCT"] = pd.to_numeric(df["NETMAINPRODUCT"], errors="coerce")
        df_confirmed = df[df["STATUS"].str.upper() == "CONFIRM"].copy()
        df_confirmed = df_confirmed[df_confirmed["NETMAINPRODUCT"].notna() & (df_confirmed["NETMAINPRODUCT"] != 0)]
        
        if df_confirmed.empty:
            return pd.DataFrame()

        agency_rename = {
            "FU GUI SERVICES": "FGY", "ZENBOX PTE LTD": "ZB",
            "APG ADVISORY PTE. LTD.": "APG", "SINGAPORE LIFESTYLE ASSOCIATES PTE LTD.": "SLA",
            "JF LIFE CONSULTANT PTE LTD": "JFL",
        }

        def get_agency(row):
            cbd = row.get("CBDD_NAME", "")
            if pd.notna(cbd) and str(cbd).strip() != "":
                raw = str(cbd).strip().upper()
            else:
                bdd = row.get("BDD_NAME", "")
                raw = str(bdd).strip().upper() if pd.notna(bdd) and str(bdd).strip() != "" else "Others"
            for key, value in agency_rename.items():
                if key in raw: return value
            return raw

        df_confirmed["Agency"] = df_confirmed.apply(get_agency, axis=1)

        def get_product_type(code):
            if pd.isna(code): return "Others"
            code_str = str(code).strip().upper()
            if code_str == "P": return "FSP"
            elif code_str == "TABLET": return "Pedestal"
            elif code_str == "URN": return "Niche"
            return "Others"

        df_confirmed["Product_Type"] = df_confirmed["PRODUCT_CODE"].apply(get_product_type)
        df_confirmed["Branch"] = branch_name
        return df_confirmed

    # --- PDF Generation Engine ---
    def generate_pdf_report(branch_data_dict, total_df):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=40)
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=22, spaceAfter=12, textColor=colors.HexColor("#1f77b4"))
        h2_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'], fontSize=16, spaceBefore=18, spaceAfter=8, textColor=colors.HexColor("#1f77b4"))
        h3_style = ParagraphStyle('SubSectionHeading', parent=styles['Heading3'], fontSize=12, spaceBefore=12, spaceAfter=6, textColor=colors.HexColor("#2ca02c"))

        elements = [Paragraph("Consolidated Executive Sales & Product Mix Report", title_style), Spacer(1, 10)]
        
        # -------------------------------------------------------------------------
        # 1. BRANCH PERFORMANCE BREAKDOWN
        # -------------------------------------------------------------------------
        elements.append(Paragraph("1. Branch Performance & Product Mix Strategy", h2_style))
        
        for br_name, df_br in branch_data_dict.items():
            elements.append(Paragraph(f"📍 {br_name} Branch Breakdown", h3_style))
            
            br_matrix = df_br.pivot_table(index="Agency", columns="Product_Type", values="NETMAINPRODUCT", aggfunc="sum", fill_value=0)
            
            for col in ["FSP", "Pedestal", "Niche", "Others"]:
                if col not in br_matrix.columns:
                    br_matrix[col] = 0.0
            
            br_matrix = br_matrix[["FSP", "Pedestal", "Niche", "Others"]].copy()
            br_matrix["Total Sales"] = br_matrix.sum(axis=1)
            
            # Enforce sequence layout hierarchy in document
            br_matrix = br_matrix.reindex(AGENCY_ORDER).fillna(0)
            
            br_table_data = [["Agency", "FSP", "Pedestal", "Niche", "Others", "Total Contribution"]]
            for idx, row in br_matrix.iterrows():
                br_table_data.append([
                    idx, 
                    format_currency(row['FSP']), 
                    format_currency(row['Pedestal']), 
                    format_currency(row['Niche']), 
                    format_currency(row['Others']), 
                    format_currency(row['Total Sales'])
                ])
                
            t_br = Table(br_table_data, hAlign='LEFT')
            t_br.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2ca02c")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('PADDING', (0,0), (-1,-1), 5),
            ]))
            elements.append(t_br)
            elements.append(Spacer(1, 10))

        # -------------------------------------------------------------------------
        # 2. OVERALL CORPORATE PERFORMANCE
        # -------------------------------------------------------------------------
        elements.append(Paragraph("2. Overall Corporate Performance", h2_style))
        
        # 2A: OVERALL BY AGENCY
        elements.append(Paragraph("2a. Overall Performance by Agency (Cross-Branch Product Mix)", h3_style))
        overall_matrix = total_df.pivot_table(index="Agency", columns="Product_Type", values="NETMAINPRODUCT", aggfunc="sum", fill_value=0)
        
        for col in ["FSP", "Pedestal", "Niche", "Others"]:
            if col not in overall_matrix.columns:
                overall_matrix[col] = 0.0
        overall_matrix = overall_matrix[["FSP", "Pedestal", "Niche", "Others"]].copy()
        overall_matrix["Total Contribution"] = overall_matrix.sum(axis=1)
        
        # Enforce corporate hierarchy sequence layout
        overall_matrix = overall_matrix.reindex(AGENCY_ORDER).fillna(0)
        
        agency_data = [["Agency", "FSP", "Pedestal", "Niche", "Others", "Total Contribution"]]
        for idx, row in overall_matrix.iterrows():
            agency_data.append([
                idx, 
                format_currency(row['FSP']), 
                format_currency(row['Pedestal']), 
                format_currency(row['Niche']), 
                format_currency(row['Others']), 
                format_currency(row['Total Contribution'])
            ])
            
        t_agency = Table(agency_data, hAlign='LEFT')
        t_agency.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#7f7f7f")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        elements.append(t_agency)
        elements.append(Spacer(1, 10))

        # 2B: OVERALL BY PRODUCT MIX
        elements.append(Paragraph("2b. Overall Performance by Product Strategy", h3_style))
        overall_product = total_df.groupby("Product_Type")["NETMAINPRODUCT"].sum().reset_index()
        overall_product = overall_product.sort_values("NETMAINPRODUCT", ascending=False)
        total_revenue = overall_product["NETMAINPRODUCT"].sum()
        
        prod_data = [["Product Category", "Total Sales", "Portfolio Share %"]]
        for _, row in overall_product.iterrows():
            share = (row['NETMAINPRODUCT'] / total_revenue) * 100
            prod_data.append([
                row['Product_Type'], 
                format_currency(row['NETMAINPRODUCT']), 
                format_pct(share)
            ])
            
        t_prod = Table(prod_data, hAlign='LEFT')
        t_prod.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1f77b4")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        elements.append(t_prod)

        doc.build(elements)
        buffer.seek(0)
        return buffer

    # --- Sidebar File Upload Handling ---
    st.sidebar.header("📁 Branch File Uploaders")
    cck_file = st.sidebar.file_uploader("Upload CCK Branch Excel", type=["xlsx", "xls"])
    lst_file = st.sidebar.file_uploader("Upload LST Branch Excel", type=["xlsx", "xls"])
    tlt_file = st.sidebar.file_uploader("Upload TLT Branch Excel", type=["xlsx", "xls"])

    branch_dfs = {}
    if cck_file: branch_dfs["CCK"] = process_branch_file(cck_file, "CCK")
    if lst_file: branch_dfs["LST"] = process_branch_file(lst_file, "LST")
    if tlt_file: branch_dfs["TLT"] = process_branch_file(tlt_file, "TLT")

    active_branches = {k: v for k, v in branch_dfs.items() if v is not None and not v.empty}

    if active_branches:
        total_df = pd.concat(active_branches.values(), ignore_index=True)
        
        tab_titles = ["Consolidated Overview"] + [f"{name} Branch" for name in active_branches.keys()]
        tabs = st.tabs(tab_titles)

        # ------------------------------------------------------------
        # TAB 0: CONSOLIDATED OVERVIEW
        # ------------------------------------------------------------
        with tabs[0]:
            st.header("🏢 Unified Corporate Overview")
            
            pdf_buffer = generate_pdf_report(active_branches, total_df)
            st.download_button(
                label="📥 Download Consolidated Executive Report (PDF)",
                data=pdf_buffer,
                file_name="consolidated_executive_sales_report.pdf",
                mime="application/pdf",
                type="primary"
            )
            st.write("---")

            # High Level Metrics
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Combined Sales", format_currency(total_df['NETMAINPRODUCT'].sum()))
            c2.metric("Active Operating Branches", len(active_branches))
            c3.metric("Total Confirmed Transactions", f"{len(total_df):,}")

            st.write("---")
            
            # --- OVERALL PERFORMANCE BY AGENCY ---
            st.subheader("Overall Performance by Agency")
            global_agency_prod = total_df.groupby(["Agency", "Product_Type"])["NETMAINPRODUCT"].sum().reset_index()
            global_agency_prod = sort_by_corporate_hierarchy(global_agency_prod, "Agency")
            
            # Build chart labels using the compact version requested ($4.98m)
            chart_text = global_agency_prod["NETMAINPRODUCT"].apply(format_chart_label)

            fig_gap = px.bar(global_agency_prod, x="Agency", y="NETMAINPRODUCT", color="Product_Type",
                             title="Consolidated Product Breakdown Across All Agencies", 
                             color_discrete_map=product_colours, barmode="stack", 
                             text=chart_text)
            fig_gap.update_layout(xaxis={'categoryorder':'array', 'categoryarray': AGENCY_ORDER})
            st.plotly_chart(fig_gap, width="stretch")
            
            global_pivot = total_df.pivot_table(index="Agency", columns="Product_Type", values="NETMAINPRODUCT", aggfunc="sum", fill_value=0)
            for p_col in ["FSP", "Pedestal", "Niche", "Others"]:
                if p_col not in global_pivot.columns:
                    global_pivot[p_col] = 0.0
            global_pivot = global_pivot[["FSP", "Pedestal", "Niche", "Others"]]
            global_pivot["Total Contribution ($)"] = global_pivot.sum(axis=1)
            
            # Enforce corporate hierarchy on data table index layout
            global_pivot = global_pivot.reindex(AGENCY_ORDER).fillna(0)
            
            st.markdown("**Data Table: Overall Agency Product Mix Matrix**")
            display_global_pivot = format_currency_df(global_pivot, ["FSP", "Pedestal", "Niche", "Others", "Total Contribution ($)"])
            st.dataframe(display_global_pivot, width="stretch")

            st.write("---")

            # --- OVERALL PERFORMANCE BY PRODUCT MIX ---
            st.subheader("Overall Performance by Product Mix")
            prod_sum = total_df.groupby("Product_Type")["NETMAINPRODUCT"].sum().reset_index()
            prod_sum["Total Sales"] = prod_sum["NETMAINPRODUCT"]
            
            fig_p = px.pie(prod_sum, names="Product_Type", values="Total Sales", hole=0.3, 
                           title="Global Product Portfolio Split", color="Product_Type", color_discrete_map=product_colours)
            st.plotly_chart(fig_p, width="stretch")
            
            st.markdown("**Data Table: Overall Portfolio Contribution**")
            prod_table = prod_sum[["Product_Type", "Total Sales"]].sort_values("Total Sales", ascending=False)
            prod_table["Portfolio Share %"] = (prod_table["Total Sales"] / prod_table["Total Sales"].sum()) * 100
            
            display_prod_table = format_currency_df(prod_table, ["Total Sales"])
            display_prod_table["Portfolio Share %"] = display_prod_table["Portfolio Share %"].apply(format_pct)
            st.dataframe(display_prod_table, width="stretch", hide_index=True)


        # ------------------------------------------------------------
        # DYNAMIC TABS 1+: INDIVIDUAL SEGMENTED BRANCH PANELS
        # ------------------------------------------------------------
        for idx, (b_name, b_df) in enumerate(active_branches.items(), start=1):
            with tabs[idx]:
                st.header(f"📍 Operational Analysis: {b_name} Branch")
                
                b_total = b_df["NETMAINPRODUCT"].sum()
                
                mc1, mc2, mc3 = st.columns(3)
                mc1.metric(f"{b_name} Total Revenue", format_currency(b_total))
                mc2.metric("Active Local Agencies", b_df["Agency"].nunique())
                mc3.metric("Volume of Line Orders", f"{len(b_df):,}")

                # Interactive Stacked Bar Chart
                st.subheader(f"Agency Performance & Product Mix in {b_name}")
                branch_agency_prod = b_df.groupby(["Agency", "Product_Type"])["NETMAINPRODUCT"].sum().reset_index()
                branch_agency_prod = sort_by_corporate_hierarchy(branch_agency_prod, "Agency")
                
                # Dynamic visual label updates to compact format
                branch_chart_text = branch_agency_prod["NETMAINPRODUCT"].apply(format_chart_label)

                fig_br_ap = px.bar(branch_agency_prod, x="Agency", y="NETMAINPRODUCT", color="Product_Type",
                                  title=f"{b_name} Branch - Revenue by Placement Channel",
                                  color_discrete_map=product_colours, barmode="stack",
                                  text=branch_chart_text)
                fig_br_ap.update_layout(xaxis={'categoryorder':'array', 'categoryarray': AGENCY_ORDER})
                st.plotly_chart(fig_br_ap, width="stretch")

                # Copy/Paste Ready Formatted Data Table (Long-form numbers preserved)
                st.markdown(f"**Data Table: {b_name} Agency Performance Matrix**")
                branch_pivot = b_df.pivot_table(index="Agency", columns="Product_Type", values="NETMAINPRODUCT", aggfunc="sum", fill_value=0)
                
                for p_col in ["FSP", "Pedestal", "Niche", "Others"]:
                    if p_col not in branch_pivot.columns:
                        branch_pivot[p_col] = 0.0
                        
                branch_pivot = branch_pivot[["FSP", "Pedestal", "Niche", "Others"]]
                branch_pivot["Total Sales ($)"] = branch_pivot.sum(axis=1)
                branch_pivot["Branch Contribution %"] = (branch_pivot["Total Sales ($)"] / b_total) * 100
                
                # Order row index structure explicitly by sequence hierarchy
                branch_pivot = branch_pivot.reindex(AGENCY_ORDER).fillna(0)
                
                display_branch_pivot = format_currency_df(branch_pivot, ["FSP", "Pedestal", "Niche", "Others", "Total Sales ($)"])
                display_branch_pivot["Branch Contribution %"] = display_branch_pivot["Branch Contribution %"].apply(format_pct)
                
                st.dataframe(display_branch_pivot, width="stretch")
                
                st.write("---")
                st.markdown("**Raw Branch Ledger Records**")
                display_raw = b_df[["FILE_NO", "Agency", "Product_Type", "NETMAINPRODUCT"]].copy()
                display_raw = sort_by_corporate_hierarchy(display_raw, "Agency")
                display_raw = format_currency_df(display_raw, ["NETMAINPRODUCT"])
                st.dataframe(display_raw, width="stretch", hide_index=True)

    else:
        st.info("👋 Welcome! Please upload at least one valid Branch Excel data sheet via the sidebar layout to initialize the dashboard panels.")

except Exception as e:
    st.error(f"🛑 Critical System Exception Triggered:\n\n{e}\n\n{traceback.format_exc()}")
