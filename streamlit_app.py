import streamlit as st
import pandas as pd
import plotly.express as px
import io

# Set page config
st.set_page_config(page_title="Sales Dashboard", layout="wide")

st.title("📊 Sales Dashboard - Confirmed Sales Analysis")

st.markdown("Upload an Excel file containing sales data to view dashboard.")

# File upload
uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx", "xls"])

if uploaded_file is not None:
    # Read the Excel file, handling metadata rows
    try:
        # Read all rows without header
        df_raw = pd.read_excel(uploaded_file, header=None)
        
        # Find the row containing "FILE_NO" (the header row)
        header_row_idx = None
        for idx, row in df_raw.iterrows():
            if row.astype(str).str.contains("FILE_NO").any():
                header_row_idx = idx
                break
        
        if header_row_idx is None:
            st.error("Could not find header row containing 'FILE_NO'. Please check the file format.")
            st.stop()
        
        # Read the file again, skipping rows before header and using that row as header
        df = pd.read_excel(uploaded_file, header=header_row_idx)
        
        # Clean column names (strip spaces)
        df.columns = df.columns.str.strip()
        
        # Ensure required columns exist
        required_cols = ["STATUS", "NETMAINPRODUCT", "CBDD_NAME", "BDD_NAME", "PRODUCT_CODE"]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            st.error(f"Missing columns: {missing}. Please check the file format.")
            st.stop()
        
        # Convert NETMAINPRODUCT to numeric, coerce errors to NaN
        df["NETMAINPRODUCT"] = pd.to_numeric(df["NETMAINPRODUCT"], errors="coerce")
        
        # Filter status = CONFIRM
        df_confirmed = df[df["STATUS"].str.upper() == "CONFIRM"].copy()
        
        if df_confirmed.empty:
            st.warning("No rows with STATUS = 'CONFIRM' found.")
            st.stop()
        
        # Drop rows where NETMAINPRODUCT is NaN or zero (non-sales)
        df_confirmed = df_confirmed[df_confirmed["NETMAINPRODUCT"].notna() & (df_confirmed["NETMAINPRODUCT"] != 0)]
        
        if df_confirmed.empty:
            st.warning("No sales (NETMAINPRODUCT > 0) found in confirmed rows.")
            st.stop()
        
        # Define agency classification
        def get_agency(row):
            cbd = row.get("CBDD_NAME", "")
            if pd.notna(cbd) and str(cbd).strip() != "":
                return str(cbd).strip()
            bdd = row.get("BDD_NAME", "")
            if pd.notna(bdd) and str(bdd).strip() != "":
                return str(bdd).strip()
            return "Others"
        
        df_confirmed["Agency"] = df_confirmed.apply(get_agency, axis=1)
        
        # Define product type classification
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
        
        # Total sales
        total_sales = df_confirmed["NETMAINPRODUCT"].sum()
        
        # Sales by Agency
        agency_sales = df_confirmed.groupby("Agency")["NETMAINPRODUCT"].sum().reset_index()
        agency_sales = agency_sales.sort_values("NETMAINPRODUCT", ascending=False)
        
        # Sales by Product
        product_sales = df_confirmed.groupby("Product_Type")["NETMAINPRODUCT"].sum().reset_index()
        product_sales = product_sales.sort_values("NETMAINPRODUCT", ascending=False)
        
        # Sales by Agency and Product (pivot)
        agency_product = df_confirmed.groupby(["Agency", "Product_Type"])["NETMAINPRODUCT"].sum().reset_index()
        pivot = agency_product.pivot(index="Agency", columns="Product_Type", values="NETMAINPRODUCT").fillna(0)
        
        # Display metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Confirmed Sales", f"${total_sales:,.0f}")
        with col2:
            st.metric("Number of Agencies", len(agency_sales))
        with col3:
            st.metric("Number of Product Types", len(product_sales))
        
        # Charts
        st.subheader("Sales by Agency")
        fig_agency = px.bar(
            agency_sales,
            x="Agency",
            y="NETMAINPRODUCT",
            title="Sales by Agency",
            labels={"NETMAINPRODUCT": "Sales ($)", "Agency": "Agency"},
            text_auto=True
        )
        fig_agency.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_agency, use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Sales by Product Type")
            fig_product = px.pie(
                product_sales,
                names="Product_Type",
                values="NETMAINPRODUCT",
                title="Product Mix",
                hole=0.3
            )
            st.plotly_chart(fig_product, use_container_width=True)
        
        with col2:
            st.subheader("Agency Breakdown by Product")
            # Stacked bar chart
            fig_stack = px.bar(
                pivot.reset_index(),
                x="Agency",
                y=pivot.columns,
                title="Agency Product Breakdown",
                labels={"value": "Sales ($)", "variable": "Product Type"},
                barmode="stack"
            )
            fig_stack.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_stack, use_container_width=True)
        
        # Show raw data table
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
