import streamlit as st
from fpdf import FPDF
import fitz  # PyMuPDF
from PIL import Image
import json
import requests
import os
from datetime import datetime
import pytz
from github import Github
import streamlit_authenticator as stauth
import pandas as pd
import base64

# Branding Guidelines and css
PRIMARY_COLOR = "#06B6D4"  # Main accent color
SECONDARY_COLOR = "#737373"  # Subheading / body text color
BACKGROUND_COLOR = "#EBEBEB"  # Light background
st.set_page_config(page_title="1st Optimal Health Report Generator", page_icon="⚕️", initial_sidebar_state="expanded")

# Function to load external CSS file
def load_css_from_github(raw_css_url):
    try:
        response = requests.get(raw_css_url)
        if response.status_code == 200:
            st.markdown(f"<style>{response.text}</style>", unsafe_allow_html=True)
        else:
            st.error("Failed to load external CSS.")
    except Exception as e:
        st.error(f"Error loading CSS: {e}")

# GitHub Raw URL for the styles.css file
GITHUB_CSS_URL = "https://raw.githubusercontent.com/theebuddylee/HealthReport/main/styles.css"

# Apply the external CSS
load_css_from_github(GITHUB_CSS_URL)

#Control Session State variables
if "current_plan_tests" not in st.session_state:
    st.session_state.current_plan_tests = []
if "current_plan_medications" not in st.session_state:
    st.session_state.current_plan_medications = []
if "current_plan_supplements" not in st.session_state:
    st.session_state.current_plan_supplements = []

# Membership Manager Dropdown and Member's Name input
st.sidebar.title("Member Details")
membership_managers = ["Allison", "Amber", "Buddy", "Brian", "Casey", "Dillon", "Jamie", "Joe"]
selected_manager = st.sidebar.selectbox("Select Membership Manager", membership_managers)
member_name = st.sidebar.text_input("Enter Member/Patient Name")

# Base URL for GitHub raw content
GITHUB_BASE_URL = "https://raw.githubusercontent.com/theebuddylee/HealthReport/main/data/"

# Function to load JSON files from GitHub
def load_json_from_github(filename):
    url = f"{GITHUB_BASE_URL}{filename}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Failed to load {filename}. HTTP {response.status_code}")
        return {}

# Load JSON data
contact_info = load_json_from_github("contact_info.json")
memberships = load_json_from_github("memberships.json")
diagnostic_tests = load_json_from_github("diagnostic_tests.json")
medications = load_json_from_github("medications.json")
supplements = load_json_from_github("supplements.json")

# Path to the PDF template
template_pdf_path = "1st Optimal Treatment PlanV2.pdf"

# Function to merge PDFs
def merge_pdfs(template_path, generated_path, output_path):
    with fitz.open(template_path) as template_pdf:
        output_pdf = fitz.open()

        # Add first 2 pages from template
        for page_num in range(2):
            output_pdf.insert_pdf(template_pdf, from_page=page_num, to_page=page_num)

        # Append the generated content PDF
        with fitz.open(generated_path) as generated_pdf:
            output_pdf.insert_pdf(generated_pdf)

        # Append the last 7 pages from the template
        total_pages = len(template_pdf)
        for page_num in range(total_pages - 6, total_pages):
            output_pdf.insert_pdf(template_pdf, from_page=page_num, to_page=page_num)

        output_pdf.save(output_path)

# Function to write More Information Sections on first and last page onto merged PDF
def overwrite_more_information(template_path, output_path, member_name, selected_manager):
    try:
        # Set your desired timezone
        local_timezone = pytz.timezone("America/Los_Angeles")
        current_date = datetime.now(local_timezone).strftime("%m-%d-%Y")

        # Retrieve manager info from the dictionary
        manager_info = contact_info.get(selected_manager, {"email": "N/A", "phone": "N/A"})
        manager_name = f"{manager_info.get('first_name', 'Unknown')} {manager_info.get('last_name', 'Unknown')}"
        manager_email = manager_info.get("email", "N/A")
        manager_phone = manager_info.get("phone", "N/A")

        # Open the template PDF
        doc = fitz.open(template_path)
        first_page = doc[0]  # Access the first page
        last_page = doc[-1]  # Access the last page

        # Define the text to insert on the first page
        first_page_content = [
            (f"{member_name or 'Not Provided'}", 1.1 * 72, 8.8 * 72),
            (f"{current_date}", 1.1 * 72, 9.31 * 72),
            (f" {selected_manager or 'Not Selected'}", 1.1 * 72, 9.85 * 72),
        ]

        # Write the text on the first page
        for content, x, y in first_page_content:
            first_page.insert_text(
                (x, y),
                content,
                fontsize=18,
                color=(1, 1, 1),  # Secondary Grey text color
                fontname="helv",
            )

        # Define the text to insert on the last page
        last_page_content = [
            (f"Health Coach: {manager_name}", 73, 8.36 * 72)]

        # Write the text on the last page
        for content, x, y in last_page_content:
            last_page.insert_text(
                (x, y),
                content,
                fontsize=18,
                 color=(1, 1, 1),  # Secondary Grey text color
                fontname="helv",
            )

        # Save the updated PDF
        doc.save(output_path)
        doc.close()
        return output_path
    except Exception as e:
        print(f"Error in overwrite_more_information: {e}")
        return None

