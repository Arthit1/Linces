import io
import re
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# --- Google Analytics (GA4) ---
GA_MEASUREMENT_ID = "G-CY3RHVG4M4"
MASTER_CLOSED_BRANCH_FILE = Path("ข้อมูลร้านปิดดำเนินการ.xlsx")


ga_code = f"""
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{GA_MEASUREMENT_ID}');
</script>
"""

# Inject GA4 tracking code
components.html(ga_code, height=0, width=0)


# -------------------------------
# ฟังก์ชันล้างวงเล็บและเติมวงเล็บให้รหัสสาขา
# อนุญาตรหัสสาขา 4 หรือ 5 หลัก

def process_text_step1(text):
    if not isinstance(text, str):
        return text

    # 1. ลบวงเล็บที่ไม่ใช่รหัสสาขา
    def replace_non_id_parentheses(match):
        inner = match.group(1)
        if re.fullmatch(r"\d{4,5}", inner):
            return f"({inner})"
        return inner

    text = re.sub(r"\(([^)]+)\)", replace_non_id_parentheses, text)

    # 2. เติมวงเล็บให้เลข 5 หลักที่ไม่มีอยู่ใน ()
    existing_ids = set(re.findall(r"\((\d{5})\)", text))

    def add_parentheses(match):
        num = match.group(1)
        if num not in existing_ids:
            return f"({num})"
        return num

    text = re.sub(r"(?<!\()\b(\d{5})\b(?!\))", add_parentheses, text)

    # 3. ลบ space ซ้ำ
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ลบรูปแบบ `)(` ถ้ามี

def process_text_step2(text):
    if isinstance(text, str):
        return re.sub(r"\)\s*\(", " ", text).strip()
    return text


# normalize ชื่อสาขาเพื่อใช้ match กับ master ร้านปิด

def normalize_branch_name(text):
    if pd.isna(text):
        return ""

    text = str(text).strip().lower()

    # ลบเลขในวงเล็บ เช่น (17271)
    text = re.sub(r"\(\d{4,5}\)", "", text)

    # ลบวงเล็บทั่วไป
    text = re.sub(r"[()]", " ", text)

    # ลบคำรบกวน
    remove_words = [
        "บริษัท", "จำกัด", "มหาชน", "บมจ",
        "ซีพี ออลล์", "ซีพีออลล์",
        "เซเว่นอีเลฟเว่น", "เซเว่น อีเลฟเว่น",
        "เซ่เว่นอีเลฟเว่น", "7-eleven", "seveneleven"
    ]

    for word in remove_words:
        text = text.replace(word, " ")

    # เอาเฉพาะข้อความหลังคำว่า "สาขา" ถ้ามี
    match = re.search(r"สาขา(.+)", text)
    if match:
        text = match.group(1)

    # แทน . ด้วย space
    text = text.replace(".", " ")

    # ลบสัญลักษณ์
    text = re.sub(r"[-_/]", " ", text)

    # ลบ space ซ้ำ
    text = re.sub(r"\s+", " ", text).strip()

    return text


# โหลดไฟล์ร้านปิดดำเนินการจาก Master File

