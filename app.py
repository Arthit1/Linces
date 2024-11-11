import pandas as pd
import re
import streamlit as st
import io
import zipfile

# Function to process text and clean data initially
def process_text_step1(text):
    if isinstance(text, str):
        matches = list(re.finditer(r'\(([^)]+)\)', text))
        words_in_parentheses = [(match.start(), match.end(), match.group(1)) for match in matches]
        cleaned_text = re.sub(r'\(.*?\)', '', text)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        result_text = cleaned_text
        for start, end, word in words_in_parentheses[:-1]:
            result_text = result_text[:start] + word + ' ' + result_text[start:]
        if words_in_parentheses:
            last_word = words_in_parentheses[-1][2]
            result_text += f' ({last_word})'
        return result_text.strip()
    return text

# Function to remove `)(` specifically
def process_text_step2(text):
    if isinstance(text, str):
        return re.sub(r'\)\s*\(', ' ', text).strip()
    return text

# Function to process the data and prepare for download
def process_data(df):
    try:
        # Step 1: Clean the data
        df_cleaned = df.applymap(process_text_step1)
        df_step2 = df_cleaned.applymap(process_text_step2)

        # Define column names based on the structure
        df_step2.columns = [
            'col0', 'col1', 'col2', 'col3', 'license_type', 'col5', 
            'col6', 'col7', 'col8', 'company_name', 'col10', 'col11', 
            'col12', 'subdistrict', 'district', 'province', 'postal_code', 'columshit'
        ]

        # Create a new column for grouping by cleaning the company name
        df_step2['group_name'] = df_step2['company_name'].apply(lambda x: re.sub(r'\(.*?\)', '', x).strip())

        # Sort data by `group_name`
        sorted_data = df_step2.sort_values(by='group_name')

        # Drop the 'group_name' helper column after sorting
        sorted_data = sorted_data.drop(columns=['group_name'])

        # Detect store IDs
        sorted_data['detected_id'] = sorted_data['company_name'].str.extract(r'\((\d+)\)')
        df_with_id = sorted_data[sorted_data['detected_id'].notnull()]
        df_without_id = sorted_data[sorted_data['detected_id'].isnull()]

        # Create in-memory files for both outputs
        output_with_id = io.StringIO()
        output_without_id = io.StringIO()
        df_with_id.to_csv(output_with_id, sep='|', index=False, header=False)
        df_without_id.to_csv(output_without_id, sep='|', index=False, header=False)

        # Prepare a ZIP file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            # Add the two files to the ZIP archive
            zip_file.writestr("output_with_id.txt", output_with_id.getvalue())
            zip_file.writestr("output_without_id.txt", output_without_id.getvalue())
        
        zip_buffer.seek(0)  # Reset buffer position to the start

        return zip_buffer

    except Exception as e:
        st.error(f"An error occurred: {e}")
        return None

# Streamlit app setup
st.title("Data Processing Application")

# File uploader for input file
uploaded_file = st.file_uploader("Choose a .txt file", type="txt")

# Process data when button is clicked
if st.button("Process File"):
    if uploaded_file:
        # Read file into a DataFrame
        df = pd.read_csv(uploaded_file, delimiter='|', header=None, dtype=str)
        
        # Run data processing function
        zip_file = process_data(df)
        
        # Provide a download button if processing was successful
        if zip_file:
            st.download_button(
                label="Download Processed Files (ZIP)",
                data=zip_file,
                file_name="processed_files.zip",
                mime="application/zip"
            )
    else:
        st.warning("Please upload an input file.")
