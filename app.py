import streamlit as st
import pandas as pd
from decimal import Decimal

st.set_page_config(page_title="Mizan", page_icon="balance", layout="wide")

st.title("Mizan - Balance Checker")
st.write("Developed by Jana Mahmoud - Mizanak Yezbot fi Sanya")

def to_dec(v):
    try:
        if pd.isna(v):
            return None
        s = str(v).replace(",", "").strip()
        if s == "" or s == "-":
            return None
        return Decimal(s)
    except:
        return None

menu = st.sidebar.radio("Menu", ["Home", "Check File"])

if menu == "Home":
    st.success("Welcome to Mizan - First Egyptian Trial Balance Checker")
    st.info("Go to Check File to upload Excel")
else:
    f = st.file_uploader("Upload Excel", type=["xlsx", "xls"])
    if f is not None:
        df = pd.read_excel(f)
        st.session_state["df"] = df
        st.dataframe(df.head(10), use_container_width=True)

    if "df" in st.session_state:
        df = st.session_state["df"]
        cols = ["--"] + list(df.columns)
        dcol = st.selectbox("Debit Column", cols, key="d")
        ccol = st.selectbox("Credit Column", cols, key="c")
        if st.button("Start Check", type="primary"):
            if dcol!= "--" and ccol!= "--":
                td = Decimal(0)
                tc = Decimal(0)
                for _, r in df.iterrows():
                    dv = to_dec(r[dcol])
                    cv = to_dec(r[ccol])
                    if dv is not None:
                        td += dv
                    if cv is not None:
                        tc += cv
                diff = abs(td - tc)
                st.metric("Total Debit", float(td))
                st.metric("Total Credit", float(tc))
                st.metric("Difference", float(diff))
                if diff > Decimal("0.01"):
                    st.error("Not Balanced")
                else:
                    st.success("Balanced - OK")
                    st.balloons()