# Section Generate Function
def add_section(title, items, data_source, pdf, show_price=False):
    if not items:
        return

    # Header for each section
    pdf.set_fill_color(6, 182, 212)
    pdf.set_text_color(242, 242, 242)
    pdf.set_font("Exo2", "B", 22)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT", align="L", fill=True)
    pdf.ln(5)

    # Content for each item
    pdf.set_text_color(115, 115, 115)
    for item in items:
        # Handle both strings and dictionaries
        if isinstance(item, dict):
            item_data = item
        else:
            item_data = next(
                (x for x in data_source if x['name'].strip().lower() == item.strip().lower()),
                None
            )

        if not item_data:
            #st.write(f"DEBUG: No match found for item '{item}' in section '{title}'.")
            continue

        # Render item content
        pdf.set_font("Exo2", "B", 20)

        # Check if this is a Diagnostic Test with a valid Shopify URL
        test_url = item_data.get("shopify_url", "")

        if test_url:  # If a valid URL exists, make it clickable
            pdf.cell(0, 8, f"{item_data['name']}", new_x="LMARGIN", new_y="NEXT", link=test_url)
            pdf.set_text_color(115, 115, 115)  # Reset text color back to normal
        else:  # If no URL, render normally
            pdf.cell(0, 8, f"{item_data['name']}", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(2)

        pdf.set_font("Exo2", "BI", 16)
        pdf.cell(0, 6, "Description:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Exo2", "", 12)
        pdf.multi_cell(0, 6, f"{item_data.get('description', 'N/A')}")

        pdf.ln(3)
        pdf.set_font("Exo2", "BI", 16)
        pdf.cell(0, 6, "Indication:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Exo2", "", 12)
        pdf.multi_cell(0, 6, f"{item_data.get('indication', 'No indication provided.')}")

        if show_price:
            pdf.ln(3)
            pdf.set_font("Exo2", "BI", 16)
            pdf.cell(0, 6, "Price:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Exo2", "", 12)
            pdf.multi_cell(0, 6, f"{item_data.get('price', 'TBD')}")
        pdf.ln(5)

# PDF generation function
def generate_pdf(selected_membership, final_tests, final_medications, final_supplements):
    try:
        generated_pdf_path = "generated_content.pdf"
        merged_pdf_path = "final_treatment_plan.pdf"
        updated_pdf_path = "updated_treatment_plan.pdf"

        # Initialize PDF
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()

        # Add Exo 2 font
        pdf.add_font("Exo2", "", "Exo2-Regular.ttf")
        pdf.add_font("Exo2", "B", "Exo2-Bold.ttf")
        pdf.add_font("Exo2", "I", "Exo2-Italic.ttf")
        pdf.add_font("Exo2", "BI", "Exo2-BoldItalic.ttf")

        # Create Title
        pdf.set_text_color(6, 182, 212)
        pdf.set_font("Exo2", "B", 36)
        pdf.cell(0, 10, "1st Optimal Treatment Plan", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(10)

        # Add sections to the PDF
        add_section("Membership", selected_membership, memberships, pdf, show_price=True)
        add_section("Diagnostic Testing", final_tests, diagnostic_tests, pdf)
        add_section("Medications", final_medications, medications, pdf)
        add_section("Supplements", final_supplements, supplements, pdf)

        # Save PDF and merge
        pdf.output(generated_pdf_path)
        merge_pdfs(template_pdf_path, generated_pdf_path, merged_pdf_path)

        # Add additional information to the final PDF
        return overwrite_more_information(merged_pdf_path, updated_pdf_path, member_name, selected_manager)
    except Exception as e:
        st.error(f"Error generating PDF: {e}")
        return None

# GitHub Configuration
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]  # Securely stored in Streamlit secrets
REPO_NAME = "theebuddylee/HealthReport"
FILE_PATH = "analytics.json"

def log_to_github(data):
    # Add a timestamp to the data
    data["timestamp"] = datetime.now().isoformat()

    try:
        # Authenticate with GitHub
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)

        # Fetch the current analytics.json file
        file = repo.get_contents(FILE_PATH)
        analytics_data = json.loads(file.decoded_content.decode())
    except Exception:
        # If the file doesn't exist or is empty, initialize as an empty list
        analytics_data = []

    # Append the new data
    analytics_data.append(data)

    # Commit the updated file to GitHub
    try:
        if 'file' in locals():
            # Update the existing file
            repo.update_file(FILE_PATH, "Update analytics.json", json.dumps(analytics_data, indent=4), file.sha)
        else:
            # Create a new file if it doesn't exist
            repo.create_file(FILE_PATH, "Create analytics.json", json.dumps(analytics_data, indent=4))
    except Exception as e:
        print(f"Error updating GitHub: {e}")

