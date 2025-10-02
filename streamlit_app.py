import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="Finance_PBH Tools", layout="wide")

# ================================================================
# Simple Authentication
# ================================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("Finance_PBH Tools - Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username == "finance" and password == "finance123":
            st.session_state.authenticated = True
            st.success("Login successful!")
            st.rerun()   # <-- updated here
        else:
            st.error("Invalid username or password")

    st.stop()

# ================================================================
# Helpers
# ================================================================
def safe_numeric_idx(df, idx):
    return (
        pd.to_numeric(
            df.iloc[:, idx].astype(str).str.replace(",", "").str.strip(),
            errors="coerce"
        ).fillna(0)
        if idx < df.shape[1] else pd.Series([0] * len(df))
    )

def find_grand_total(df):
    for i, row in df.iterrows():
        row_str = " ".join([str(x).lower().strip() for x in row if pd.notna(x)])
        if "grand total" in row_str:
            return row
    return None

# ================================================================
# Sidebar
# ================================================================
st.sidebar.title("Finance_PBH Tools")

st.sidebar.markdown("### AX Report Extractor")
subcategory = st.sidebar.radio(
    "Select Report",
    [
        "TrialBalanceByCostCentre Report",
        "Trial Balance by Entity Report",
        "GL Journal Listing By Department Report"
    ]
)

