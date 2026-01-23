# streamlit_app.py

import streamlit as st
from logic import generate_ideas_deepseek, select_and_score_openai
from openai import OpenAI
import json

st.set_page_config(page_title="AI Idea Dashboard", layout="centered")

# ==================== INITIALIZE SESSION STATE ====================
# Initialize all session state variables at the start
if "passed_idea" not in st.session_state:
    st.session_state.passed_idea = ""

# NEW: Initialize the specific search formats
if "search_payload" not in st.session_state:
    st.session_state.search_payload = {
        "general": [],
        "review": "",
        "thesis": ""
    }

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

# ==================== HELPER FUNCTION ====================
def transform_idea_for_search(client, idea):
    """
    Transforms the core idea into 3 specific search formats:
    1. 3 Short Sentences (General)
    2. Review Paper Query
    3. Thesis/KrishiKosh Query
    """
    prompt = f"""
    Analyze this research idea: "{idea}"
    
    Output a JSON object with exactly these keys:
    1. "general_sentences": A list of exactly 3 short, distinct, keyword-heavy sentences suitable for a search engine.
    2. "review_query": A single search query optimized to find "Review Papers" or "State of Art" on this topic.
    3. "thesis_query": A single search query optimized to find "Theses", "Dissertations" or "KrishiKosh" entries.
    
    Do not include markdown formatting, just raw JSON.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {
            "general_sentences": [idea, idea + " method", idea + " analysis"],
            "review_query": idea + " review paper",
            "thesis_query": idea + " thesis dissertation"
        }

# ==================== SIDEBAR - API KEYS ====================
with st.sidebar:
    st.header("🔑 API Settings")
    
    # Page 1 APIs
    st.subheader("Idea Generation")
    deepseek_key = st.text_input(
        "DeepSeek API Key", 
        type="password",
        value=st.session_state.deepseek_key,
        key="input_deepseek"
    )
    if deepseek_key:
        st.session_state.deepseek_key = deepseek_key
    
    openai_key = st.text_input(
        "OpenAI Key", 
        type="password",
        value=st.session_state.openai_key,
        key="input_openai"
    )
    if openai_key:
        st.session_state.openai_key = openai_key
    
    st.divider()
    
    # Page 2 APIs
    st.subheader("Search Engine")
    serp_key = st.text_input(
        "SerpAPI Key", 
        type="password",
        value=st.session_state.serpapi_key,
        key="input_serp"
    )
    if serp_key:
        st.session_state.serpapi_key = serp_key
    
    semantic_key = st.text_input(
        "Semantic Scholar Key (Optional)", 
        type="password",
        value=st.session_state.semantic_key,
        key="input_semantic"
    )
    if semantic_key:
        st.session_state.semantic_key = semantic_key
    
    st.divider()
    
    # Page 4 APIs
    st.subheader("PDF Download")
    core_key = st.text_input(
        "CORE API Key (Optional)", 
        type="password",
        value=st.session_state.core_key,
        key="input_core"
    )
    if core_key:
        st.session_state.core_key = core_key
    
    st.caption("💡 Get free CORE API: core.ac.uk")
    
    st.divider()
    
    # ==================== WORKFLOW STATUS ====================
    st.subheader("📊 Progress Tracker")
    
    progress_steps = []
    
    if st.session_state.get("passed_idea"):
        progress_steps.append("✅ Idea Generated")
    
    if st.session_state.get("search_payload") and st.session_state.search_payload["general"]:
        progress_steps.append("✅ Search Strategies Created")

    if st.session_state.get("all_papers"):
        progress_steps.append(f"✅ {len(st.session_state.all_papers)} Papers Found")
    
    if st.session_state.get("scored_papers"):
        progress_steps.append(f"✅ {len(st.session_state.scored_papers)} Papers Scored")
    
    if st.session_state.get("selected_paper_ids") and st.session_state.selected_paper_ids:
        progress_steps.append(f"✅ {len(st.session_state.selected_paper_ids)} Papers Selected")
    
    if st.session_state.get("download_results"):
        results = st.session_state.download_results
        progress_steps.append(f"✅ {results.get('success_count', 0)} PDFs Downloaded")
    
    if progress_steps:
        for step in progress_steps:
            st.success(step)
    else:
        st.info("👆 Enter API keys to start")

# ==================== MAIN CONTENT ====================

st.title("💡 Idea Generation Dashboard")

with st.container(border=True):
    title = st.text_input("Project Title", placeholder="e.g., Pest Management in Cotton")
    search_title = st.text_input("Search Title", placeholder="e.g., Integrated Pest Management")
    tongue_use = st.text_input("Tongue Use", placeholder="e.g., Technical, Academic")

# ==================== GENERATE LOGIC ====================
if st.button("Generate & Process Ideas", type="primary"):
    if not st.session_state.deepseek_key or not st.session_state.openai_key:
        st.error("❌ Please enter both DeepSeek and OpenAI API keys in the sidebar.")
    else:
        with st.spinner("🔄 Generating ideas (DeepSeek)..."):
            try:
                # 1. Generate Raw Ideas
                raw_ideas = generate_ideas_deepseek(
                    st.session_state.deepseek_key, 
                    title, 
                    search_title, 
                    tongue_use
                )
                
                # 2. Score and Select Best Idea
                best_idea, clout = select_and_score_openai(
                    st.session_state.openai_key, 
                    raw_ideas, 
                    title, 
                    search_title
                )
                
                # Save Main Idea
                st.session_state.passed_idea = best_idea
                
                # 3. NEW: Transform into Search Payloads
                with st.spinner("⚙️ Optimizing search strategies..."):
                    client = OpenAI(api_key=st.session_state.openai_key)
                    search_strategies = transform_idea_for_search(client, best_idea)
                    
                    st.session_state.search_payload = {
                        "general": search_strategies.get("general_sentences", []),
                        "review": search_strategies.get("review_query", ""),
                        "thesis": search_strategies.get("thesis_query", "")
                    }

                st.subheader("✨ Selected Best Idea")
                with st.container(border=True):
                    st.markdown(f"**Core Concept:** {best_idea}")
                    st.metric(label="Clout Score", value=f"{clout}%")
                    
                    st.divider()
                    st.write("**Search Engine Pre-sets Generated:**")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.info("General Search\n(3 Sentences)")
                    with c2:
                        st.warning("Review Paper\n(Strategy)")
                    with c3:
                        st.success("KrishiKosh Thesis\n(Strategy)")
                
                st.success("✅ Idea generated & search strategies prepared!")
                
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
        st.caption("⬆️ Generate idea first")

with nav_col2:
    if st.session_state.get("all_papers"):
        if st.button("⚖️ Score & Select", use_container_width=True):
            st.switch_page("pages/3_Sorting_and_Filtering.py")
    else:
        st.button("⚖️ Score & Select", disabled=True, use_container_width=True)
        st.caption("⬆️ Search papers first")

with nav_col3:
    if st.session_state.get("selected_paper_ids") and st.session_state.selected_paper_ids:
        if st.button("📥 Download PDFs", use_container_width=True, type="primary"):
            st.switch_page("pages/4_PDF_Downloader.py")
    else:
        st.button("📥 Download PDFs", disabled=True, use_container_width=True)
        st.caption("⬆️ Select papers first")

with nav_col4:
    if st.session_state.get("download_results"):
        results = st.session_state.download_results
        if st.button(f"📊 Results ({results.get('success_count', 0)})", use_container_width=True):
            st.switch_page("pages/4_PDF_Downloader.py")
    else:
        st.button("📊 Results", disabled=True, use_container_width=True)
        st.caption("⬆️ Download first")

# ==================== QUICK STATS ====================
if any(key in st.session_state for key in ["all_papers", "scored_papers", "selected_paper_ids"]):
    st.divider()
    st.subheader("📈 Workflow Statistics")
    
    stat1, stat2, stat3, stat4 = st.columns(4)
    
    with stat1:
        papers_found = len(st.session_state.get("all_papers", []))
        st.metric("Papers Found", papers_found)
    
    with stat2:
        papers_scored = len(st.session_state.get("scored_papers", []))
        st.metric("Papers Scored", papers_scored)
    
    with stat3:
        papers_selected = len(st.session_state.get("selected_paper_ids", set()))
        st.metric("Selected", papers_selected)
    
    with stat4:
        if "download_results" in st.session_state:
            downloaded = st.session_state.download_results.get("success_count", 0)
            st.metric("Downloaded", downloaded)
        else:
            st.metric("Downloaded", 0)

# ==================== FOOTER ====================
st.divider()
with st.expander("ℹ️ How to Use This App"):
    st.markdown("""
    **Workflow Steps:**
    1. **Enter API Keys** in the sidebar (they will be remembered)
    2. **Generate Idea** - Creates a core concept AND 3 specific search strategies (General, Review, Thesis).
    3. **Search Papers** - Uses the 3 strategies to find targeted papers.
    4. **Score & Select** - Go to Page 3 to filter and select relevant papers
    5. **Download PDFs** - Finally, download selected papers on Page 4
    """)