def load_closed_branch_names(excel_source):
    df_excel = pd.read_excel(excel_source, dtype=str)

    # ลบ 2 แถวแรกตามโครงสร้างไฟล์ master
    df_excel = df_excel.iloc[2:].reset_index(drop=True)

    branch_col = "ชื่อสาขา"
    if branch_col not in df_excel.columns:
        raise KeyError(f"ไม่พบคอลัมน์ '{branch_col}' ในไฟล์ Master")

    df_excel = df_excel[[branch_col]].copy()
    df_excel.columns = ["closed_branch_name"]

    df_excel["closed_branch_name"] = (
        df_excel["closed_branch_name"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df_excel = df_excel[df_excel["closed_branch_name"] != ""]
    df_excel["branch_name_key"] = df_excel["closed_branch_name"].apply(normalize_branch_name)

    closed_branch_set = set(df_excel["branch_name_key"].dropna().unique())
    return df_excel, closed_branch_set, branch_col


# ฟังก์ชันประมวลผลหลัก

def process_data(df, closed_branch_set=None):
    try:
        df_cleaned = df.copy()

        # ล้างเฉพาะคอลัมน์ชื่อบริษัท
        df_cleaned[9] = df_cleaned[9].apply(process_text_step1)
        df_cleaned = df_cleaned.applymap(process_text_step2)

        # ตั้งชื่อคอลัมน์
        df_cleaned.columns = [
            "col0", "col1", "col2", "col3", "license_type", "col5",
            "col6", "col7", "col8", "company_name", "col10", "col11",
            "col12", "subdistrict", "district", "province", "postal_code", "columshit"
        ]

        # เรียงข้อมูล
        df_cleaned["group_name"] = df_cleaned["company_name"].apply(
            lambda x: re.sub(r"\(.*?\)", "", str(x)).strip()
        )
        df_cleaned = df_cleaned.sort_values(by="group_name")
        df_cleaned = df_cleaned.drop(columns=["group_name"])

        # ตรวจจับรหัสสาขา
        df_cleaned["detected_id"] = df_cleaned["company_name"].str.extract(r"\((\d{4,5})\)")

        # แยกเป็น 2 กลุ่ม
        df_with_id = df_cleaned[df_cleaned["detected_id"].notnull()].copy()
        df_without_id = df_cleaned[df_cleaned["detected_id"].isnull()].copy()

        df_with_id = df_with_id.drop(columns=["detected_id"])

        matched_closed = pd.DataFrame()
        not_matched_closed = pd.DataFrame()

        if closed_branch_set is not None:
            df_without_id["branch_name_key"] = df_without_id["company_name"].apply(normalize_branch_name)
            df_without_id["matched_closed_branch"] = df_without_id["branch_name_key"].isin(closed_branch_set)

            matched_closed = df_without_id[df_without_id["matched_closed_branch"]].copy()
            not_matched_closed = df_without_id[~df_without_id["matched_closed_branch"]].copy()

            matched_closed = matched_closed.drop(columns=["detected_id", "branch_name_key", "matched_closed_branch"])
            not_matched_closed = not_matched_closed.drop(columns=["detected_id", "branch_name_key", "matched_closed_branch"])
        else:
            not_matched_closed = df_without_id.drop(columns=["detected_id"])

        # Export เป็นไฟล์ .txt
        output_with_id = io.StringIO()
        output_without_id = io.StringIO()
        output_matched_closed = io.StringIO()

        df_with_id.to_csv(output_with_id, sep="|", index=False, header=False)
        not_matched_closed.to_csv(output_without_id, sep="|", index=False, header=False)

        if closed_branch_set is not None and not matched_closed.empty:
            matched_closed.to_csv(output_matched_closed, sep="|", index=False, header=False)

        # ใส่ ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("output_with_id.txt", output_with_id.getvalue())
            zip_file.writestr("output_without_id.txt", output_without_id.getvalue())
            if closed_branch_set is not None:
                zip_file.writestr("output_without_id_matched_closed.txt", output_matched_closed.getvalue())

        zip_buffer.seek(0)

        summary = {
            "with_id_count": len(df_with_id),
            "without_id_count": len(not_matched_closed),
            "matched_closed_count": len(matched_closed),
        }

        return zip_buffer, summary

    except Exception as e:
        st.error(f"เกิดข้อผิดพลาด: {e}")
        return None, None


# -------------------------------
# ส่วนแสดงผลของ Streamlit
st.title("📄 ระบบตรวจสอบข้อมูลการต่อใบอนุญาตสรรพสามิตอัตโนมัติ \nUpdate 23-3-2569")


if MASTER_CLOSED_BRANCH_FILE.exists():
    st.caption(f"ใช้ Master File ร้านปิด: {MASTER_CLOSED_BRANCH_FILE.name}")
else:
    st.caption("ยังไม่พบ Master File ร้านปิด ระบบจะทำงานโดยไม่ตรวจสอบร้านปิด")

uploaded_file = st.file_uploader("📤 เลือกไฟล์ .txt เพื่อประมวลผล", type="txt")

if st.button("🚀 ประมวลผลไฟล์"):
    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file, delimiter="|", header=None, dtype=str)

            closed_branch_set = None
            detected_excel_col = None

            if MASTER_CLOSED_BRANCH_FILE.exists():
                _, closed_branch_set, detected_excel_col = load_closed_branch_names(MASTER_CLOSED_BRANCH_FILE)
            else:
                st.warning("ไม่พบไฟล์ Master ร้านปิดดำเนินการ ระบบจะประมวลผลโดยไม่ตรวจสอบร้านปิด")

            zip_file, summary = process_data(df, closed_branch_set)

            if zip_file:
                st.success("✅ ประมวลผลสำเร็จ! ดาวน์โหลดได้ด้านล่าง")

                if closed_branch_set is not None:
                    st.info(
                        f"""ผลการตรวจสอบร้านปิดแล้ว:
- ไฟล์ Master ที่ใช้: {MASTER_CLOSED_BRANCH_FILE.name}
- คอลัมน์ที่ใช้ Match: {detected_excel_col}
- จำนวนรายการที่มี ID: {summary['with_id_count']}
- จำนวนรายการไม่มี ID และไม่เจอในร้านปิดแล้ว: {summary['without_id_count']}
- จำนวนรายการไม่มี ID แต่เจอในร้านปิดแล้ว: {summary['matched_closed_count']}
"""
                    )
                else:
                    st.info(
                        f"""สรุปผล:
- จำนวนรายการที่มี ID: {summary['with_id_count']}
- จำนวนรายการไม่มี ID: {summary['without_id_count']}
"""
                    )

                st.download_button(
                    label="📥 ดาวน์โหลดไฟล์ที่ประมวลผล (ZIP)",
                    data=zip_file,
                    file_name="processed_files.zip",
                    mime="application/zip",
                )
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์: {e}")
    else:
        st.warning("กรุณาอัปโหลดไฟล์ก่อนประมวลผล")
