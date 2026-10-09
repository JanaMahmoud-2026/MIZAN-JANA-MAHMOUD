import io
import math
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Dict, List, Tuple, Optional, Any

import pandas as pd
import streamlit as st

# ReportLab Imports for PDF Generation
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

# Arabic text reshape for PDF rendering
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_ARABIC_SUPPORT = True
except ImportError:
    HAS_ARABIC_SUPPORT = False

# ==========================================
# Application Configuration & Branding
# ==========================================
APP_TITLE = "Mizan | ميزان"
APP_SUBTITLE = "نظام الذكاء المحاسبي لاكتشاف الأخطاء وتدقيق القوائم المالية"
FOUNDER_NAME = "جنى محمود"
SLOGAN = "ميزانك يظبط في ثانية ⚖️"

st.set_page_config(
    page_title=f"{APP_TITLE} - {FOUNDER_NAME}",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (RTL and Modern UI)
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
    
    html, body, [class*="css"], div, p, span, h1, h2, h3, h4, button, input {{
        font-family: 'Cairo', sans-serif !important;
        direction: rtl;
        text-align: right;
    }}
    
    .stApp {{
        background-color: #f8fafc;
    }}
    
    .main-header {{
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #ffffff;
        padding: 2.5rem 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.25);
        border: 1px solid #334155;
    }}
    
    .main-header h1 {{
        color: #38bdf8 !important;
        font-weight: 800;
        margin-bottom: 0.5rem;
    }}
    
    .main-header p {{
        color: #94a3b8;
        font-size: 1.1rem;
        margin: 0;
    }}
    
    .metric-card {{
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.25rem;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }}
    
    .metric-card .value {{
        font-size: 1.8rem;
        font-weight: 700;
        color: #0f172a;
    }}
    
    .metric-card .label {{
        font-size: 0.9rem;
        color: #64748b;
    }}

    .stButton>button {{
        border-radius: 8px;
        font-weight: 600;
    }}
    </style>
""", unsafe_allow_shortcut=True)

# ==========================================
# Core Accounting Logic Functions
# ==========================================

def safe_to_decimal(val: Any) -> Optional[Decimal]:
    """Safely convert any scalar input to Decimal for accurate calculations."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        if math.isnan(val) or math.isinf(val):
            return None
        return Decimal(str(val))
    if isinstance(val, Decimal):
        return val
    
    clean_str = str(val).strip().replace(',', '')
    if clean_str == '' or clean_str.lower() in ['none', 'nan', 'null', '-']:
        return None
    try:
        return Decimal(clean_str)
    except (InvalidOperation, ValueError):
        return None

def check_debit_credit_balance(
    df: pd.DataFrame, 
    debit_col: str, 
    credit_col: str, 
    tolerance: float = 0.01
) -> Dict[str, Any]:
    """Verify if total debits match total credits."""
    total_debit = Decimal('0.00')
    total_credit = Decimal('0.00')
    
    for _, row in df.iterrows():
        d = safe_to_decimal(row.get(debit_col))
        c = safe_to_decimal(row.get(credit_col))
        if d is not None:
            total_debit += d
        if c is not None:
            total_credit += c
            
    diff = abs(total_debit - total_credit)
    is_balanced = diff <= Decimal(str(tolerance))
    
    return {
        "total_debit": float(total_debit),
        "total_credit": float(total_credit),
        "difference": float(diff),
        "is_balanced": is_balanced
    }

def detect_missing_values(
    df: pd.DataFrame, 
    debit_col: Optional[str], 
    credit_col: Optional[str]
) -> List[Dict[str, Any]]:
    """Detect rows where both debit and credit are blank or invalid."""
    issues = []
    if not debit_col or not credit_col:
        return issues
        
    for idx, row in df.iterrows():
        d = safe_to_decimal(row.get(debit_col))
        c = safe_to_decimal(row.get(credit_col))
        
        # Row has no financial value entered in both debit and credit
        if d is None and c is None:
            issues.append({
                "row_index": idx,
                "excel_row": idx + 2,
                "column": f"{debit_col} / {credit_col}",
                "original_value": "فارغ / غير محدد",
                "issue_type": "قيمة مفقودة",
                "description": "لا توجد قيمة مسجلة في كل من المدين والدائن لهذا القيد.",
                "suggested_value": None,
                "severity": "عالي",
                "auto_correctable": False
            })
    return issues