# Load and display the logo
logo_path = "1st-Optimal-Logo-Dark.png"  # Replace with your actual logo file path
st.image(logo_path, width=500)  # Adjust width as needed

# Streamlit UI
st.title("1st Optimal Treatment Plan Generator")
st.subheader("Select Products for Your Report")

# Membership dropdown
selected_membership = st.multiselect("Membership", [item['name'] for item in memberships], max_selections=1)

# Dropdowns for Tests, Medications, and Supplements
def add_custom_entry(category, base_items, session_state_key):
    # Display dropdown with all items (full dictionaries) plus "Other"
    selected_items = st.multiselect(
        f"Select {category}", [item['name'] for item in base_items] + ["Other"], max_selections=10
    )

    # Handle "Other" for adding custom entries
    if "Other" in selected_items:
        st.subheader(f"Add a Custom {category[:-1]}")
        custom_name = st.text_input(f"{category[:-1]} Name")
        custom_description = st.text_area(f"{category[:-1]} Description")
        custom_indication = st.text_area(f"{category[:-1]} Indication")
        if st.button(f"Add {category[:-1]}"):
            if custom_name and custom_description and custom_indication:
                st.success(f"Custom {category[:-1]} '{custom_name}' added!")
                st.session_state[session_state_key].append({
                    "name": custom_name,
                    "description": custom_description,
                    "indication": custom_indication,
                })
            else:
                st.error("Please fill all fields to add the custom entry.")

    # Combine selected predefined items and custom entries
    final_items = st.session_state[session_state_key] + [
        item for item in base_items if item['name'] in selected_items
    ]

    return final_items

# Process user selections
final_tests = add_custom_entry("Tests", diagnostic_tests, "current_plan_tests")
final_medications = add_custom_entry("Medications", medications, "current_plan_medications")
final_supplements = add_custom_entry("Supplements", supplements, "current_plan_supplements")

