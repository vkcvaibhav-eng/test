import streamlit as st
from logic import generate_ideas_deepseek, select_and_score_openai

st.set_page_config(page_title="AI Idea Dashboard", layout="centered")

# Initialize session state for the idea
if "passed_idea" not in st.session_state:
    st.session_state.passed_idea = ""

with st.sidebar:
    st.header("🔑 API Settings")
    deepseek_key = st.text_input("DeepSeek API Key", type="password")
    openai_key = st.text_input("OpenAI Key", type="password")

st.title("💡 Idea Generation Dashboard")

with st.container(border=True):
    title = st.text_input("Project Title")
    search_title = st.text_input("Search Title")
    tongue_use = st.text_input("Tongue Use")

if st.button("Generate & Process", type="primary"):
    if not deepseek_key or not openai_key:
        st.error("Please enter both API keys.")
    else:
        with st.spinner("Processing..."):
            raw_ideas = generate_ideas_deepseek(deepseek_key, title, search_title, tongue_use)
            best_idea, clout = select_and_score_openai(openai_key, raw_ideas, title, search_title)
            
            # Save to session state
            st.session_state.passed_idea = best_idea
            
            st.subheader("Selected Best Idea")
            with st.container(border=True):
                st.markdown(best_idea)
                st.metric(label="Clout Score", value=f"{clout}%")

# BUTTON A: Transfer Logic
if st.session_state.passed_idea:
   if st.button("🚀 Send to Search Engine"):
    st.switch_page("pages/search_engine.py")