def validate_vat(
    df: pd.DataFrame,
    amount_col: str,
    vat_col: str,
    vat_rate: float = 0.14,
    tolerance: float = 0.05
) -> List[Dict[str, Any]]:
    """Validate VAT calculation based on base amount and standard rate (Default 14%)."""
    issues = []
    rate_dec = Decimal(str(vat_rate))
    tol_dec = Decimal(str(tolerance))
    
    for idx, row in df.iterrows():
        base_amt = safe_to_decimal(row.get(amount_col))
        recorded_vat = safe_to_decimal(row.get(vat_col))
        
        if base_amt is not None and recorded_vat is not None:
            expected_vat = (base_amt * rate_dec).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            diff = abs(recorded_vat - expected_vat)
            
            if diff > tol_dec:
                issues.append({
                    "row_index": idx,
                    "excel_row": idx + 2,
                    "column": vat_col,
                    "original_value": str(recorded_vat),
                    "issue_type": "خطأ ضريبة القيمة المضافة",
                    "description": f"الضريبة المسجلة ({recorded_vat}) لا تطابق 14% من المبلغ ({expected_vat}).",
                    "suggested_value": float(expected_vat),
                    "severity": "متوسط",
                    "auto_correctable": True
                })
    return issues

def detect_duplicate_entries(
    df: pd.DataFrame, 
    check_cols: List[str]
) -> List[Dict[str, Any]]:
    """Identify potential duplicate transaction records."""
    issues = []
    valid_cols = [c for c in check_cols if c in df.columns]
    if not valid_cols:
        return issues
        
    duplicates = df[df.duplicated(subset=valid_cols, keep=False)]
    for idx in duplicates.index:
        issues.append({
            "row_index": idx,
            "excel_row": idx + 2,
            "column": "صف كامل",
            "original_value": "مكرر",
            "issue_type": "قيد مكرر محتمل",
            "description": "يوجد تكرار متطابق لهذه العملية في البيانات الحالية.",
            "suggested_value": None,
            "severity": "منخفض",
            "auto_correctable": False
        })
    return issues

def detect_invalid_values(
    df: pd.DataFrame, 
    numeric_cols: List[str]
) -> List[Dict[str, Any]]:
    """Detect negative or non-numeric entries in financial columns."""
    issues = []
    for col in numeric_cols:
        if col not in df.columns:
            continue
        for idx, row in df.iterrows():
            val = row.get(col)
            if pd.isna(val) or val == "" or val is None:
                continue
            
            dec_val = safe_to_decimal(val)
            if dec_val is None:
                issues.append({
                    "row_index": idx,
                    "excel_row": idx + 2,
                    "column": col,
                    "original_value": str(val),
                    "issue_type": "قيمة غير رقمية",
                    "description": f"الخلايا تحتوي على نص غير قابل للحساب في عمود رقمي.",
                    "suggested_value": 0.0,
                    "severity": "عالي",
                    "auto_correctable": True
                })
            elif dec_val < Decimal('0.00'):
                issues.append({
                    "row_index": idx,
                    "excel_row": idx + 2,
                    "column": col,
                    "original_value": str(dec_val),
                    "issue_type": "قيمة سالبة غير متوقعة",
                    "description": "تم تسجيل قيمة سالبة في عمود يحبذ أن تكون قيمه موجبة.",
                    "suggested_value": float(abs(dec_val)),
                    "severity": "متوسط",
                    "auto_correctable": True
                })
    return issues

# ==========================================
# Helper: PDF Generation
# ==========================================
def format_arabic_text(text: str) -> str:
    """Prepare Arabic string for PDF layout engine."""
    if not HAS_ARABIC_SUPPORT or not text:
        return str(text)
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)

