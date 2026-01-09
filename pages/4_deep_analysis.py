import streamlit as st
from openai import OpenAI
# Note: You can add other clients (Anthropic, Google) here as you grow

st.set_page_config(page_title="Deep Research Analysis", layout="wide")

st.title("📑 Page 4: Deep Research Synthesis")

# 1. Retrieve the papers you checked on Page 3
selected_ids = st.session_state.get("selected_paper_ids", set())
all_scored = st.session_state.get("scored_papers", [])
final_papers = [p for p in all_scored if p['id'] in selected_ids]

if not final_papers:
    st.warning("⚠️ No papers selected. Go back to Page 3 and check some boxes!")
    if st.button("⬅️ Back to Selection"):
        st.switch_page("pages/3_Sorting_and_Filtering.py")
else:
    st.info(f"Analyzing {len(final_papers)} selected documents.")
    
    # 2. Select the "Strength" LLM based on your handwritten notes
    with st.sidebar:
        st.header("🧠 LLM Strength Selection")
        llm_choice = st.selectbox("Choose Best Task Performer", 
                                ["OpenAI (All-rounder)", "Claude (Citations)", "DeepSeek (Logic)"])
        api_key = st.session_state.get("openai_key")

    if st.button("🚀 Generate Final Summary & Logic"):
        if not api_key:
            st.error("Missing API Key. Please enter it on the Dashboard.")
        else:
            client = OpenAI(api_key=api_key)
            
            for paper in final_papers:
                with st.container(border=True):
                    st.subheader(f"📄 {paper['title']}")
                    st.caption(f"Category: {paper['category']} | Score: {paper['relevance_score']}%")
                    
                    with st.spinner("Writing Logical Arguments..."):
                        # Prompt follows your notes: Read Abstract, Results, Reference sections
                        prompt = f"""
                        Task: Theme Extraction & Long Logic Writing
                        Context: {paper['snippet']}
                        
                        Requirements from User:
                        1. First read Abstract to understand the paper.
                        2. Specifically extract themes from Results & Discussion.
                        3. Write a summary with Logical Arguments.
                        4. Match citations to the Reference Section.
                        """
                        
                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[{"role": "user", "content": prompt}]
                        )
                        st.markdown(response.choices[0].message.content)
            
            st.success("✅ Analysis Complete! You can now copy this to your report.")
