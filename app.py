import pandas as pd
import re
import streamlit as st
import io
import zipfile

# ฟังก์ชันล้างวงเล็บและเติมวงเล็บให้รหัสสาขา (เลข 5 หลัก)
def process_text_step1(text):
    if not isinstance(text, str):
        return text

    # 1. ลบวงเล็บที่ไม่ใช่รหัสสาขา
    def replace_non_id_parentheses(match):
        inner = match.group(1)
        if re.fullmatch(r'\d{5}', inner):  # รหัสสาขา
            return f'({inner})'
        else:
            return inner  # ลบวงเล็บ แต่คงข้อความไว้

    text = re.sub(r'\(([^)]+)\)', replace_non_id_parentheses, text)

    # 2. เติมวงเล็บให้เลข 5 หลักที่ไม่มีอยู่ใน ()
    existing_ids = set(re.findall(r'\((\d{5})\)', text))

    def add_parentheses(match):
        num = match.group(1)
        if num not in existing_ids:
            return f'({num})'
        return num

    text = re.sub(r'(?<!\()\b(\d{5})\b(?!\))', add_parentheses, text)

    # 3. ลบ space ซ้ำ
    text = re.sub(r'\s+', ' ', text).strip()

    return text

# ลบรูปแบบ `)(` ถ้ามี
def process_text_step2(text):
    if isinstance(text, str):
        return re.sub(r'\)\s*\(', ' ', text).strip()
    return text

# ฟังก์ชันประมวลผลหลัก
def process_data(df):
    try:
        df_cleaned = df.copy()

        # ล้างเฉพาะคอลัมน์ชื่อบริษัท
        df_cleaned[9] = df_cleaned[9].apply(process_text_step1)
        df_cleaned = df_cleaned.applymap(process_text_step2)

        # ตั้งชื่อคอลัมน์
        df_cleaned.columns = [
            'col0', 'col1', 'col2', 'col3', 'license_type', 'col5',
            'col6', 'col7', 'col8', 'company_name', 'col10', 'col11',
            'col12', 'subdistrict', 'district', 'province', 'postal_code', 'columshit'
        ]

        # ✅ เพิ่มขั้นตอนการเรียงแบบเดิม
        df_cleaned['group_name'] = df_cleaned['company_name'].apply(
            lambda x: re.sub(r'\(.*?\)', '', x).strip()
        )
        df_cleaned = df_cleaned.sort_values(by='group_name')
        df_cleaned = df_cleaned.drop(columns=['group_name'])

        # ตรวจจับรหัสสาขา
        df_cleaned['detected_id'] = df_cleaned['company_name'].str.extract(r'\((\d{5})\)')

        # แยกเป็น 2 กลุ่ม
        df_with_id = df_cleaned[df_cleaned['detected_id'].notnull()].copy()
        df_without_id = df_cleaned[df_cleaned['detected_id'].isnull()].copy()

        # ลบคอลัมน์ตรวจจับก่อน export
        df_with_id = df_with_id.drop(columns=['detected_id'])
        df_without_id = df_without_id.drop(columns=['detected_id'])

        # Export เป็นไฟล์ .txt
        output_with_id = io.StringIO()
        output_without_id = io.StringIO()
        df_with_id.to_csv(output_with_id, sep='|', index=False, header=False)
        df_without_id.to_csv(output_without_id, sep='|', index=False, header=False)

        # ใส่ ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("output_with_id.txt", output_with_id.getvalue())
            zip_file.writestr("output_without_id.txt", output_without_id.getvalue())

        zip_buffer.seek(0)
        return zip_buffer

    except Exception as e:
        st.error(f"เกิดข้อผิดพลาด: {e}")
        return None

# ส่วนแสดงผลของ Streamlit
st.title("📄 ระบบตรวจสอบข้อมูลการต่อใบอนุญาตสรรพสามิตอัตโนมัติ")

uploaded_file = st.file_uploader("📤 เลือกไฟล์ .txt เพื่อประมวลผล", type="txt")

if st.button("🚀 ประมวลผลไฟล์"):
    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file, delimiter='|', header=None, dtype=str)

            zip_file = process_data(df)

            if zip_file:
                st.success("✅ ประมวลผลสำเร็จ! ดาวน์โหลดได้ด้านล่าง")
                st.download_button(
                    label="📥 ดาวน์โหลดไฟล์ที่ประมวลผล (ZIP)",
                    data=zip_file,
                    file_name="processed_files.zip",
                    mime="application/zip"
                )
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์: {e}")
    else:
        st.warning("กรุณาอัปโหลดไฟล์ก่อนประมวลผล")
