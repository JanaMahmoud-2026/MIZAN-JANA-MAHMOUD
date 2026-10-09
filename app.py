import streamlit as st
import pandas as pd
from decimal import Decimal

st.set_page_config(page_title="Mizan - ميزان", page_icon="⚖️", layout="wide")
st.markdown("<h1 style='text-align:center'>⚖️ ميزان | Mizan</h1><p style='text-align:center'>فكرة وتطوير: جنى محمود - ميزانك يظبط في ثانية</p>", unsafe_allow_html=True)

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

st.sidebar.title("القائمة")
menu = st.sidebar.radio("اختاري", ["الرئيسية", "فحص الملف"])

if menu == "الرئيسية":
    st.success("مرحبا بك في مشروع ميزان")
    st.info("ادخلي على 'فحص الملف' وارفعي ملف Excel")
else:
    f = st.file_uploader("اختاري ملف Excel", type=["xlsx", "xls"])
    if f is not None:
        df = pd.read_excel(f)
        st.session_state["df"] = df
        st.dataframe(df.head(10), use_container_width=True)
    if "df" in st.session_state:
        df = st.session_state["df"]
        cols = ["-- اختاري --"] + list(df.columns)
        dcol = st.selectbox("عمود المدين", cols)
        ccol = st.selectbox("عمود الدائن", cols)
        if st.button("ابدأ الفحص 🔍", type="primary"):
            if not dcol.startswith("--") and not ccol.startswith("--"):
                td = sum([to_dec(x) or Decimal(0) for x in df[dcol]])
                tc = sum([to_dec(x) or Decimal(0) for x in df[ccol]])
                st.metric("اجمالي المدين", float(td))
                st.metric("اجمالي الدائن", float(tc))
                st.metric("الفرق", float(abs(td-tc)))
                if abs(td-tc) > Decimal("0.01"):
                    st.error("الميزان غير متوازن")
                else:
                    st.success("الميزان متوازن ✅")
                    st.balloons()