def generate_pdf_report(
    filename: str,
    total_rows: int,
    balance_info: Dict[str, Any],
    issues: List[Dict[str, Any]],
    accepted_corrections: Dict[int, Dict[str, Any]]
) -> bytes:
    """Build a professional Arabic PDF Audit Summary Report."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    # Custom Arabic PDF styles
    title_style = ParagraphStyle(
        'ArabicTitle',
        parent=styles['Heading1'],
        alignment=TA_CENTER,
        fontSize=18,
        spaceAfter=15
    )
    normal_style = ParagraphStyle(
        'ArabicNormal',
        parent=styles['Normal'],
        alignment=TA_RIGHT,
        fontSize=10,
        spaceAfter=6
    )

    # Header
    story.append(Paragraph(format_arabic_text(f"تقرير التدقيق المحاسبي - مشروع {APP_TITLE}"), title_style))
    story.append(Paragraph(format_arabic_text(f"صاحبة المشروع / المهندسة: {FOUNDER_NAME}"), normal_style))
    story.append(Paragraph(format_arabic_text(f"اسم الملف المفحوص: {filename}"), normal_style))
    story.append(Paragraph(format_arabic_text(f"تاريخ الفحص: {datetime.now().strftime('%Y-%m-%d %H:%M')}"), normal_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f172a"), spaceAfter=15))

    # Summary Table
    summary_data = [
        [format_arabic_text("القيمة"), format_arabic_text("المؤشر")],
        [str(total_rows), format_arabic_text("إجمالي القيود المفحوصة")],
        [f"{balance_info.get('total_debit', 0):,.2f}", format_arabic_text("إجمالي المدين")],
        [f"{balance_info.get('total_credit', 0):,.2f}", format_arabic_text("إجمالي الدائن")],
        [f"{balance_info.get('difference', 0):,.2f}", format_arabic_text("الفارق (الفرق)")],
        [str(len(issues)), format_arabic_text("عدد الملاحظات المكتشفة")],
        [str(len(accepted_corrections)), format_arabic_text("التصحيحات المعتمدة")]
    ]
    
    t = Table(summary_data, colWidths=[200, 250])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 20))

    # Disclaimer
    disclaimer = "تنبيه هام: هذا التقرير تم توليده تلقائياً عبر نظام ميزان لاكتشاف الأخطاء الشائعة، ولا يعتبر شهادة تدقيق محاسبي رسمي معتمدة قانونياً."
    story.append(Paragraph(format_arabic_text(disclaimer), normal_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ==========================================
# Streamlit Interface Logic
# ==========================================

def main():
    # Sidebar Navigation
    st.sidebar.image("https://img.icons8.com/isometric/100/scales.png", width=70)
    st.sidebar.title(f"{APP_TITLE}")
    st.sidebar.caption(f"تطوير: **{FOUNDER_NAME}**")
    st.sidebar.markdown(f"*{SLOGAN}*")
    st.sidebar.divider()

    menu = st.sidebar.radio(
        "القائمة الرئيسية:",
        ["الصفحة الرئيسية", "رفع وفحص الملفات", "مراجعة التصحيحات", "تحميل التقارير", "عن المشروع"]
    )

    # Initialize Session States
    if 'uploaded_df' not in st.session_state:
        st.session_state.uploaded_df = None
    if 'filename' not in st.session_state:
        st.session_state.filename = ""
    if 'issues' not in st.session_state:
        st.session_state.issues = []
    if 'accepted_corrections' not in st.session_state:
        st.session_state.accepted_corrections = {}
    if 'balance_info' not in st.session_state:
        st.session_state.balance_info = {}

    # ----------------------------------------------------
    # Page 1: الصفحة الرئيسية
    # ----------------------------------------------------
    if menu == "الصفحة الرئيسية":
        st.markdown(f"""
            <div class="main-header">
                <h1>مشروع {APP_TITLE}</h1>
                <p>{APP_SUBTITLE}</p>
                <p style="font-weight: bold; color: #38bdf8; margin-top: 10px;">فكرة وتطوير: {FOUNDER_NAME}</p>
            </div>
        """, unsafe_allow_shortcut=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("""
                <div class="metric-card">
                    <div class="value">⚡ سريع ودقيق</div>
                    <div class="label">فحص التوازن المالي وضريبة القيمة المضافة في ثوانٍ</div>
                </div>
            """, unsafe_allow_shortcut=True)
        with col2:
            st.markdown("""
                <div class="metric-card">
                    <div class="value">🔒 آمن 100%</div>
                    <div class="label">معالجة محلية بالكامل للبيانات دون مشاركة خارج الجهاز</div>
                </div>
            """, unsafe_allow_shortcut=True)
        with col3:
            st.markdown("""
                <div class="metric-card">
                    <div class="value">📊 تقارير سريعة</div>
                    <div class="label">تصدير ملخصات PDF وملفات Excel المعدلة بسهولة</div>
                </div>
            """, unsafe_allow_shortcut=True)

        st.subheader("💡 تجربة سريعة لنظام ميزان")
        st.write("يمكنك البدء فوراً بتحميل دفتر تجريبي جاهز يضم أخطاء محاسبية مدمجة لاختبار النظام:")
        
        if st.button("🚀 تحميل بيانات تجريبية وفحصها الآن", type="primary"):
            demo_data = {
                "التاريخ": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-03", "2026-01-04"],
                "اسم الحساب": ["المبيعات", "المشتريات", "الكهرباء", "الكهرباء", "الأجور"],
                "البيان": ["فاتورة مبيعات", "مشتريات بضاعة", "سداد فاتورة", "سداد فاتورة", "مرتبات"],
                "مدين": [0.0, 5000.0, 400.0, 400.0, -1500.0],
                "دائن": [10000.0, 0.0, 0.0, 0.0, 0.0],
                "المبلغ الخاضع": [10000.0, 5000.0, 0.0, 0.0, 0.0],
                "الضريبة المسجلة": [1200.0, 700.0, 0.0, 0.0, 0.0]  # Note: 1200 is wrong, 14% of 10000 is 1400
            }
            st.session_state.uploaded_df = pd.DataFrame(demo_data)
            st.session_state.filename = "demo_accounting_ledger.xlsx"
            st.success("تم تحميل الملف التجريبي بنجاح! انتقل إلى تبويب 'رفع وفحص الملفات' لإكمال عملية الفحص.")

    # ----------------------------------------------------
    # Page 2: رفع وفحص الملفات
    # ----------------------------------------------------
    elif menu == "رفع وفحص الملفات":
        st.title("🔍 رفع وفحص ملفات Excel")
        
        file_input = st.file_uploader("اختر ملف Excel محاسبي (.xlsx, .xls)", type=["xlsx", "xls"])
        
        if file_input is not None:
            try:
                xl = pd.ExcelFile(file_input)
                sheet = st.selectbox("اختر الورقة (Sheet):", xl.sheet_names)
                df = pd.read_excel(file_input, sheet_name=sheet)
                st.session_state.uploaded_df = df
                st.session_state.filename = file_input.name
            except Exception as e:
                st.error(f"حدث خطأ أثناء قراءة الملف: {e}")

        if st.session_state.uploaded_df is not None:
            df = st.session_state.uploaded_df
            st.subheader("📋 معاينة البيانات")
            st.dataframe(df.head(10), use_container_width=True)

            st.divider()
            st.subheader("🎯 تعيين الأعمدة (Mapping)")
            
            cols = ["-- غير محدد --"] + list(df.columns)
            
            c1, c2, c3 = st.columns(3)
            with c1:
                debit_c = st.selectbox("عمود المدين (Debit):", cols, index=1 if len(cols)>1 else 0)
                amount_c = st.selectbox("عمود المبلغ الخاضع للضريبة:", cols, index=0)
            with c2:
                credit_c = st.selectbox("عمود الدائن (Credit):", cols, index=2 if len(cols)>2 else 0)
                vat_c = st.selectbox("عمود ضريبة القيمة المضافة:", cols, index=0)
            with c3:
                desc_c = st.selectbox("عمود البيان / الوصف:", cols, index=0)
                account_c = st.selectbox("عمود اسم الحساب:", cols, index=0)

            if st.button("⚡ بدء الفحص المحاسبي الشامل", type="primary"):
                issues = []
                
                # Convert string dropdowns to actual column names or None
                d_col = debit_c if debit_c != "-- غير محدد --" else None
                c_col = credit_c if credit_c != "-- غير محدد --" else None
                a_col = amount_c if amount_c != "-- غير محدد --" else None
                v_col = vat_c if vat_c != "-- غير محدد --" else None

                # Rule A: Debit/Credit Balance
                if d_col and c_col:
                    bal = check_debit_credit_balance(df, d_col, c_col)
                    st.session_state.balance_info = bal
                else:
                    st.session_state.balance_info = {}

                # Rule B: Missing Values
                issues.extend(detect_missing_values(df, d_col, c_col))

                # Rule C: VAT Validation
                if a_col and v_col:
                    issues.extend(validate_vat(df, a_col, v_col))

                # Rule D: Duplicate Detection
                check_cols = [col for col in [account_c, desc_c, d_col, c_col] if col and col != "-- غير محدد --"]
                if check_cols:
                    issues.extend(detect_duplicate_entries(df, check_cols))

                # Rule E: Invalid Numbers / Negative check
                num_cols = [col for col in [d_col, c_col] if col]
                if num_cols:
                    issues.extend(detect_invalid_values(df, num_cols))

                st.session_state.issues = issues
                st.session_state.accepted_corrections = {}
                st.success(f"تم الانتهاء من الفحص! تم إيجاد {len(issues)} ملاحظة/خطأ.")

    # ----------------------------------------------------
    # Page 3: مراجعة التصحيحات
    # ----------------------------------------------------
    elif menu == "مراجعة التصحيحات":
        st.title("🛠️ مراجعة وتصحيح الأخطاء")

        issues = st.session_state.get('issues', [])
        if not issues:
            st.info("لا توجد أخطاء مكتشفة حالياً أو لم يتم تشغيل الفحص بعد.")
        else:
            st.write(f"إجمالي الملاحظات المكتشفة: **{len(issues)}**")
            
            for idx, issue in enumerate(issues):
                with st.expander(f"تنبيه الصف {issue['excel_row']} - {issue['issue_type']} (مستوى الخطورة: {issue['severity']})", expanded=True):
          
