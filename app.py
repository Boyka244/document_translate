import os
import time
import fitz  # PyMuPDF
from google import genai
import streamlit as st

st.set_page_config(page_title="Layout PDF Translator", page_icon="📄")
st.title("📄 PDF Layout-Preserving Translator")

api_key = st.sidebar.text_input("Gemini API Key", type="password") or os.environ.get("GEMINI_API_KEY")

if not api_key:
    st.warning("Please enter your Gemini API Key in the sidebar to proceed.")
    st.stop()

client = genai.Client(api_key=api_key)

def translate_batch(texts: list[str], target_lang: str) -> list[str]:
    """Translates a list of text blocks in a single API request to avoid rate limits."""
    if not texts:
        return []
    
    # Format texts as a numbered list
    formatted_prompt = f"Translate each of the following text blocks into {target_lang}.\n"
    formatted_prompt += "Return ONLY a numbered list of translations matching the exact input order.\n"
    formatted_prompt += "Do NOT combine lines, add intro text, or skip any items.\n\n"
    
    for idx, text in enumerate(texts):
        formatted_prompt += f"{idx + 1}. {text}\n"

    # Retry loop with backoff for rate limits (429 / 503)
    for attempt in range(5):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=formatted_prompt
            )
            
            # Parse numbered responses back into a list
            lines = response.text.strip().split("\n")
            translations = []
            for line in lines:
                # Remove leading numbers like "1. ", "2. "
                clean_line = line.strip()
                if clean_line and clean_line[0].isdigit():
                    parts = clean_line.split(".", 1)
                    if len(parts) > 1:
                        clean_line = parts[1].strip()
                if clean_line:
                    translations.append(clean_line)
            
            # Fallback if parsing counts match
            if len(translations) == len(texts):
                return translations
            return [line for line in lines if line.strip()][:len(texts)]

        except Exception as e:
            if "429" in str(e) or "503" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait_time = 4 * (attempt + 1)
                time.sleep(wait_time)
                continue
            raise e
            
    return texts  # Return originals if all retries fail

target_language = st.sidebar.selectbox("Target Language", ["Romanian", "Spanish", "French", "German", "Italian", "Portuguese", "Japanese", "Chinese"])
uploaded_file = st.file_uploader("Upload PDF File", type=["pdf"])

if uploaded_file and st.button("Translate PDF"):
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        pdf_bytes = uploaded_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        
        for page_num in range(total_pages):
            status_text.text(f"Translating Page {page_num + 1} of {total_pages}...")
            page = doc[page_num]
            blocks = page.get_text("blocks")
            
            # Filter text blocks
            valid_blocks = [b for b in blocks if b[6] == 0 and b[4].strip()]
            
            if valid_blocks:
                original_texts = [b[4].strip() for b in valid_blocks]
                
                # Single batch API call for the whole page
                translated_texts = translate_batch(original_texts, target_language)
                
                # Overlay translated text back onto the PDF
                for idx, b in enumerate(valid_blocks):
                    bbox = fitz.Rect(b[:4])
                    trans_text = translated_texts[idx] if idx < len(translated_texts) else original_texts[idx]
                    
                    page.add_redact_annot(bbox, fill=(1, 1, 1))
                    page.apply_redactions()
                    
                    page.insert_textbox(
                        bbox,
                        trans_text,
                        fontsize=8,
                        fontname="helv",
                        color=(0, 0, 0)
                    )
            
            # Throttle requests slightly to stay safely under free rate limits
            time.sleep(2)
            progress_bar.progress((page_num + 1) / total_pages)
        
        output_pdf_bytes = doc.tobytes()
        doc.close()
        
        status_text.text("Translation complete!")
        st.success("PDF Translated Successfully!")
        st.download_button(
            label="Download Translated PDF",
            data=output_pdf_bytes,
            file_name=f"translated_{uploaded_file.name}",
            mime="application/pdf"
        )
    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}")
