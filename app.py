import streamlit as st
import boto3
import uuid
from datetime import datetime
from PIL import Image
import io
import re
import os
import base64

# --- Page Config ---
st.set_page_config(
    page_title="The Great Floor Survey",
    page_icon="senstride_icon.png"
)

st.markdown("""
<style>
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)
    
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

# --- Session State Setup ---
if "user_info_provided" not in st.session_state:
    st.session_state["user_info_provided"] = False
if "upload_complete" not in st.session_state:
    st.session_state["upload_complete"] = False
if "user_info" not in st.session_state:
    st.session_state["user_info"] = {}

# --- Helpers ---
def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

# --- UI Screens ---
def show_user_info_form():
    st.image("collage.jpg", use_container_width=True)

    # Use columns to center the container
    left_col, center_col, right_col = st.columns([1, 5, 1])
    with center_col:
        
        with open("senstride_logo.png", "rb") as f:
            img_data = base64.b64encode(f.read()).decode()
        
        st.markdown(f"""
        <div style='text-align: center; margin-top: 1rem; margin-bottom: 2rem;'>
            <img src='data:image/png;base64,{img_data}' width='180'/>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="white-box">', unsafe_allow_html=True)

        st.title("The Great Floor Survey!")
        st.markdown("""
Welcome to our research effort to **reduce falls** and **preserve active independence** in the elderly.

We're asking for your help by taking top-down photos of **common floor surfaces** in aged care environments.

Thank you from the Senstride team!

### Instructions
- Take clear **top-down** photos
- Include a variety of surfaces (e.g., carpet, tiles, mats, wood)
- Upload up to **50 photos** per session
- Only `.jpg` or `.jpeg` files are accepted

---

Before you begin, please enter your details:
""")

        name = st.text_input("Your Name", value="")
        email = st.text_input("Your Email", value="")
        organisation = st.text_input("Organisation Name", value="")

        name_clean = name.strip()
        email_clean = email.strip()
        org_clean = organisation.strip()

        if st.button("Continue"):
            if not name_clean:
                st.error("Please enter your name.")
            elif not is_valid_email(email_clean):
                st.error("Please enter a valid email address.")
            elif not org_clean:
                st.error("Please enter your organisation name.")
            else:
                st.session_state["user_info"] = {
                    "name": name_clean,
                    "email": email_clean,
                    "organisation": org_clean
                }
                st.session_state["user_info_provided"] = True
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    st.stop()

def show_thank_you_screen():
    st.title("Upload Complete")
    st.success("Your photos have been uploaded.")
    st.markdown("### Thank You")
    st.info("Thank you for joining us on the journey to reduce falls and preserve active independence in the elderly.")
    st.stop()

def show_upload_screen():
    st.title("Upload Your Floor Photos")
    st.markdown("""
Upload photos now. They will be securely stored and used to help improve fall prevention tools.

**Only .jpg or .jpeg files are accepted.**
""")

    uploaded_files = st.file_uploader(
        "Upload s many as you want - from 1 to 50 at a time",
        type=["jpg", "jpeg"],
        accept_multiple_files=True
    )

    if uploaded_files:
        if len(uploaded_files) > 50:
            st.warning("Please limit your upload to 50 photos.")
        elif st.button("Submit Photos"):
            try:
                user_id = str(uuid.uuid4())
                user_info = st.session_state["user_info"]
                timestamp = datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S')
                uploaded_filenames = []

                with st.spinner("Uploading your photos..."):
                    for file in uploaded_files:
                        ext = file.name.split('.')[-1].lower()
                        if ext not in ["jpg", "jpeg"]:
                            continue  # Skip non-JPGs (safety check)

                        unique_filename = f"{timestamp.replace(' ', '_').replace(':', '-')}_{uuid.uuid4().hex[:8]}.jpg"
                        uploaded_filenames.append(unique_filename)

                        image = Image.open(file)

                        # Resize if wider than 1280px
                        if image.width > 1280:
                            w_percent = 1280 / float(image.width)
                            h_size = int((float(image.height) * float(w_percent)))
                            image = image.resize((1280, h_size), Image.LANCZOS)

                        buffer = io.BytesIO()
                        image.save(buffer, format="JPEG", quality=90, optimize=True)
                        buffer.seek(0)

                        s3.upload_fileobj(
                            buffer,
                            Bucket=S3_BUCKET,
                            Key=unique_filename
                        )

                # Log metadata to DynamoDB
                table.put_item(Item={
                    "id": user_id,
                    "name": user_info["name"],
                    "email": user_info["email"],
                    "organisation": user_info["organisation"],
                    "timestamp": timestamp,
                    "num_photos": len(uploaded_filenames),
                    "photo_names": uploaded_filenames
                })

                st.session_state["upload_complete"] = True
                st.rerun()

            except Exception as e:
                st.error(f"Upload failed: {e}")
    st.stop()

# --- Routing Logic ---
if not st.session_state["user_info_provided"]:
    show_user_info_form()
elif st.session_state["upload_complete"]:
    show_thank_you_screen()
else:
    show_upload_screen()
