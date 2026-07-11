import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

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

# Helper to format numbers for charts (e.g. 15.77m)
def format_big_number(value):
    if abs(value) >= 1e6:
        return f"{value/1e6:.2f}m"
    elif abs(value) >= 1e3:
        return f"{value/1e3:.2f}k"
    else:
        return f"{value:.2f}"

uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx", "xls"])

if uploaded_file is not None:
    try:
        # ---- Read file and locate header ----
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

        # ---- Agency mapping ----
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
            for key, value in agency_rename.items():
                if key in raw:
                    return value
            return raw

        df_confirmed["Agency"] = df_confirmed.apply(get_agency, axis=1)

        # ---- Product type ----
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

        # ---- Agency sales ----
        agency_sales = df_confirmed.groupby("Agency")["NETMAINPRODUCT"].sum().reset_index()
        custom_order = ["FGY", "ZB", "APG", "SLA", "JFL"]
        agency_sales["Order"] = agency_sales["Agency"].apply(
            lambda x: custom_order.index(x) if x in custom_order else 999
        )
        agency_sales = agency_sales.sort_values(["Order", "Agency"]).drop("Order", axis=1)

        # Create formatted text column for chart
        agency_sales["Display"] = agency_sales["NETMAINPRODUCT"].apply(format_big_number)

        # ---- Product sales ----
        product_sales = df_confirmed.groupby("Product_Type")["NETMAINPRODUCT"].sum().reset_index()
        product_sales = product_sales.sort_values("NETMAINPRODUCT", ascending=False)
        product_sales["Display"] = product_sales["NETMAINPRODUCT"].apply(format_big_number)

        # ---- Agency-Product pivot ----
        agency_product = df_confirmed.groupby(["Agency", "Product_Type"])["NETMAINPRODUCT"].sum().reset_index()
        pivot = agency_product.pivot(index="Agency", columns="Product_Type", values="NETMAINPRODUCT").fillna(0)
        pivot = pivot.reindex(agency_sales["Agency"])

        # ---- Metrics ----
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Confirmed Sales", f"${total_sales:,.2f}")
        with col2:
            st.metric("Number of Agencies", len(agency_sales))
        with col3:
            st.metric("Number of Product Types", len(product_sales))

        # ---- Chart: Sales by Agency ----
        st.subheader("Sales by Agency")
        fig_agency = px.bar(
            agency_sales,
            x="Agency",
            y="NETMAINPRODUCT",
            title="Sales by Agency",
            labels={"NETMAINPRODUCT": "Sales ($)", "Agency": "Agency"},
            text="Display",   # show formatted text on bars
            color="Agency",
            color_discrete_map=agency_colours,
            category_orders={"Agency": agency_sales["Agency"].tolist()}
        )
        fig_agency.update_traces(textposition="outside")
        fig_agency.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_agency, use_container_width=True)

        with st.expander("View data table for Sales by Agency"):
            # Format with $ and commas
            styled_agency = agency_sales[["Agency", "NETMAINPRODUCT"]].style.format(
                {"NETMAINPRODUCT": "${:,.2f}"}
            )
            st.dataframe(styled_agency, use_container_width=True)

        # ---- Charts: Product Mix & Agency Breakdown ----
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
                color_discrete_map=product_colours,
                hover_data={"Display": True}
            )
            fig_product.update_traces(
                textinfo="label+percent",
                hovertemplate="<b>%{label}</b><br>Sales: %{customdata[0]}<br>Percentage: %{percent}<extra></extra>",
                customdata=product_sales[["Display"]].values
            )
            st.plotly_chart(fig_product, use_container_width=True)

            with st.expander("View data table for Product Mix"):
                styled_product = product_sales[["Product_Type", "NETMAINPRODUCT"]].style.format(
                    {"NETMAINPRODUCT": "${:,.2f}"}
                )
                st.dataframe(styled_product, use_container_width=True)

        with col2:
            st.subheader("Agency Breakdown by Product")
            pivot_reset = pivot.reset_index().melt(id_vars="Agency", var_name="Product_Type", value_name="Sales")
            # Add formatted display column for hover
            pivot_reset["Display"] = pivot_reset["Sales"].apply(format_big_number)

            fig_stack = px.bar(
                pivot_reset,
                x="Agency",
                y="Sales",
                color="Product_Type",
                title="Agency Product Breakdown",
                labels={"Sales": "Sales ($)", "Agency": "Agency"},
                barmode="stack",
                color_discrete_map=product_colours,
                category_orders={"Agency": agency_sales["Agency"].tolist()},
                text="Display"
            )
            fig_stack.update_traces(textposition="inside")
            fig_stack.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_stack, use_container_width=True)

            with st.expander("View data table for Agency Product Breakdown"):
                # Show pivot with formatted numbers
                pivot_display = pivot.copy()
                for col in pivot_display.columns:
                    pivot_display[col] = pivot_display[col].apply(lambda x: f"${x:,.2f}")
                st.dataframe(pivot_display, use_container_width=True)

        # ---- Raw Data ----
        with st.expander("Show Raw Data (Confirmed Sales)"):
            st.dataframe(
                df_confirmed[["FILE_NO", "ENTITY_NAME", "Agency", "Product_Type", "NETMAINPRODUCT", "CBDD_NAME", "BDD_NAME"]],
                use_container_width=True
            )

        # ---- Download processed data ----
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
