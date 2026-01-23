# streamlit_app.py

import streamlit as st
from logic import generate_ideas_deepseek, select_and_score_openai

st.set_page_config(page_title="AI Idea Dashboard", layout="centered")

# ==================== INITIALIZE SESSION STATE ====================
if "passed_idea" not in st.session_state:
    st.session_state.passed_idea = ""
if "deepseek_key" not in st.session_state:
    st.session_state.deepseek_key = ""
if "openai_key" not in st.session_state:
    st.session_state.openai_key = ""
if "serpapi_key" not in st.session_state:
    st.session_state.serpapi_key = ""
if "semantic_key" not in st.session_state:
    st.session_state.semantic_key = ""
if "core_key" not in st.session_state:
    st.session_state.core_key = ""

# ==================== SIDEBAR - API KEYS ====================
with st.sidebar:
    st.header("🔑 API Settings")
    
    # Page 1 APIs
    st.subheader("Idea Generation")
    deepseek_key = st.text_input("DeepSeek API Key", type="password", value=st.session_state.deepseek_key, key="input_deepseek")
    if deepseek_key: st.session_state.deepseek_key = deepseek_key
    
    openai_key = st.text_input("OpenAI Key", type="password", value=st.session_state.openai_key, key="input_openai")
    if openai_key: st.session_state.openai_key = openai_key
    
    st.divider()
    
    # Page 2 APIs
    st.subheader("Search Engine")
    serp_key = st.text_input("SerpAPI Key", type="password", value=st.session_state.serpapi_key, key="input_serp")
    if serp_key: st.session_state.serpapi_key = serp_key
    
    semantic_key = st.text_input("Semantic Scholar Key (Optional)", type="password", value=st.session_state.semantic_key, key="input_semantic")
    if semantic_key: st.session_state.semantic_key = semantic_key
    
    st.divider()
    
    # Page 4 APIs
    st.subheader("PDF Download")
    core_key = st.text_input("CORE API Key (Optional)", type="password", value=st.session_state.core_key, key="input_core")
    if core_key: st.session_state.core_key = core_key

# ==================== MAIN CONTENT ====================
st.title("💡 Idea Generation Dashboard")
st.markdown("Generates a **Core Research Idea** that will be used to find Research Papers, Review Papers, and Theses.")

with st.container(border=True):
    title = st.text_input("Project Title", placeholder="e.g., Pest Management in Cotton")
    search_title = st.text_input("Search Title", placeholder="e.g., Integrated Pest Management")
    tongue_use = st.text_input("Tongue Use", placeholder="e.g., Technical, Academic")

# ==================== GENERATE LOGIC ====================
if st.button("Generate & Process Ideas", type="primary"):
    if not st.session_state.deepseek_key or not st.session_state.openai_key:
        st.error("❌ Please enter both DeepSeek and OpenAI API keys in the sidebar.")
    else:
        with st.spinner("🔄 Generating core idea..."):
            try:
                # Logic assumes generation of ONE strong core idea
                raw_ideas = generate_ideas_deepseek(st.session_state.deepseek_key, title, search_title, tongue_use)
                best_idea, clout = select_and_score_openai(st.session_state.openai_key, raw_ideas, title, search_title)
                
                # Save to session state
                st.session_state.passed_idea = best_idea
                
                st.subheader("✨ Selected Core Idea")
                with st.container(border=True):
                    st.markdown(best_idea)
                    st.metric(label="Clout Score", value=f"{clout}%")
                    st.caption("This core idea will automatically adapt for Research, Review, and Thesis searches.")
                
                st.success("✅ Idea generated! Proceed to 'Search Papers'.")
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

# ==================== NAVIGATION ====================
st.divider()
st.subheader("🚀 Workflow Navigation")

nav_col1, nav_col2, nav_col3, nav_col4 = st.columns(4)

with nav_col1:
    if st.session_state.get("passed_idea"):
        if st.button("📚 Search Papers", use_container_width=True):
            st.switch_page("pages/search_engine.py")
    else:
        st.button("📚 Search Papers", disabled=True, use_container_width=True)

with nav_col2:
    if st.session_state.get("all_papers"):
        if st.button("⚖️ Score & Select", use_container_width=True):
            st.switch_page("pages/3_Sorting_and_Filtering.py")
    else:
        st.button("⚖️ Score & Select", disabled=True, use_container_width=True)

with nav_col3:
    if st.session_state.get("selected_paper_ids"):
        if st.button("📥 Download PDFs", use_container_width=True, type="primary"):
            st.switch_page("pages/4_PDF_Downloader.py")
    else:
        st.button("📥 Download PDFs", disabled=True, use_container_width=True)

with nav_col4:
    if st.session_state.get("download_results"):
        if st.button("📊 Results", use_container_width=True):
            st.switch_page("pages/4_PDF_Downloader.py")
    else:
        st.button("📊 Results", disabled=True, use_container_width=True)