# Optimized Side-by-Side Cards Layout with Branding Styles
optimized_card_layout = f"""
<style>
    .test-card {{
        border: 2px solid {PRIMARY_COLOR};
        padding: 15px;
        border-radius: 12px;
        background-color: {BACKGROUND_COLOR};
        box-shadow: 2px 2px 10px rgba(0,0,0,0.1);
        margin-bottom: 15px;
    }}
    .test-card h4 {{
        text-align: center;
        margin-bottom: 8px;
        font-size: 18px;
        color: {PRIMARY_COLOR};
    }}
    .test-card a {{
        text-decoration: none;
        font-weight: bold;
        color: {PRIMARY_COLOR};
    }}
    .test-card details {{
        margin-top: 5px;
        font-size: 14px;
    }}
    .test-card summary {{
        font-weight: bold;
        cursor: pointer;
        color: {SECONDARY_COLOR};
    }}
    .test-card p {{
        font-size: 13px;
        color: {SECONDARY_COLOR};
    }}
</style>
"""
#Comparison table for selected tests
if final_tests:
    st.markdown("### Compare Selected Tests")

    num_columns = min(len(final_tests), 3)  # Max 3 columns per row
    rows = [final_tests[i : i + num_columns] for i in range(0, len(final_tests), num_columns)]

    for row in rows:
        cols = st.columns(len(row))

        for col, test in zip(cols, row):
            with col:
                shopify_url = test.get("shopify_url", "#")  # Use '#' if missing to prevent errors

                st.markdown(
                    f"""
                    <div class="test-card">
                        <h4>
                            <a href="{shopify_url}" target="_blank">{test['name']}</a>
                        </h4>
                        <details open>  <!-- Keep expanded on load -->
                            <summary>Description</summary>
                            <p>{test.get('description', 'N/A')}</p>
                        </details>
                        <details open>  <!-- Keep expanded on load -->
                            <summary>Indication</summary>
                            <p>{test.get('indication', 'N/A')}</p>
                        </details>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

# Debugging
#st.write("DEBUG: Final Tests:", final_tests)
#st.write("DEBUG: Final Medications:", final_medications)
#st.write("DEBUG: Final Supplements:", final_supplements)

# PDF Generation
if st.button("Generate PDF"):
    # Debugging: Display the selections
    #st.write("DEBUG: Selected Membership:", selected_membership)
    #st.write("DEBUG: Final Tests:", final_tests)
    #st.write("DEBUG: Final Medications:", final_medications)
    #st.write("DEBUG: Final Supplements:", final_supplements)

    # Attempt to generate the PDF
    pdf_path = generate_pdf(selected_membership, final_tests, final_medications, final_supplements)

    # Log analytics data to GitHub
    analytics_data = {
        "member_name": member_name,
        "manager": selected_manager,
        "membership": selected_membership,
        "tests": final_tests,
        "medications": final_medications,
        "supplements": final_supplements,
    }
    try:
        log_to_github(analytics_data)
        #st.success("Selections logged to GitHub Analytics successfully!")
    except Exception as e:
        st.error(f"Failed to log selections to Analytics: {e}")

    # Handle PDF generation result
    if pdf_path:
        st.success("PDF generated successfully!")
        with open(pdf_path, "rb") as pdf_file:
            st.download_button("Download Treatment Plan", data=pdf_file, file_name="1stOptimal_Treatment_Builder_Template.pdf", mime="application/pdf")
    else:
        st.error("PDF generation failed.")

def load_json_with_sha_from_github(filename):
    # Use the GitHub API URL for the file
    url = f"https://api.github.com/repos/theebuddylee/HealthReport/contents/data/{filename}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        # Parse the response JSON
        content = response.json()
        file_content = content.get("content")  # File content is Base64-encoded
        sha = content.get("sha")  # File SHA
        if file_content and sha:
            # Decode the Base64-encoded content
            json_data = json.loads(base64.b64decode(file_content).decode("utf-8"))
            return json_data, sha
        else:
            st.error("Failed to extract file content or SHA from the response.")
            return None, None
    else:
        st.error(f"Failed to load {filename}. HTTP {response.status_code}")
        return None, None

def update_json_on_github(filename, data, sha):
    # GitHub API URL for the file
    url = f"https://api.github.com/repos/theebuddylee/HealthReport/contents/data/{filename}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    # Prepare the payload for updating the file
    payload = {
        "message": f"Update {filename}",  # Commit message
        "content": base64.b64encode(json.dumps(data, indent=4).encode("utf-8")).decode("utf-8"),  # Base64-encoded content
        "sha": sha  # The SHA of the file being updated
    }

    # Send the PUT request to update the file
    response = requests.put(url, headers=headers, json=payload)
    if response.status_code == 200:
        st.success(f"{filename} updated successfully!")
    else:
        st.error(f"Failed to update {filename}. HTTP {response.status_code}: {response.json()}")

# Advanced Editing Interface with Toggle and Secure Password Authentication
st.sidebar.markdown("---")  # Adds a visual divider
sidebar_placeholder = st.sidebar.empty()

with sidebar_placeholder:
    show_editor = st.sidebar.toggle("Enable Product Editor")

# If the toggle is enabled, request admin password
if show_editor:
    admin_pass = st.sidebar.text_input("Enter Admin Password", type="password")

    # Retrieve stored password from Streamlit secrets
    stored_password = st.secrets["ADMIN_PASS"] if "ADMIN_PASS" in st.secrets else None

    if stored_password and admin_pass == stored_password:
        with st.expander("Product Editor"):
            st.subheader("Edit JSON Files")

            # Select JSON file to edit
            json_files = ["contact_info.json", "memberships.json", "diagnostic_tests.json", "medications.json", "supplements.json"]
            selected_file = st.selectbox("Select JSON File to Edit:", json_files)

            # Load the selected file
            data, sha = load_json_with_sha_from_github(selected_file)

            if data:
                # Display JSON editor
                edited_data = st.text_area("Edit JSON Data:", value=json.dumps(data, indent=4), height=400)

                if st.button("Save Changes"):
                    try:
                        # Update the JSON file on GitHub
                        update_json_on_github(selected_file, json.loads(edited_data), sha)
                    except Exception as e:
                        st.error(f"Failed to save changes: {e}")
            else:
                st.error(f"Unable to load {selected_file}.")
    else:
        st.sidebar.error("Incorrect password. Access denied.")


