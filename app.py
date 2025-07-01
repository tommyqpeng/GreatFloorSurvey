import streamlit as st
import boto3
import uuid
from datetime import datetime
import tempfile
import os

# --- Load Secrets ---
AWS_ACCESS_KEY = st.secrets["aws_access_key_id"]
AWS_SECRET_KEY = st.secrets["aws_secret_access_key"]
AWS_REGION = st.secrets["aws_region"]
S3_BUCKET = st.secrets["s3_bucket"]
DYNAMO_TABLE = st.secrets["dynamodb_table"]

# --- AWS Clients ---
s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

dynamodb = boto3.resource(
    "dynamodb",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)
table = dynamodb.Table(DYNAMO_TABLE)

# --- Email Validation ---
import re
def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

# --- App State ---
if 'submitted' not in st.session_state:
    st.session_state['submitted'] = False
if 'user_info' not in st.session_state:
    st.session_state['user_info'] = {}

# --- Page 1: Info Entry ---
if not st.session_state['submitted']:
    st.title("The Great Floor Survey!")

    st.markdown("""
Welcome to our research effort to **reduce falls** and **preserve active independence** in the elderly.

We're asking for your help by taking top-down photos of **common floor surfaces** in aged care environments.

### Instructions
- Take clear **top-down** photos
- Include a variety of surfaces (e.g., carpet, tiles, mats, wood)
- Upload up to **100 photos** per session

---

Before you begin, please enter your name and email:
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
            st.rerun()

# --- Page 2: Upload Photos ---
else:
    st.title("Upload Your Floor Photos")

    st.markdown("""
Upload photos now. They will be securely stored and used to help improve fall prevention tools.
""")

    uploaded_files = st.file_uploader("Upload up to 100 photos (JPG or PNG)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

    if uploaded_files:
        if len(uploaded_files) > 100:
            st.warning("Please limit your upload to 100 photos.")
        elif st.button("Submit Photos"):
            try:
                user_id = str(uuid.uuid4())
                name = st.session_state['user_info']['name']
                email = st.session_state['user_info']['email']
                timestamp = datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S')
                original_names = []

                with st.spinner("Uploading your photos..."):
                    for file in uploaded_files:
                        original_name = file.name
                        ext = original_name.split('.')[-1]
                        unique_filename = f"{timestamp.replace(' ', '_').replace(':', '-')}_{uuid.uuid4().hex[:8]}.{ext}"
                        original_names.append(original_name)

                        # Save temp file to upload
                        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                            tmp_file.write(file.read())
                            tmp_file_path = tmp_file.name

                        s3.upload_file(
                            Filename=tmp_file_path,
                            Bucket=S3_BUCKET,
                            Key=unique_filename,
                            ExtraArgs={"StorageClass": "INTELLIGENT_TIERING"}
                        )
                        os.remove(tmp_file_path)

                # Log to DynamoDB
                table.put_item(Item={
                    "id": user_id,
                    "name": name,
                    "email": email,
                    "timestamp": timestamp,
                    "num_photos": len(original_names),
                    "photo_names": original_names
                })

                st.success(f"Uploaded {len(original_names)} photo(s) successfully.")
                st.markdown("---")
                st.markdown("### Thank You")
                st.info("Thank you for joining us on the journey to reduce falls and preserve active independence in the elderly.")

            except Exception as e:
                st.error(f"Upload failed: {e}")
