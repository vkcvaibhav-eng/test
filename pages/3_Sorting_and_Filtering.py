import streamlit as st
import json
from openai import OpenAI

# Page Configuration
st.set_page_config(page_title="Refinement & Scoring", layout="wide")

# --- CORE FUNCTIONS ---

def llm_filter_stage_1(papers, idea, client):
    """Stage 1: GPT-4o-mini rough sort to find top 50."""
    prompt = f"""
    Search Idea: {idea}
    Task: Review these papers and pick the TOP 50 most likely to be relevant. 
    Return ONLY a JSON object with a key "indices" containing a list of numbers.
    Papers: {[{'idx': i, 'title': p['title']} for i, p in enumerate(papers)]}
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    data = json.loads(response.choices[0].message.content)
    indices = data.get("indices", [])
    return [papers[i] for i in indices if i < len(papers)]

def llm_score_stage_2(papers, idea, client):
    """Stage 2: GPT-4o final relevance scoring and classification."""
    refined_papers = []
    progress_bar = st.progress(0)
    for i, p in enumerate(papers):
        prompt = f"""
        Idea: {idea}
        Paper Title: {p['title']}
        Snippet: {p.get('snippet', 'N/A')}
        Task: 
        1. Score relevance (0-100).
        2. Classify as 'Research Article', 'Review Paper', or 'Thesis'.
        Return JSON: {{"score": 85, "category": "Research Article"}}
        """
        res = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        data = json.loads(res.choices[0].message.content)
        p['relevance_score'] = data.get('score', 0)
        p['category'] = data.get('category', 'Research Article')
        refined_papers.append(p)
        progress_bar.progress((i + 1) / len(papers))
    return refined_papers

# --- UI SECTION ---

st.title("⚖️ Paper Scoring & Selection Dashboard")

# 1. Check if data exists from the Search Engine
if "all_papers" not in st.session_state or not st.session_state.all_papers:
    st.warning("⚠️ No papers found. Please run the search on the 'Search Engine' page first.")
    if st.button("Back to Search"):
        st.switch_page("search_engine.py") # Ensure the filename matches exactly
else:
    papers = st.session_state.all_papers
    idea = st.session_state.get("search_idea", "General Research")
    openai_key = st.session_state.get("openai_key")

    st.info(f"Loaded {len(papers)} papers from search for idea: **{idea}**")

    # Action Button
    if st.button("🚀 Start AI Refinement"):
        if not openai_key:
            st.error("Please provide an OpenAI API Key in the Search Engine settings.")
        else:
            client = OpenAI(api_key=openai_key)
            
            with st.status("Stage 1: Filtering Top Candidates...", expanded=True):
                # Filters down to top 50
                top_50 = llm_filter_stage_1(papers[:300], idea, client)
                st.session_state.top_50 = top_50
            
            with st.status("Stage 2: Precision Scoring...", expanded=True):
                # Assigns scores and categories
                scored_papers = llm_score_stage_2(top_50, idea, client)
                st.session_state.scored_papers = scored_papers
            st.rerun()

    # 2. Display Results if Scored
    if "scored_papers" in st.session_state:
        scored = st.session_state.scored_papers
        
        # Categorization logic
        research = sorted([p for p in scored if p['category'] == "Research Article"], 
                          key=lambda x: x.get('relevance_score', 0), reverse=True)
        reviews = sorted([p for p in scored if p['category'] == "Review Paper"], 
                         key=lambda x: x.get('relevance_score', 0), reverse=True)
        theses = sorted([p for p in scored if p['category'] == "Thesis"], 
                        key=lambda x: x.get('relevance_score', 0), reverse=True)

        st.header("📍 Selected Sources")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader(f"Research ({len(research)})")
            for p in research[:10]:
                st.info(f"**{p['relevance_score']}%** - {p['title']}")

        with col2:
            st.subheader(f"Reviews ({len(reviews)})")
            for p in reviews[:5]:
                st.success(f"**{p['relevance_score']}%** - {p['title']}")

        with col3:
            st.subheader(f"Theses ({len(theses)})")
            for p in theses[:5]:
                st.warning(f"**{p['relevance_score']}%** - {p['title']}")

        st.divider()

        # 3. Manual Selection and Full Pool
        st.header("📋 All Scored Papers")
        for i, p in enumerate(scored):
            with st.expander(f"{p['relevance_score']}% | {p['category']} | {p['title']}"):
                st.write(p.get('snippet', 'No description available.'))
                st.write(f"[Source Link]({p.get('link', '#')})")
