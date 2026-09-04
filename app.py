import os
import fitz  # PyMuPDF
from google import genai
import streamlit as st

st.set_page_config(page_title="Layout PDF Translator", page_icon="📄")
st.title("📄 PDF Layout-Preserving Translator")

# Secret key input or reading environment variable
api_key = st.sidebar.text_input("Gemini API Key", type="password") or os.environ.get("GEMINI_API_KEY")

if not api_key:
    st.warning("Please enter your Gemini API Key in the sidebar to proceed.")
    st.stop()

client = genai.Client(api_key=api_key)

def translate_text(text: str, target_lang: str) -> str:
    """Translates text while stripping excess context."""
    if not text.strip():
        return text
    prompt = f"Translate the following text into {target_lang}. Output ONLY the translated text, no quotes or commentary.\n\n{text}"
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text.strip()

target_language = st.sidebar.selectbox("Target Language", ["Spanish", "French", "German", "Italian", "Portuguese", "Japanese", "Chinese"])
uploaded_file = st.file_uploader("Upload PDF File", type=["pdf"])

if uploaded_file and st.button("Translate PDF"):
    with st.spinner("Processing PDF layout and translating..."):
        try:
            # Read PDF bytes from upload
            pdf_bytes = uploaded_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # Translate page by page
            for page_num in range(len(doc)):
                page = doc[page_num]
                blocks = page.get_text("blocks")
                
                for b in blocks:
                    if b[6] == 0:  # Text block indicator
                        bbox = fitz.Rect(b[:4])
                        original_text = b[4].strip()
                        
                        if not original_text:
                            continue
                        
                        translated_text = translate_text(original_text, target_language)
                        
                        # Remove old text (fill white) and overlay new text
                        page.add_redact_annot(bbox, fill=(1, 1, 1))
                        page.apply_redactions()
                        
                        page.insert_textbox(
                            bbox,
                            translated_text,
                            fontsize=9,
                            fontname="helv",
                            color=(0, 0, 0)
                        )
            
            # Save modified PDF to output buffer
            output_pdf_bytes = doc.tobytes()
            doc.close()
            
            st.success("Translation complete!")
            st.download_button(
                label="Download Translated PDF",
                data=output_pdf_bytes,
                file_name=f"translated_{uploaded_file.name}",
                mime="application/pdf"
            )
        except Exception as e:
            st.error(f"Error processing PDF: {str(e)}")
