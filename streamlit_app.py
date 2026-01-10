# streamlit_app.py

import streamlit as st
from logic import generate_ideas_deepseek, select_and_score_openai

st.set_page_config(page_title="AI Idea Dashboard", layout="centered")

if "passed_idea" not in st.session_state:
    st.session_state.passed_idea = ""

with st.sidebar:
    st.header("🔑 API Settings")
    
    # Page 1 APIs
    deepseek_key = st.text_input("DeepSeek API Key", type="password")
    openai_key = st.text_input("OpenAI Key", type="password")
    
    st.divider()
    
    # Page 2 APIs
    st.subheader("Search Engine APIs")
    serp_key = st.text_input("SerpAPI Key", type="password")
    semantic_key = st.text_input("Semantic Scholar Key (Optional)", type="password")
    
    st.divider()
    
    # Page 4 APIs
    st.subheader("Download APIs (Optional)")
    core_key = st.text_input("CORE API Key (Optional)", type="password")
    
    st.caption("💡 Get free CORE API key from core.ac.uk")
    
    # Save API keys to session state for other pages
    if serp_key:
        st.session_state.serpapi_key = serp_key
    if semantic_key:
        st.session_state.semantic_key = semantic_key
    if core_key:
        st.session_state.core_key = core_key
    
    st.divider()
    
    # Workflow Status
    st.subheader("📊 Workflow Progress")
    
    if st.session_state.get("passed_idea"):
        st.success("✅ Idea Generated")
    
    if "all_papers" in st.session_state:
        st.success(f"✅ {len(st.session_state.all_papers)} Papers Found")
    
    if "scored_papers" in st.session_state:
        st.success(f"✅ {len(st.session_state.scored_papers)} Papers Scored")
    
    if "selected_paper_ids" in st.session_state and st.session_state.selected_paper_ids:
        st.success(f"✅ {len(st.session_state.selected_paper_ids)} Papers Selected")
    
    if "download_results" in st.session_state:
        results = st.session_state.download_results
        st.metric("📥 PDFs Downloaded", results.get('success_count', 0))
        st.metric("❌ Failed", results.get('failed_count', 0))

st.title("💡 Idea Generation Dashboard")

with st.container(border=True):
    title = st.text_input("Project Title")
    search_title = st.text_input("Search Title")
    tongue_use = st.text_input("Tongue Use")

# --- CLEAN GENERATE LOGIC ---
if st.button("Generate & Process", type="primary"):
    if not deepseek_key or not openai_key:
        st.error("Please enter both API keys.")
    else:
        with st.spinner("Processing..."):
            raw_ideas = generate_ideas_deepseek(deepseek_key, title, search_title, tongue_use)
            best_idea, clout = select_and_score_openai(openai_key, raw_ideas, title, search_title)
            
            # Save for Page 2 and Page 3
            st.session_state.passed_idea = best_idea
            st.session_state.openai_key = openai_key
            
            st.subheader("Selected Best Idea")
            with st.container(border=True):
                st.markdown(best_idea)
                st.metric(label="Clout Score", value=f"{clout}%")

# --- NAVIGATION SECTION ---
st.divider()
st.subheader("🚀 Workflow Navigation")

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.session_state.get("passed_idea"):
        if st.button("📚 Search Papers", use_container_width=True):
            st.switch_page("pages/search_engine.py")
    else:
        st.button("📚 Search Papers", disabled=True, use_container_width=True)
        st.caption("Generate idea first")

with col2:
    if "all_papers" in st.session_state:
        if st.button("⚖️ Score & Filter", use_container_width=True):
            st.switch_page("pages/3_Sorting_and_Filtering.py")
    else:
        st.button("⚖️ Score & Filter", disabled=True, use_container_width=True)
        st.caption("Run search first")

with col3:
    if "selected_paper_ids" in st.session_state and st.session_state.selected_paper_ids:
        if st.button("📥 Download PDFs", use_container_width=True, type="primary"):
            st.switch_page("pages/4_PDF_Downloader.py")
    else:
        st.button("📥 Download PDFs", disabled=True, use_container_width=True)
        st.caption("Select papers first")

with col4:
    if "download_results" in st.session_state:
        results = st.session_state.download_results
        if st.button(f"📊 View Results ({results['success_count']})", use_container_width=True):
            st.switch_page("pages/4_PDF_Downloader.py")
    else:
        st.button("📊 View Results", disabled=True, use_container_width=True)
        st.caption("Download first")

# --- QUICK STATS ---
if any(key in st.session_state for key in ["all_papers", "scored_papers", "selected_paper_ids"]):
    st.divider()
    st.subheader("📈 Quick Stats")
    
    stat_col1, stat_col2, stat_col3 = st.columns(3)
    
    with stat_col1:
        papers_found = len(st.session_state.get("all_papers", []))
        st.metric("Papers Found", papers_found)
    
    with stat_col2:
        papers_scored = len(st.session_state.get("scored_papers", []))
        st.metric("Papers Scored", papers_scored)
    
    with stat_col3:
        papers_selected = len(st.session_state.get("selected_paper_ids", []))
        st.metric("Papers Selected", papers_selected)
