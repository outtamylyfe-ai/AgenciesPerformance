import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

st.set_page_config(page_title="Sales Dashboard", layout="wide")

st.title("📊 Sales Dashboard - Confirmed Sales Analysis")

st.markdown("Upload an Excel file containing sales data to view dashboard.")

# Custom colour mapping for agencies
agency_colours = {
    "FGY": "#808080",   # grey
    "ZB": "#800080",    # purple
    "APG": "#000080",   # navy
    "SLA": "#FF0000",   # red
    "JFL": "#00FFFF",   # cyan
}

# Product type colours
product_colours = {
    "FSP": "#1f77b4",
    "Pedestal": "#ff7f0e",
    "Niche": "#2ca02c",
    "Others": "#d62728",
}

uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx", "xls"])

if uploaded_file is not None:
    try:
        # Read file and find header row
        df_raw = pd.read_excel(uploaded_file, header=None)
        header_row_idx = None
        for idx, row in df_raw.iterrows():
            if row.astype(str).str.contains("FILE_NO").any():
                header_row_idx = idx
                break

        if header_row_idx is None:
            st.error("Could not find header row containing 'FILE_NO'. Please check the file format.")
            st.stop()

        df = pd.read_excel(uploaded_file, header=header_row_idx)
        df.columns = df.columns.str.strip()

        required_cols = ["STATUS", "NETMAINPRODUCT", "CBDD_NAME", "BDD_NAME", "PRODUCT_CODE"]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            st.error(f"Missing columns: {missing}. Please check the file format.")
            st.stop()

        df["NETMAINPRODUCT"] = pd.to_numeric(df["NETMAINPRODUCT"], errors="coerce")
        df_confirmed = df[df["STATUS"].str.upper() == "CONFIRM"].copy()
        df_confirmed = df_confirmed[df_confirmed["NETMAINPRODUCT"].notna() & (df_confirmed["NETMAINPRODUCT"] != 0)]

        if df_confirmed.empty:
            st.warning("No sales (NETMAINPRODUCT > 0) found in confirmed rows.")
            st.stop()

        # Agency mapping
        agency_rename = {
            "FU GUI SERVICES": "FGY",
            "ZENBOX PTE LTD": "ZB",
            "APG ADVISORY PTE. LTD.": "APG",
            "SINGAPORE LIFESTYLE ASSOCIATES PTE LTD.": "SLA",
            "JF LIFE CONSULTANT PTE LTD": "JFL",
        }

        def get_agency(row):
            cbd = row.get("CBDD_NAME", "")
            if pd.notna(cbd) and str(cbd).strip() != "":
                raw = str(cbd).strip().upper()
            else:
                bdd = row.get("BDD_NAME", "")
                if pd.notna(bdd) and str(bdd).strip() != "":
                    raw = str(bdd).strip().upper()
                else:
                    return "Others"
            # Find longest matching key (case-insensitive)
            for key, value in agency_rename.items():
                if key in raw:
                    return value
            return raw  # return original if not in map

        df_confirmed["Agency"] = df_confirmed.apply(get_agency, axis=1)

        # Product type
        def get_product_type(code):
            if pd.isna(code):
                return "Others"
            code_str = str(code).strip().upper()
            if code_str == "P":
                return "FSP"
            elif code_str == "TABLET":
                return "Pedestal"
            elif code_str == "URN":
                return "Niche"
            else:
                return "Others"

        df_confirmed["Product_Type"] = df_confirmed["PRODUCT_CODE"].apply(get_product_type)

        total_sales = df_confirmed["NETMAINPRODUCT"].sum()

        # Agency sales aggregation
        agency_sales = df_confirmed.groupby("Agency")["NETMAINPRODUCT"].sum().reset_index()
        # Order agencies: custom order then alphabetical for others, put "Others" last
        custom_order = ["FGY", "ZB", "APG", "SLA", "JFL"]
        agency_sales["Order"] = agency_sales["Agency"].apply(
            lambda x: custom_order.index(x) if x in custom_order else 999
        )
        agency_sales = agency_sales.sort_values(["Order", "Agency"]).drop("Order", axis=1)

        # Product sales
        product_sales = df_confirmed.groupby("Product_Type")["NETMAINPRODUCT"].sum().reset_index()
        product_sales = product_sales.sort_values("NETMAINPRODUCT", ascending=False)

        # Agency-Product pivot
        agency_product = df_confirmed.groupby(["Agency", "Product_Type"])["NETMAINPRODUCT"].sum().reset_index()
        pivot = agency_product.pivot(index="Agency", columns="Product_Type", values="NETMAINPRODUCT").fillna(0)
        # Reorder rows according to agency order
        pivot = pivot.reindex(agency_sales["Agency"])

        # Metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Confirmed Sales", f"${total_sales:,.0f}")
        with col2:
            st.metric("Number of Agencies", len(agency_sales))
        with col3:
            st.metric("Number of Product Types", len(product_sales))

        # ---- Sales by Agency ----
        st.subheader("Sales by Agency")
        fig_agency = px.bar(
            agency_sales,
            x="Agency",
            y="NETMAINPRODUCT",
            title="Sales by Agency",
            labels={"NETMAINPRODUCT": "Sales ($)", "Agency": "Agency"},
            text_auto=True,
            color="Agency",
            color_discrete_map=agency_colours,
            category_orders={"Agency": agency_sales["Agency"].tolist()}
        )
        fig_agency.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_agency, use_container_width=True)
        with st.expander("View data table for Sales by Agency"):
            st.dataframe(agency_sales, use_container_width=True)

        # ---- Sales by Product Type (Pie) ----
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Sales by Product Type")
            fig_product = px.pie(
                product_sales,
                names="Product_Type",
                values="NETMAINPRODUCT",
                title="Product Mix",
                hole=0.3,
                color="Product_Type",
                color_discrete_map=product_colours
            )
            st.plotly_chart(fig_product, use_container_width=True)
            with st.expander("View data table for Product Mix"):
                st.dataframe(product_sales, use_container_width=True)

        # ---- Agency Breakdown by Product (Stacked Bar) ----
        with col2:
            st.subheader("Agency Breakdown by Product")
            # Prepare data for stacked bar (long format)
            pivot_reset = pivot.reset_index().melt(id_vars="Agency", var_name="Product_Type", value_name="Sales")
            fig_stack = px.bar(
                pivot_reset,
                x="Agency",
                y="Sales",
                color="Product_Type",
                title="Agency Product Breakdown",
                labels={"Sales": "Sales ($)", "Agency": "Agency"},
                barmode="stack",
                color_discrete_map=product_colours,
                category_orders={"Agency": agency_sales["Agency"].tolist()}
            )
            fig_stack.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_stack, use_container_width=True)
            with st.expander("View data table for Agency Product Breakdown"):
                # Show the pivot table
                st.dataframe(pivot, use_container_width=True)

        # ---- Raw Data ----
        with st.expander("Show Raw Data (Confirmed Sales)"):
            st.dataframe(
                df_confirmed[["FILE_NO", "ENTITY_NAME", "Agency", "Product_Type", "NETMAINPRODUCT", "CBDD_NAME", "BDD_NAME"]],
                use_container_width=True
            )

        # Download processed data
        csv = df_confirmed.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download processed data as CSV",
            data=csv,
            file_name="confirmed_sales.csv",
            mime="text/csv"
        )

    except Exception as e:
        st.error(f"An error occurred: {e}")

else:
    st.info("Please upload an Excel file to begin.")
