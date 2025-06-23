import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import io
import os
import re
from datetime import datetime
from pdf2image import convert_from_bytes
import cv2
import numpy as np

# 🔧 Manually set tesseract path if not added to system PATH
pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

# Set up directories
UPLOAD_FOLDER = "uploads"
LOG_FILE = "dataset.csv"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize dataset file if not present
if not os.path.exists(LOG_FILE):
    pd.DataFrame(columns=[
        "Driver ID", "Driver Name", "Amount", "Date", "Receipt Type", "Timestamp"
    ]).to_csv(LOG_FILE, index=False)

st.title("Receipt Upload and Logging System")

# Form
with st.form("receipt_form"):
    driver_id = st.text_input("Enter Driver ID (e.g., A12)")
    receipt_type = st.selectbox("Select Receipt Type", ["DR receipt", "AA conf"])
    date_input = st.date_input("Enter Date of Transaction")
    uploaded_file = st.file_uploader("Upload Receipt (Image or PDF)", type=["png", "jpg", "jpeg", "pdf"])
    submitted = st.form_submit_button("Upload and Process")

def clean_opay_amount_text(text):
    text = re.sub(r"[\u20a6N]", "", text)
    text = text.replace(",", "").replace(" ", "")
    return re.sub(r"[^\d.]", "", text)

def clean_access_tiny_amount_text(text):
    text = text.replace("‘", "").replace("’", "").replace("`", "")
    text = text.replace(",", "")
    text = text.replace("c0a", "000").replace("cOa", "000").replace("coa", "000").replace("co", "00").replace("oa", "00")
    text = text.replace("N", "").replace("n", "")
    text = text.replace("l", "1").replace("O", "0").replace("o", "0")
    text = re.sub(r"[^\d.]", "", text)
    return text

def clean_fidelity_amount_text(text):
    text = text.replace("‘", "").replace("’", "").replace("`", "")
    text = text.replace(",", "")
    text = text.replace("c0a", "000").replace("cOa", "000").replace("coa", "000").replace("co", "00").replace("oa", "00")
    text = text.replace("N", "").replace("n", "")
    text = text.replace("l", "1").replace("O", "0").replace("o", "0")
    text = re.sub(r"[^\d.]", "", text)
    return text

def extract_info_if_opay(text):
    if "ds pay transaction receipt" not in text.lower():
        return None

    amount_match = re.search(r"(?:[\u20a6N]\s?)?([\d,\.]+)", text)
    amount_raw = amount_match.group(1).replace(" ", "") if amount_match else "Unknown"
    amount_cleaned = clean_opay_amount_text(amount_raw)
    if amount_cleaned and amount_cleaned != "Unknown":
        try:
            amount_numeric = float(amount_cleaned.replace(",", ""))
            if amount_numeric >= 100000:
                amount_short = f"N{int(amount_numeric / 1000)}k"
            elif amount_numeric >= 10000:
                amount_short = f"N{int(amount_numeric / 1000)}k"
            elif amount_numeric >= 1000:
                amount_short = f"N{round(amount_numeric / 1000, 1)}k"
            elif amount_numeric >= 100:
                amount_short = f"N{int(amount_numeric / 100)}h"
            else:
                amount_short = f"N{int(amount_numeric)}"
            amount = f"N{amount_numeric:,.2f}"
        except:
            amount = amount_short = "Unknown"
    else:
        amount = amount_short = "Unknown"

    lines = text.splitlines()
    driver_name = "Unknown"
    for i, line in enumerate(lines):
        if "Sender Details" in line:
            same_line_match = re.search(r"Sender Details\s*(.+)", line)
            if same_line_match:
                name_candidate = same_line_match.group(1).strip()
                if len(name_candidate.split()) >= 2:
                    driver_name = name_candidate.title()
                    break
            if i + 1 < len(lines):
                next_line_candidate = lines[i + 1].strip()
                if len(next_line_candidate.split()) >= 2:
                    driver_name = next_line_candidate.title()
                    break
    return amount, amount_short, driver_name