# ================================================================
# TrialBalanceByCostCentre Report
# ================================================================
if subcategory == "TrialBalanceByCostCentre Report":
    st.header("Trial Balance By Cost Centre Report")

    tabs = st.tabs(["📥 File Extractor", "🧪 Audit Data Extractor", "📈 Analysis", "📊 Reporting"])

    # ------------------------------------------------
    # 📥 File Extractor
    # ------------------------------------------------
    with tabs[0]:
        uploaded_file = st.file_uploader("Upload TrialBalanceByCostCentre.csv", type=["csv"])

        if uploaded_file is not None:
            # --- Show raw preview
            uploaded_file.seek(0)
            df_preview = pd.read_csv(uploaded_file, header=None, nrows=20, encoding="latin1")
            df_preview.columns = [f"col_{i}" for i in range(len(df_preview.columns))]
            st.subheader("Raw File Preview (first 20 rows, column numbers)")
            st.dataframe(df_preview)

            # --- Extract report date
            uploaded_file.seek(0)
            df_raw = pd.read_csv(uploaded_file, header=None, encoding="latin1")
            st.session_state.df_raw_full = df_raw.copy()
            raw_date_text = str(df_raw.iloc[3, 13]) if pd.notna(df_raw.iloc[3, 13]) else ""
            match = re.search(r"\d{2}/\d{2}/\d{4}", raw_date_text)
            report_date = match.group(0) if match else ""
            date_end = pd.to_datetime(report_date, format="%d/%m/%Y", errors="coerce")

            # --- Load data with row 5 as header
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, skiprows=5, header=0, encoding="latin1")

            # --- Identify Department header rows
            dept_rows = df['A/C Type'].astype(str).str.contains("Department:", na=False)
            df.loc[dept_rows, 'Department'] = df['Account Code']
            df['Department'] = df['Department'].ffill()

            # --- Remove junk rows
            bad_strings = [
                "Department Total", "Grand Total", "No. of Record",
                "End of Report", "Date printed", "CRITERIA:", "CITERIA:"
            ]
            mask_bad = df.apply(
                lambda row: row.astype(str).str.contains('|'.join(bad_strings), case=False, na=False).any(),
                axis=1
            )
            df = df[~mask_bad]

            # --- Remove Department header rows completely
            df = df[~dept_rows]

            # --- Drop rows without Account Code
            df = df[df['Account Code'].notna() & (df['Account Code'].astype(str).str.strip() != "")]

            # --- Split Department
            dept_split = df['Department'].astype(str).str.split("-", n=1, expand=True)
            div_cd_full = dept_split[0].str.strip()
            dept_name = dept_split[1].str.strip()
            cost_centre_code = div_cd_full.str.extract(r'^(CC|HT|INS)', expand=False)
            dept_code = div_cd_full.str.replace(r'^(CC|HT|INS)', '', regex=True).str.strip()

            # --- Build clean dataset
            df_final = pd.DataFrame({
                "Account Type": df['A/C Type'],
                "Account Code": df['Account Code'],
                "Account Name": df['A/C Name'],
                "Cost Centre Code": cost_centre_code,
                "Department Code": dept_code,
                "Department Name": dept_name,
                "Date": date_end.strftime("%d/%m/%Y") if pd.notna(date_end) else "",
                "Opening Balance Debit": safe_numeric_idx(df, 12),
                "Opening Balance Credit": safe_numeric_idx(df, 14),
                "MTD Debit": safe_numeric_idx(df, 15),
                "MTD Credit": safe_numeric_idx(df, 16),
                "Closing Balance Debit": safe_numeric_idx(df, 17),
                "Closing Balance Credit": safe_numeric_idx(df, 19)
            })
            st.session_state.df_final = df_final.copy()

            # --- Show preview
            st.subheader("Clean Trial Balance Preview (first 50 rows)")
            st.dataframe(df_final.head(50), use_container_width=True)

            # --- Download
            csv = df_final.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="Download Clean CSV",
                data=csv,
                file_name="Clean_TrialBalanceByCostCentre.csv",
                mime="text/csv"
            )

    # ------------------------------------------------
    # 🧪 Audit Data Extractor
    # ------------------------------------------------
    with tabs[1]:
        if "df_final" not in st.session_state or st.session_state.df_final is None:
            st.warning("Please upload and extract data first in 📥 File Extractor.")
        else:
            clean_df = st.session_state.df_final
            raw_df = st.session_state.df_raw_full

            # Clean totals
            clean_totals = {
                "Opening Balance Debit": clean_df["Opening Balance Debit"].sum(),
                "Opening Balance Credit": clean_df["Opening Balance Credit"].sum(),
                "MTD Debit": clean_df["MTD Debit"].sum(),
                "MTD Credit": clean_df["MTD Credit"].sum(),
                "Closing Balance Debit": clean_df["Closing Balance Debit"].sum(),
                "Closing Balance Credit": clean_df["Closing Balance Credit"].sum()
            }

            # Raw grand total
            st.subheader("Raw File Ending (last 10 rows)")
            st.dataframe(raw_df.tail(10))

            grand_row = find_grand_total(raw_df)
            if grand_row is not None:
                raw_totals = {
                    "Opening Balance Debit": pd.to_numeric(str(grand_row[12]).replace(",", ""), errors="coerce"),
                    "Opening Balance Credit": pd.to_numeric(str(grand_row[14]).replace(",", ""), errors="coerce"),
                    "MTD Debit": pd.to_numeric(str(grand_row[15]).replace(",", ""), errors="coerce"),
                    "MTD Credit": pd.to_numeric(str(grand_row[16]).replace(",", ""), errors="coerce"),
                    "Closing Balance Debit": pd.to_numeric(str(grand_row[17]).replace(",", ""), errors="coerce"),
                    "Closing Balance Credit": pd.to_numeric(str(grand_row[19]).replace(",", ""), errors="coerce")
                }
            else:
                raw_totals = {k: None for k in clean_totals.keys()}

            audit_df = pd.DataFrame([
                {
                    "Metric": k,
                    "Clean Total": clean_totals[k],
                    "Raw Grand Total": raw_totals[k],
                    "Difference": (clean_totals[k] - raw_totals[k]) if raw_totals[k] is not None else None
                }
                for k in clean_totals.keys()
            ])

            st.subheader("Cross-check Clean vs Raw Grand Total")
            st.dataframe(audit_df, use_container_width=True)

    # ------------------------------------------------
    # 📈 Analysis
    # ------------------------------------------------
    with tabs[2]:
        st.info("Analysis features (P&L and Balance Sheet) will be added here.")

    # ------------------------------------------------
    # 📊 Reporting
    # ------------------------------------------------
    with tabs[3]:
        st.info("Reporting features (styled tables, export to PDF/Excel) will be added here.")

# ================================================================
# Trial Balance by Entity Report (placeholder)
# ================================================================
if subcategory == "Trial Balance by Entity Report":
    st.header("Trial Balance by Entity Report")
    tabs = st.tabs(["📥 File Extractor", "🧪 Audit Data Extractor", "📈 Analysis", "📊 Reporting"])
    for tab in tabs:
        with tab:
            st.info("This section will be developed later.")

# ================================================================
# GL Journal Listing By Department Report (placeholder)
# ================================================================
if subcategory == "GL Journal Listing By Department Report":
    st.header("GL Journal Listing By Department Report")
    tabs = st.tabs(["📥 File Extractor", "🧪 Audit Data Extractor", "📈 Analysis", "📊 Reporting"])
    for tab in tabs:
        with tab:
            st.info("This section will be developed later.")
