import streamlit as st
import pandas as pd
from decimal import Decimal

st.set_page_config(page_title="Mizan", page_icon="balance", layout="wide")

st.title("Mizan - Balance Checker")
st.write("Developed by Jana Mahmoud - Mizanak Yezbot fi Sanya")
with st.expander("📖 How to use / طريقة الاستخدام - اضغط هنا"):
    tab_ar, tab_en = st.tabs(["🇪🇬 العربية", "🇺🇸 English"])
    with tab_ar:
        st.markdown("""
        **أهلاً بيك في ميزان - ميزانك يزبط في ثانية!**
        
        **1. جهز ملف الاكسيل:**
        - لازم يكون فيه عمود **مدين (Debit)** وعمود **دائن (Credit)**
        
        **2. ارفع الملف:**
        - دوس على زرار Upload واختار ملفك
        
        **3. شوف النتيجة:**
        - لو متوازن ✅ هيقولك الميزان مظبوط
        - لو مش متوازن ❌ هيطلعلك الفرق كام بالظبط
        """)
    with tab_en:
        st.markdown("""
        **Welcome to Mizan - Your Balance in a Second!**
        
        **1. Prepare your Excel:**
        - Must have **Debit** and **Credit** columns
        
        **2. Upload:**
        - Click Upload and choose your file
        
        **3. Get result:**
        - Balanced ✅: Correct!
        - Not Balanced ❌: Shows difference
        """)
        
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
