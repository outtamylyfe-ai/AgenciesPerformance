import streamlit as st
import pandas as pd
import plotly.express as px
import io
import traceback
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.barcharts import VerticalBarChart  # <-- Fixed import here
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.legends import Legend

try:
    st.set_page_config(page_title="Multi-Branch Sales Dashboard", layout="wide")

    st.title("📊 Sales Dashboard - Multi-Branch Analysis")
    st.markdown("Upload Excel files for **CCK**, **LST**, and **TLT** branches to view individual and consolidated insights.")

    # Corporate Hierarchy sequence
    AGENCY_ORDER = ["FGY", "ZB", "APG", "SLA", "JFL"]
    PRODUCT_ORDER = ["FSP", "Pedestal", "Niche", "Others"]

    # Color definitions
    product_colours = {"FSP": "#1f77b4", "Pedestal": "#ff7f0e", "Niche": "#2ca02c", "Others": "#d62728"}
    rl_colors = [colors.HexColor("#1f77b4"), colors.HexColor("#ff7f0e"), colors.HexColor("#2ca02c"), colors.HexColor("#d62728")]

    # Formatting utilities
    def format_currency(value):
        if pd.isna(value): return "$0.00"
        return f"${value:,.2f}"

    def format_currency_df(df, numeric_cols):
        df_display = df.copy()
        for col in numeric_cols:
            if col in df_display.columns:
                df_display[col] = df_display[col].apply(format_currency)
        return df_display

    def format_chart_label(value):
        if pd.isna(value) or value == 0: return ""
        if abs(value) >= 1e6: return f"${value/1e6:.2f}m"
        elif abs(value) >= 1e3: return f"${value/1e3:.1f}k"
        return f"${value:.2f}"

    def format_pct(value):
        if pd.isna(value): return "0.00%"
        return f"{value:,.2f}%"

    def sort_by_corporate_hierarchy(df, agency_col="Agency"):
        df[agency_col] = pd.Categorical(df[agency_col], categories=AGENCY_ORDER, ordered=True)
        return df.sort_values(agency_col)

    # --- Processing Engine ---
    def process_branch_file(uploaded_file, branch_name):
       # --- Native ReportLab Vector Drawing Generator ---
    def generate_pdf_chart(pivot_df):
        # Prepare 2D matrix array matching AGENCY_ORDER x PRODUCT_ORDER
        chart_data = []
        for p_type in PRODUCT_ORDER:
            row_series = []
            for agency in AGENCY_ORDER:
                val = pivot_df.loc[agency, p_type] if agency in pivot_df.index else 0.0
                row_series.append(val)
            chart_data.append(row_series)

        d = Drawing(450, 180)
        chart = VerticalBarChart() # <-- Instantiated as standard VerticalBarChart
        chart.x = 40
        chart.y = 25
        chart.height = 130
        chart.width = 380
        chart.data = chart_data
        
        # Enable stacked layout configuration safely 
        chart.categoryAxis.style = 'stacked' # <-- This property handles the stacking!
        
        chart.categoryAxis.categoryNames = AGENCY_ORDER
        chart.categoryAxis.labels.fontSize = 9
        chart.valueAxis.valueMin = 0
        chart.valueAxis.labels.fontSize = 8

        # Map programmatic corporate color assignments
        for idx, color_obj in enumerate(rl_colors):
            chart.bars[idx].fillColor = color_obj

        # Legend Configuration
        legend = Legend()
        legend.x = 350
        legend.y = 150
        legend.alignment = 'right'
        legend.fontName = 'Helvetica'
        legend.fontSize = 8
        legend.colorNamePairs = list(zip(rl_colors, PRODUCT_ORDER))
        
        d.add(chart)
        d.add(legend)
        return d
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

    # --- Native ReportLab Vector Drawing Generator ---
    def generate_pdf_chart(pivot_df):
        # Prepare 2D matrix array matching AGENCY_ORDER x PRODUCT_ORDER
        chart_data = []
        for p_type in PRODUCT_ORDER:
            row_series = []
            for agency in AGENCY_ORDER:
                val = pivot_df.loc[agency, p_type] if agency in pivot_df.index else 0.0
                row_series.append(val)
            chart_data.append(row_series)

        d = Drawing(450, 180)
        chart = VerticalStackedBarChart()
        chart.x = 40
        chart.y = 25
        chart.height = 130
        chart.width = 380
        chart.data = chart_data
        chart.categoryAxis.categoryNames = AGENCY_ORDER
        chart.categoryAxis.labels.fontSize = 9
        chart.valueAxis.valueMin = 0
        chart.valueAxis.labels.fontSize = 8

        # Map programmatic corporate color assignments
        for idx, color_obj in enumerate(rl_colors):
            chart.bars[idx].fillColor = color_obj

        # Legend Configuration
        legend = Legend()
        legend.x = 350
        legend.y = 150
        legend.alignment = 'right'
        legend.fontName = 'Helvetica'
        legend.fontSize = 8
        legend.colorNamePairs = list(zip(rl_colors, PRODUCT_ORDER))
        
        d.add(chart)
        d.add(legend)
        return d

    # --- PDF Generation Engine ---
    def generate_pdf_report(branch_data_dict, total_df):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=40)
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=20, spaceAfter=10, textColor=colors.HexColor("#1f77b4"))
        h2_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'], fontSize=14, spaceBefore=14, spaceAfter=6, textColor=colors.HexColor("#1f77b4"))
        h3_style = ParagraphStyle('SubSectionHeading', parent=styles['Heading3'], fontSize=11, spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#2ca02c"))

        elements = [Paragraph("Consolidated Corporate Sales & Product Matrix", title_style), Spacer(1, 5)]
        grand_total = total_df['NETMAINPRODUCT'].sum()

        # -------------------------------------------------------------------------
        # 1. SEGMENTED OPERATIONAL BREAKDOWN BY BRANCH
        # -------------------------------------------------------------------------
        elements.append(Paragraph("1. Operational Performance Breakdown by Branch", h2_style))
        
        for br_name, df_br in branch_data_dict.items():
            elements.append(Paragraph(f"📍 {br_name} Branch Performance Matrix", h3_style))
            br_total = df_br["NETMAINPRODUCT"].sum()
            
            br_pivot = df_br.pivot_table(index="Agency", columns="Product_Type", values="NETMAINPRODUCT", aggfunc="sum", fill_value=0)
            for col in PRODUCT_ORDER:
                if col not in br_pivot.columns: br_pivot[col] = 0.0
            br_pivot = br_pivot[PRODUCT_ORDER].reindex(AGENCY_ORDER).fillna(0)
            
            # Draw Vector Graphical Chart Element
            elements.append(generate_pdf_chart(br_pivot))
            elements.append(Spacer(1, 10))

            br_table_data = [["Agency", "FSP", "Pedestal", "Niche", "Others", "Branch Vol %", "Global Vol %"]]
            for idx, row in br_pivot.iterrows():
                row_sum = row.sum()
                br_share = (row_sum / br_total * 100) if br_total > 0 else 0.0
                global_share = (row_sum / grand_total * 100) if grand_total > 0 else 0.0
                
                br_table_data.append([
                    idx, format_currency(row['FSP']), format_currency(row['Pedestal']),
                    format_currency(row['Niche']), format_currency(row['Others']),
                    format_pct(br_share), format_pct(global_share)
                ])
                
            t_br = Table(br_table_data, hAlign='LEFT')
            t_br.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2ca02c")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('PADDING', (0,0), (-1,-1), 4),
                ('FONTSIZE', (0,0), (-1,-1), 8),
            ]))
            elements.append(t_br)
            elements.append(Spacer(1, 15))

        # -------------------------------------------------------------------------
        # 2. OVERALL CORPORATE PERFORMANCE
        # -------------------------------------------------------------------------
        elements.append(Paragraph("2. Overall Corporate Performance Matrix", h2_style))
        
        # 2A: OVERALL BY AGENCY
        elements.append(Paragraph("2a. Consolidated Contribution Performance by Corporate Agency Hierarchy", h3_style))
        overall_pivot = total_df.pivot_table(index="Agency", columns="Product_Type", values="NETMAINPRODUCT", aggfunc="sum", fill_value=0)
        for col in PRODUCT_ORDER:
            if col not in overall_pivot.columns: overall_pivot[col] = 0.0
        overall_pivot = overall_pivot[PRODUCT_ORDER].reindex(AGENCY_ORDER).fillna(0)
        
        # Add Global Corporate Level Stacked Chart Graphic
        elements.append(generate_pdf_chart(overall_pivot))
        elements.append(Spacer(1, 10))

        agency_data = [["Agency", "FSP", "Pedestal", "Niche", "Others", "Total Sales", "Corporate %"]]
        for idx, row in overall_pivot.iterrows():
            row_sum = row.sum()
            corp_share = (row_sum / grand_total * 100) if grand_total > 0 else 0.0
            agency_data.append([
                idx, format_currency(row['FSP']), format_currency(row['Pedestal']),
                format_currency(row['Niche']), format_currency(row['Others']),
                format_currency(row_sum), format_pct(corp_share)
            ])
            
        t_agency = Table(agency_data, hAlign='LEFT')
        t_agency.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#7f7f7f")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('PADDING', (0,0), (-1,-1), 4),
            ('FONTSIZE', (0,0), (-1,-1), 8),
        ]))
        elements.append(t_agency)

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
        grand_corporate_revenue = total_df['NETMAINPRODUCT'].sum()
        
        tab_titles = ["Consolidated Overview"] + [f"{name} Branch" for name in active_branches.keys()]
        tabs = st.tabs(tab_titles)

        # ------------------------------------------------------------
        # TAB 0: CONSOLIDATED OVERVIEW
        # ------------------------------------------------------------
        with tabs[0]:
            st.header("🏢 Unified Corporate Overview")
            
            pdf_buffer = generate_pdf_report(active_branches, total_df)
            st.download_button(
                label="📥 Download Consolidated Executive Report with Charts (PDF)",
                data=pdf_buffer,
                file_name="consolidated_executive_sales_report.pdf",
                mime="application/pdf",
                type="primary"
            )
            st.write("---")

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Combined Sales", format_currency(grand_corporate_revenue))
            c2.metric("Active Operating Branches", len(active_branches))
            c3.metric("Total Confirmed Transactions", f"{len(total_df):,}")
            st.write("---")
            
            # --- OVERALL PERFORMANCE BY AGENCY ---
            st.subheader("Overall Performance by Agency")
            global_agency_prod = total_df.groupby(["Agency", "Product_Type"])["NETMAINPRODUCT"].sum().reset_index()
            global_agency_prod = sort_by_corporate_hierarchy(global_agency_prod, "Agency")
            
            fig_gap = px.bar(global_agency_prod, x="Agency", y="NETMAINPRODUCT", color="Product_Type",
                             title="Consolidated Product Breakdown Across All Agencies", 
                             color_discrete_map=product_colours, barmode="stack", 
                             text=global_agency_prod["NETMAINPRODUCT"].apply(format_chart_label))
            fig_gap.update_layout(xaxis={'categoryorder':'array', 'categoryarray': AGENCY_ORDER})
            st.plotly_chart(fig_gap, width="stretch")
            
            global_pivot = total_df.pivot_table(index="Agency", columns="Product_Type", values="NETMAINPRODUCT", aggfunc="sum", fill_value=0)
            for p_col in PRODUCT_ORDER:
                if p_col not in global_pivot.columns: global_pivot[p_col] = 0.0
            global_pivot = global_pivot[PRODUCT_ORDER]
            global_pivot["Total Contribution ($)"] = global_pivot.sum(axis=1)
            global_pivot["Overall Corporate Contribution %"] = (global_pivot["Total Contribution ($)"] / grand_corporate_revenue) * 100
            
            global_pivot = global_pivot.reindex(AGENCY_ORDER).fillna(0)
            
            st.markdown("**Data Table: Overall Agency Product Mix Matrix**")
            display_global_pivot = format_currency_df(global_pivot, ["FSP", "Pedestal", "Niche", "Others", "Total Contribution ($)"])
            display_global_pivot["Overall Corporate Contribution %"] = display_global_pivot["Overall Corporate Contribution %"].apply(format_pct)
            st.dataframe(display_global_pivot, width="stretch")

            st.write("---")

            # --- OVERALL PERFORMANCE BY PRODUCT MIX ---
            st.subheader("Overall Performance by Product Mix")
            prod_sum = total_df.groupby("Product_Type")["NETMAINPRODUCT"].sum().reset_index()
            
            fig_p = px.pie(prod_sum, names="Product_Type", values="NETMAINPRODUCT", hole=0.3, 
                           title="Global Product Portfolio Split", color="Product_Type", color_discrete_map=product_colours)
            st.plotly_chart(fig_p, width="stretch")
            
            st.markdown("**Data Table: Overall Portfolio Contribution**")
            prod_table = prod_sum.rename(columns={"NETMAINPRODUCT": "Total Sales"}).sort_values("Total Sales", ascending=False)
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

                st.subheader(f"Agency Performance & Product Mix in {b_name}")
                branch_agency_prod = b_df.groupby(["Agency", "Product_Type"])["NETMAINPRODUCT"].sum().reset_index()
                branch_agency_prod = sort_by_corporate_hierarchy(branch_agency_prod, "Agency")
                
                fig_br_ap = px.bar(branch_agency_prod, x="Agency", y="NETMAINPRODUCT", color="Product_Type",
                                  title=f"{b_name} Branch - Revenue by Placement Channel",
                                  color_discrete_map=product_colours, barmode="stack",
                                  text=branch_agency_prod["NETMAINPRODUCT"].apply(format_chart_label))
                fig_br_ap.update_layout(xaxis={'categoryorder':'array', 'categoryarray': AGENCY_ORDER})
                st.plotly_chart(fig_br_ap, width="stretch")

                st.markdown(f"**Data Table: {b_name} Agency Performance Matrix**")
                branch_pivot = b_df.pivot_table(index="Agency", columns="Product_Type", values="NETMAINPRODUCT", aggfunc="sum", fill_value=0)
                
                for p_col in PRODUCT_ORDER:
                    if p_col not in branch_pivot.columns: branch_pivot[p_col] = 0.0
                        
                branch_pivot = branch_pivot[PRODUCT_ORDER]
                branch_pivot["Total Branch Sales ($)"] = branch_pivot.sum(axis=1)
                branch_pivot["Agency Contribution in Branch %"] = (branch_pivot["Total Branch Sales ($)"] / b_total) * 100
                branch_pivot["Agency Branch Contribution in Overall %"] = (branch_pivot["Total Branch Sales ($)"] / grand_corporate_revenue) * 100
                
                branch_pivot = branch_pivot.reindex(AGENCY_ORDER).fillna(0)
                
                display_branch_pivot = format_currency_df(branch_pivot, ["FSP", "Pedestal", "Niche", "Others", "Total Branch Sales ($)"])
                display_branch_pivot["Agency Contribution in Branch %"] = display_branch_pivot["Agency Contribution in Branch %"].apply(format_pct)
                display_branch_pivot["Agency Branch Contribution in Overall %"] = display_branch_pivot["Agency Branch Contribution in Overall %"].apply(format_pct)
                
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
