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

    # Color definitions
    agency_colours = {"FGY": "#808080", "ZB": "#800080", "APG": "#000080", "SLA": "#FF0000", "JFL": "#00FFFF"}
    product_colours = {"FSP": "#1f77b4", "Pedestal": "#ff7f0e", "Niche": "#2ca02c", "Others": "#d62728"}

    def format_big_number(value):
        if abs(value) >= 1e6: return f"{value/1e6:.2f}m"
        elif abs(value) >= 1e3: return f"{value/1e3:.2f}k"
        else: return f"{value:.2f}"

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

    # --- PDF Generation Engine (Programmatic layout avoiding Kaleido entirely) ---
    def generate_pdf_report(branch_data_dict, total_df):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        styles = getSampleStyleSheet()
        
        # Custom Typography
        title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=24, spaceAfter=15, textColor=colors.HexColor("#1f77b4"))
        h2_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'], fontSize=16, spaceBefore=15, spaceAfter=10, textColor=colors.HexColor("#2ca02c"))

        elements = [Paragraph("Executive Sales Summary Report", title_style), Spacer(1, 12)]
        
        # Section 1: Consolidated Overview
        elements.append(Paragraph("1. Consolidated Overview Across Active Branches", h2_style))
        summary_data = [["Branch / Attribute", "Total Confirmed Sales", "Unique Agencies", "Data Records"]]
        
        for br_name, df_br in branch_data_dict.items():
            if not df_br.empty:
                summary_data.append([
                    f"{br_name} Branch", 
                    f"${df_br['NETMAINPRODUCT'].sum():,.2f}", 
                    str(df_br['Agency'].nunique()), 
                    str(len(df_br))
                ])
        summary_data.append([
            "Total Consolidated", 
            f"${total_df['NETMAINPRODUCT'].sum():,.2f}", 
            str(total_df['Agency'].nunique()), 
            str(len(total_df))
        ])
        
        t_summary = Table(summary_data, hAlign='LEFT')
        t_summary.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1f77b4")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#e6e6e6")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ]))
        elements.append(t_summary)
        elements.append(Spacer(1, 15))

        # Section 2: Detailed Performance Matrix by Agency
        elements.append(Paragraph("2. Consolidated Performance Matrix by Agency", h2_style))
        agency_perf = total_df.groupby("Agency")["NETMAINPRODUCT"].sum().reset_index().sort_values("NETMAINPRODUCT", ascending=False)
        
        perf_data = [["Agency Name", "Aggregated Financial Performance", "Share %"]]
        total_sales_val = total_df['NETMAINPRODUCT'].sum()
        for _, row in agency_perf.iterrows():
            pct = (row['NETMAINPRODUCT'] / total_sales_val) * 100
            perf_data.append([row['Agency'], f"${row['NETMAINPRODUCT']:,.2f}", f"{pct:.1f}%"])
            
        t_perf = Table(perf_data, hAlign='LEFT')
        t_perf.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#7f7f7f")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        elements.append(t_perf)

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

    # Clean out unparseable or completely empty sheets
    active_branches = {k: v for k, v in branch_dfs.items() if v is not None and not v.empty}

    if active_branches:
        # Build master unified dataframe
        total_df = pd.concat(active_branches.values(), ignore_index=True)
        
        # Create Dynamic UI Tabs based on which inputs are present
        tab_titles = ["Consolidated Overview"] + [f"{name} Branch" for name in active_branches.keys()]
        tabs = st.tabs(tab_titles)

        # ------------------------------------------------------------
        # TAB 0: CONSOLIDATED METRICS & GENERATE EXPORTS
        # ------------------------------------------------------------
        with tabs[0]:
            st.header("🏢 Unified Corporate Overview")
            
            # Action and PDF Download Bar
            pdf_buffer = generate_pdf_report(active_branches, total_df)
            st.download_button(
                label="📥 Download Consolidated Executive Report (PDF)",
                data=pdf_buffer,
                file_name="consolidated_executive_sales_report.pdf",
                mime="application/pdf",
                type="primary"
            )
            st.write("---")

            # High level metrics
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Combined Sales", f"${total_df['NETMAINPRODUCT'].sum():,.2f}")
            c2.metric("Active Operating Branches", len(active_branches))
            c3.metric("Total Confirmed Transactions", len(total_df))

            # Cross Branch Comparative Performance Charts
            st.subheader("Branch vs Branch Performance Breakdown")
            branch_summary = total_df.groupby("Branch")["NETMAINPRODUCT"].sum().reset_index()
            fig_br = px.bar(branch_summary, x="Branch", y="NETMAINPRODUCT", text=branch_summary["NETMAINPRODUCT"].apply(format_big_number),
                            title="Revenue Contributed by Location Branch", color="Branch")
            st.plotly_chart(fig_br, width="stretch")

            # Consolidated Product Mix & Agency Breakdown
            col_l, col_r = st.columns(2)
            with col_l:
                st.subheader("Global Product Strategy Mix")
                prod_sum = total_df.groupby("Product_Type")["NETMAINPRODUCT"].sum().reset_index()
                fig_p = px.pie(prod_sum, names="Product_Type", values="NETMAINPRODUCT", hole=0.3, color="Product_Type", color_discrete_map=product_colours)
                st.plotly_chart(fig_p, width="stretch")
            
            with col_r:
                st.subheader("Inter-Branch Agency Landscape")
                ag_br_pivot = total_df.groupby(["Agency", "Branch"])["NETMAINPRODUCT"].sum().reset_index()
                fig_ag_br = px.bar(ag_br_pivot, x="Agency", y="NETMAINPRODUCT", color="Branch", barmode="stack", title="Agency Contribution split by Branch Location")
                st.plotly_chart(fig_ag_br, width="stretch")

        # ------------------------------------------------------------
        # DYNAMIC TABS 1+: INDIVIDUAL SEGMENTED BRANCH PANELS
        # ------------------------------------------------------------
        for idx, (b_name, b_df) in enumerate(active_branches.items(), start=1):
            with tabs[idx]:
                st.header(f"📍 Operational Analysis: {b_name} Branch")
                
                b_total = b_df["NETMAINPRODUCT"].sum()
                agency_sales = b_df.groupby("Agency")["NETMAINPRODUCT"].sum().reset_index()
                agency_sales["Display"] = agency_sales["NETMAINPRODUCT"].apply(format_big_number)
                
                product_sales = b_df.groupby("Product_Type")["NETMAINPRODUCT"].sum().reset_index()
                product_sales["Display"] = product_sales["NETMAINPRODUCT"].apply(format_big_number)

                # Segmented Metrics
                mc1, mc2, mc3 = st.columns(3)
                mc1.metric(f"{b_name} Total Revenue", f"${b_total:,.2f}")
                mc2.metric("Active Local Agencies", len(agency_sales))
                mc3.metric("Volume of Line Orders", len(b_df))

                # Segmented Bar Chart
                st.subheader("Agency Performance Breakdown")
                fig_agency = px.bar(agency_sales, x="Agency", y="NETMAINPRODUCT", text="Display", color="Agency",
                                    color_discrete_map=agency_colours, title=f"{b_name} - Revenue by Placement Channel")
                fig_agency.update_traces(textposition="outside")
                st.plotly_chart(fig_agency, width="stretch")

                # Split Product View Grid
                sub_l, sub_r = st.columns(2)
                with sub_l:
                    st.subheader("Product Group Delivery Distribution")
                    fig_product = px.pie(product_sales, names="Product_Type", values="NETMAINPRODUCT", hole=0.3, color="Product_Type", color_discrete_map=product_colours)
                    st.plotly_chart(fig_product, width="stretch")
                
                with sub_r:
                    st.subheader("Raw Local Datatable Extract")
                    st.dataframe(b_df[["FILE_NO", "Agency", "Product_Type", "NETMAINPRODUCT"]], width="stretch")

    else:
        st.info("👋 Welcome! Please upload at least one valid Branch Excel data sheet via the sidebar layout to initialize the dashboard panels.")

except Exception as e:
    st.error(f"🛑 Critical System Exception Triggered:\n\n{e}\n\n{traceback.format_exc()}")
