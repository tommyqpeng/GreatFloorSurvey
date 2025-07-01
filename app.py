import streamlit as st
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
import tempfile
import os
import json
from datetime import datetime
import uuid

# --- Config ---
GOOGLE_SHEET_NAME = st.secrets["google_sheet_name"]
DRIVE_FOLDER_ID = st.secrets["google_drive_folder_id"]
SERVICE_ACCOUNT_CREDS = json.loads(st.secrets["gsheet_drive_creds"])

# --- Auth Setup ---
def init_gsheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_CREDS, scope)
    client = gspread.authorize(creds)
    sheet = client.open(GOOGLE_SHEET_NAME).sheet1
    return sheet

def init_drive():
    gauth = GoogleAuth()
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(
        SERVICE_ACCOUNT_CREDS, ["https://www.googleapis.com/auth/drive"]
    )
    gauth.Authorize()
    return GoogleDrive(gauth)

# --- Utils ---
def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

# --- State ---
if 'submitted' not in st.session_state:
    st.session_state['submitted'] = False
if 'user_info' not in st.session_state:
    st.session_state['user_info'] = {}

# --- Page 1: Intro, Name & Email ---
if not st.session_state['submitted']:
    st.title("The Great Floor Survey!")
    st.markdown("""
Welcome to our research effort to **reduce falls** and **preserve active independence** in the elderly.

We're asking for your help by taking part in a quick photo survey of **floor surfaces** commonly found in aged care environments.

### Instructions
- Take **top-down photos** 
- Try to capture **as many different types of floor surfaces** as possible (e.g., carpet, tiles, rugs, wood, ramps, etc.)
- You can upload up to **100 photos** in one go

---

Before we begin, please enter your details below.
""")

    name = st.text_input("Your Name")
    email = st.text_input("Your Email")

    if st.button("Continue"):
        if not name.strip():
            st.error("Please enter your name.")
        elif not is_valid_email(email):
            st.error("Please enter a valid email address.")
        else:
            st.session_state['submitted'] = True
            st.session_state['user_info'] = {'name': name.strip(), 'email': email.strip()}
            st.experimental_rerun()

# --- Page 2: Upload Photos ---
else:
    st.title("Upload Your Floor Photos")

    st.markdown("""
You can now upload your batch of photos. These will help our team build smarter tools to predict and prevent falls in aged care settings.
""")

    uploaded_files = st.file_uploader("Upload up to 100 photos (JPG or PNG)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

    if uploaded_files:
        if len(uploaded_files) > 100:
            st.warning("Please limit your upload to 100 photos.")
        elif st.button("Submit Photos"):
            try:
                drive = init_drive()
                sheet = init_gsheet()

                photo_names = []
                timestamp_str = datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S')

                with st.spinner("Uploading your photos..."):
                    for file in uploaded_files:
                        original_name = file.name
                        ext = original_name.split('.')[-1]
                        unique_filename = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{uuid.uuid4().hex[:8]}.{ext}"
                        photo_names.append(original_name)

                        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                            tmp_file.write(file.read())
                            upload = drive.CreateFile({
                                'title': unique_filename,
                                'parents': [{'id': DRIVE_FOLDER_ID}]
                            })
                            upload.SetContentFile(tmp_file.name)
                            upload.Upload()
                            os.remove(tmp_file.name)

                # Log to Google Sheet
                name = st.session_state['user_info']['name']
                email = st.session_state['user_info']['email']
                sheet.append_row([
                    timestamp_str,
                    name,
                    email,
                    len(photo_names),
                    ", ".join(photo_names)
                ])

                st.success(f"Uploaded {len(photo_names)} photo(s) successfully.")
                st.markdown("---")
                st.markdown("### Thank You")
                st.info("Thank you for joining us on the journey to reduce falls and preserve active independence in the elderly.")

            except Exception as e:
                st.error(f"Upload failed: {e}")
