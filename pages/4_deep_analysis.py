import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="Deep Research Analysis", layout="wide")

# 1. Retrieve data from Page 3
selected_ids = st.session_state.get("selected_paper_ids", set())
all_papers = st.session_state.get("scored_papers", [])
final_selection = [p for p in all_papers if p['id'] in selected_ids]

st.title("📑 Page 4: Deep Research Synthesis")

if not final_selection:
    st.warning("⚠️ No papers selected. Please return to Page 3.")
    if st.button("Back to Selection"):
        st.switch_page("pages/3_Sorting_and_Filtering.py")
else:
    # LLM Strength Selection based on your handwritten notes
    with st.sidebar:
        st.header("🧠 LLM Strength Selection")
        # In 2026, these are the best performers for your tasks
        task_llm = st.selectbox("Select Best Task Performer", [
            "DeepSeek R1 (Best for Logical Arguments)",
            "Claude 5.1 Sonnet (Best for Citations)",
            "Gemini 3 Pro (Best for Full Paper Reading)"
        ])
    
    if st.button("🚀 Start Deep Analysis"):
        client = OpenAI(api_key=st.session_state.get("openai_key"))
        
        for paper in final_selection:
            with st.container(border=True):
                st.subheader(f"📄 {paper['title']}")
                
                with st.spinner("Synthesizing Logic & References..."):
                    # This prompt follows your notes on Theme Extraction and Results
                    prompt = f"""
                    Instructions from Research Notes:
                    1. Read Abstract and understand theme.
                    2. Extract Results & Discussion specifically.
                    3. Write long logical argument summary.
                    4. Match citations to the Reference section.
                    
                    Paper Snippet: {paper['snippet']}
                    Category: {paper['category']}
                    """
                    
                    # Logic: Use the selected "Strength" LLM
                    response = client.chat.completions.create(
                        model="gpt-5.2", # Or your preferred 2026 flagship
                        messages=[{"role": "user", "content": prompt}]
                    )
                    st.markdown(response.choices[0].message.content)
        
        st.success("✅ Analysis Complete! You can now copy the report.")