def extract_info_if_access(text):
    if "access tiny" not in text.lower():
        return None

    amount_match = re.search(r"Transaction Amount\s*[\u20a6N‘’`]?([\w,\.]+)", text)
    amount_raw = amount_match.group(1).replace(" ", "") if amount_match else "Unknown"
    amount_cleaned = clean_access_tiny_amount_text(amount_raw)
    if amount_cleaned and amount_cleaned != "Unknown":
        try:
            amount_numeric = float(amount_cleaned.replace(",", ""))
            if amount_numeric >= 100000:
                amount_short = f"N{int(amount_numeric / 1000)}k"
            elif amount_numeric >= 10000:
                amount_short = f"N{int(amount_numeric / 1000)}k"
            elif amount_numeric >= 1000:
                amount_short = f"N{round(amount_numeric / 1000, 1)}k"
            elif amount_numeric >= 100:
                amount_short = f"N{int(amount_numeric / 100)}h"
            else:
                amount_short = f"N{int(amount_numeric)}"
            amount = f"N{amount_numeric:,.2f}"
        except:
            amount = amount_short = "Unknown"
    else:
        amount = amount_short = "Unknown"

    driver_name = "Unknown"
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "sender" in line.lower():
            name_candidate = re.sub(r"sender\s*", "", line, flags=re.I).strip()
            if name_candidate and "beneficiary" not in name_candidate.lower():
                driver_name = name_candidate.title()
                break
            elif i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and "beneficiary" not in next_line.lower():
                    driver_name = next_line.title()
                    break

    return amount, amount_short, driver_name

def extract_info_if_fidelity(text):
    if "fidelity" not in text.lower():
        return None

    amount_match = re.search(r"Transaction Amount\s*[\u20a6N‘’`]?([\w,\.]+)", text)
    amount_raw = amount_match.group(1).replace(" ", "") if amount_match else "Unknown"
    amount_cleaned = clean_fidelity_amount_text(amount_raw)
    if amount_cleaned and amount_cleaned != "Unknown":
        try:
            amount_numeric = float(amount_cleaned.replace(",", ""))
            if amount_numeric >= 100000:
                amount_short = f"N{int(amount_numeric / 1000)}k"
            elif amount_numeric >= 10000:
                amount_short = f"N{int(amount_numeric / 1000)}k"
            elif amount_numeric >= 1000:
                amount_short = f"N{round(amount_numeric / 1000, 1)}k"
            elif amount_numeric >= 100:
                amount_short = f"N{int(amount_numeric / 100)}h"
            else:
                amount_short = f"N{int(amount_numeric)}"
            amount = f"N{amount_numeric:,.2f}"
        except:
            amount = amount_short = "Unknown"
    else:
        amount = amount_short = "Unknown"

    driver_name = "Unknown"
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "sender" in line.lower():
            name_candidate = re.sub(r"sender\s*", "", line, flags=re.I).strip()
            if name_candidate and "beneficiary" not in name_candidate.lower():
                driver_name = name_candidate.title()
                break
            elif i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and "beneficiary" not in next_line.lower():
                    driver_name = next_line.title()
                    break

    return amount, amount_short, driver_name

if submitted and uploaded_file:
    original_filename = uploaded_file.name

    if uploaded_file.type == "application/pdf":
        images = convert_from_bytes(uploaded_file.read())
        image = images[0]
    else:
        image = Image.open(uploaded_file)

    image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    preprocessed_image = Image.fromarray(thresh)

    text = pytesseract.image_to_string(preprocessed_image)
    st.text_area("OCR Text", text, height=200)

    result = extract_info_if_opay(text)
    if not result:
        result = extract_info_if_access(text)
    if not result:
        result = extract_info_if_fidelity(text)

    if result:
        amount, amount_short, driver_name = result
    else:
        amount = amount_short = "Unknown"
        driver_name = "Unknown" if receipt_type == "DR receipt" else "-"

    parsed_date = datetime.strptime(str(date_input), "%Y-%m-%d")
    date_for_dataset = parsed_date.strftime("%d/%m/%Y")
    date_for_filename = parsed_date.strftime("%d.%m.%y")

    save_folder = os.path.join(UPLOAD_FOLDER, "DR_receipts" if receipt_type == "DR receipt" else "AA_conf")
    os.makedirs(save_folder, exist_ok=True)

    new_filename = f"{driver_id},{amount_short},{date_for_filename},{receipt_type}".replace(" ", "_") + os.path.splitext(original_filename)[1]
    save_path = os.path.join(save_folder, new_filename)

    if uploaded_file.type == "application/pdf":
        images[0].save(save_path)
    else:
        image.save(save_path)

    new_record = {
        "Driver ID": driver_id,
        "Driver Name": driver_name,
        "Amount": amount,
        "Date": date_for_dataset,
        "Receipt Type": receipt_type,
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    df = pd.read_csv(LOG_FILE)
    df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
    df.to_csv(LOG_FILE, index=False)

    st.success("Receipt uploaded and logged successfully!")
    st.code(new_filename, language="text")
    st.write("Extracted Info:")
    st.json(new_record)

st.markdown("---")
st.subheader("Upload History")
log_df = pd.read_csv(LOG_FILE)
st.dataframe(log_df.tail(10))
