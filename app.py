import streamlit as st
import pandas as pd
import requests
import json
import time
import io
import os

# --- Page Configuration ---
st.set_page_config(
    page_title="Cookie Category Analyzer",
    page_icon="🍪",
    layout="centered",
)

# --- Responsive CSS ---
st.markdown(
    """
    <style>
    /* Desktop layout */
    @media (min-width: 768px) {
        [data-testid="stSidebar"] {
            width: 30% !important;
            max-width: 450px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --- Main App UI ---
st.title("🍪 Cookie Category Analyzer")
st.write("Analyze and categorize your website's cookies.")

# --- Corrected instructions to match original logic ---
st.write("Please ensure your Excel file has **no header row**, with data starting from the second row:")
st.markdown("""
- **Column 1:** Should contain the Cookie Name
- **Column 2:** Should contain the Domain Category
""")


# --- Sidebar for API Configuration ---
with st.sidebar:
    st.header("API Configuration")
    st.markdown(
        "To use this app, you need a Google Gemini API key. "
        "You can get a free key from Google AI Studio."
    )

    st.markdown("#### **Step 1: Get Your Key (Optional)**")
    st.link_button(
        "Go to Google AI Studio",
        "https://aistudio.google.com/app/apikey",
        help="Click to open Google AI Studio in a new tab.",
        type="primary",
        use_container_width=True
    )
    
    with st.expander("See instructions for Google AI Studio"):
        st.info("On the Google AI Studio website, follow these two steps:")
        st.markdown("1. Click the **Create API key** button.")
        st.markdown("2. In the pop-up, click **Create API key in new project**.")
        st.markdown("3. Copy the generated key and paste it below.")
        
    st.markdown("---")

    st.markdown("#### **Step 2: Enter Your Key**")
    st.caption("If you leave this blank, a default key will be used.")
    GEMINI_API_KEY_USER = st.text_input(
        "Paste your Gemini API Key here", type="password", label_visibility="collapsed"
    )

    # --- NEW: Logic to use a fallback API key ---
    # Securely access the default key from st.secrets
    # In your local environment, create a file .streamlit/secrets.toml
    # And add: GEMINI_API_KEY = "AIzaSyDyz5l3BWGA9XRcQcsNAuBLyO-DchLutIs"
    try:
        FALLBACK_API_KEY = st.secrets["GEMINI_API_KEY"]
    except:
        # This is a less secure fallback for environments without secrets.toml
        FALLBACK_API_KEY = "AIzaSyDyz5l3BWGA9XRcQcsNAuBLyO-DchLutIs"


    if GEMINI_API_KEY_USER:
        GEMINI_API_KEY = GEMINI_API_KEY_USER
        st.success("Using your provided API key.")
    else:
        GEMINI_API_KEY = FALLBACK_API_KEY
        st.info("Using the default API key for analysis.")

    API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

    st.header("Processing Controls")
    st.caption("Adjust the processing speed and retry attempts.")
    MAX_RETRIES = st.slider("Max Retries per Cookie", 5, 10, 5) 
    CHUNK_SIZE_PAUSE = st.slider("Pause After # Cookies", 5, 100, 5) 
    PAUSE_DURATION = st.slider("Pause Duration (seconds)", 10, 60, 10)


# --- Core Functions ---
def get_cookie_details(_cookie_name, retries):
    headers = {"Content-Type": "application/json"}
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "cookieName": {"type": "STRING"},
            "recommendedCategory": {"type": "STRING"},
            "justification": {"type": "STRING"},
        }, "required": ["cookieName", "recommendedCategory", "justification"],
    }
    prompt_text = (
        f"Analyze the cookie named '{_cookie_name}'. "
        f"Determine its category (e.g., 'Essential Cookies', 'Performance Cookies', "
        f"'Functional Cookies', 'Targeting Cookies', 'Unknown') "
        f"and provide a concise justification for this classification. "
        f"The justification should be no more than two lines and should summarize the cookie's function and why it belongs to the assigned category."
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt_text}]}],
        "generationConfig": { "responseMimeType": "application/json", "responseSchema": response_schema, },
    }
    for attempt in range(retries):
        try:
            response = requests.post(API_URL, headers=headers, data=json.dumps(payload))
            response.raise_for_status()
            response_data = response.json()
            if "candidates" in response_data and response_data["candidates"]:
                return json.loads(response_data["candidates"][0]["content"]["parts"][0]["text"])
            else: return None
        except requests.exceptions.RequestException as e:
            status_code = getattr(e.response, "status_code", None)
            if status_code == 429:
                time.sleep(60)
                continue
            time.sleep(2**attempt)
    return {"cookieName": _cookie_name, "recommendedCategory": "Error", "justification": f"API call failed after {retries} attempts."}

def process_dataframe(df):
    # Use column names instead of indices for clarity
    cookie_records = [tuple(row) for row in df[["Cookie Name", "Domain Category"]].itertuples(index=False)]
    
    total_cookies = len(cookie_records)
    st.info(f"Found {total_cookies} unique cookies to process.")
    
    progress_bar = st.progress(0, text="Initializing...")
    status_text = st.empty()
    results_list = []

    for index, (cookie_name, domain_category) in enumerate(cookie_records):
        status_text.text(f"🔄 Processing {index + 1}/{total_cookies}: {cookie_name}")
        try:
            time.sleep(1) # Basic rate limiting
            api_details = get_cookie_details(cookie_name, retries=MAX_RETRIES) 
            
            if api_details:
                gemini_category = api_details.get("recommendedCategory", "Unknown")
                gemini_justification = api_details.get("justification", "")
                final_category = gemini_category
                final_justification = gemini_justification

                if gemini_category == domain_category:
                    if gemini_category == "Unknown":
                        final_justification = "Need confirmation from Client"
                    else:
                        final_justification = "N/A"
                else: 
                    if gemini_category == "Unknown":
                        final_category = domain_category
                        final_justification = "N/A"
                    elif domain_category != "Unknown":
                        final_category = f"{domain_category}/{gemini_category}"
                        final_justification = (f"Depending on the website's use case it can be classified as " f"{domain_category}/{gemini_category}. {gemini_justification}")
                
                final_result = {
                    "Cookie Name": cookie_name, 
                    "Domain Category": domain_category, 
                    "Recommended Category": final_category, 
                    "Justification": final_justification
                }
                results_list.append(final_result)
        except Exception as e:
            results_list.append({
                "Cookie Name": cookie_name, 
                "Domain Category": domain_category, 
                "Recommended Category": "Processing Error", 
                "Justification": str(e)
            })
            
        progress_bar.progress((index + 1) / total_cookies, text=f"Processed {index + 1}/{total_cookies}")
        
        if (index + 1) % CHUNK_SIZE_PAUSE == 0 and (index + 1) < total_cookies:
            status_text.text(f"⏸️ Pausing for {PAUSE_DURATION} seconds to manage rate limits...")
            time.sleep(PAUSE_DURATION)

    status_text.success("🎉 All cookies have been processed!")
    return pd.DataFrame(results_list)

# --- File Uploader and Main Logic ---
uploaded_file = st.file_uploader("Choose an Excel file", type=["xlsx"], label_visibility="collapsed")

if uploaded_file:
    if not GEMINI_API_KEY:
        st.error("Please enter your Gemini API Key in the sidebar to begin.")
    else:
        try:
            # Read file with no header and skipping the first row
            input_df = pd.read_excel(uploaded_file, header=None, skiprows=1)
            # Assign clear column names
            input_df.columns = ["Cookie Name", "Domain Category"]

            # --- Preprocessing Step: Identify and display duplicates ---
            duplicate_mask = input_df.duplicated(subset="Cookie Name", keep=False)
            duplicate_cookies_df = input_df[duplicate_mask].sort_values(by="Cookie Name")

            if not duplicate_cookies_df.empty:
                st.warning(f"⚠️ Found {len(duplicate_cookies_df)} duplicate cookie entries.")
                st.write("### Duplicate Cookies Found:")
                st.dataframe(duplicate_cookies_df.reset_index().rename(columns={'index': 'Original Row (1-based)'}))
                st.write("Removing these duplicates for analysis to prevent redundant API calls.")
            else:
                st.success("✅ No duplicate cookie entries found. Proceeding with analysis.")
            
            if st.button("Start Analysis", type="primary", use_container_width=True):
                with st.spinner("Analyzing cookies... This may take a while."):
                    # --- Preprocessing Step: Remove duplicates for API processing ---
                    unique_cookies_df = input_df.drop_duplicates(subset=["Cookie Name"]).copy()
                    
                    # Process only the unique cookies
                    analysis_results_df = process_dataframe(unique_cookies_df)

                    # --- NEW: Merge the analysis results back to the original dataframe ---
                    # This ensures the output file has the same number of rows as the input
                    # and duplicates get the same analysis result.
                    
                    # We only need the new analysis columns from the results
                    result_columns = ["Cookie Name", "Recommended Category", "Justification"]
                    
                    # Use a left merge to map results back to the original full list
                    output_df = pd.merge(
                        input_df, 
                        analysis_results_df[result_columns], 
                        on="Cookie Name", 
                        how="left"
                    )

                    st.write("### Analysis Results")
                    st.dataframe(output_df)

                    # Prepare for download
                    output_buffer = io.BytesIO()
                    with pd.ExcelWriter(output_buffer, engine="xlsxwriter") as writer:
                        output_df.to_excel(writer, index=False, sheet_name="Results")
                    
                    st.download_button(
                        label="📥 Download Results as Excel", 
                        data=output_buffer.getvalue(), 
                        file_name="cookie_analysis_results.xlsx", 
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                        use_container_width=True
                    )
        except Exception as e:
            st.error(f"An error occurred while reading or processing the file: {e}")