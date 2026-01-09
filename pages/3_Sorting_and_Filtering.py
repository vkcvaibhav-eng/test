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
        # Add a unique ID for selection tracking
        p['id'] = f"{p['category']}_{i}" 
        refined_papers.append(p)
        progress_bar.progress((i + 1) / len(papers))
    return refined_papers

# --- UI SECTION ---

st.title("⚖️ Paper Scoring & Selection Dashboard")

# Initialize selection state if it doesn't exist
if "selected_paper_ids" not in st.session_state:
    st.session_state.selected_paper_ids = set()

if "all_papers" not in st.session_state or not st.session_state.all_papers:
    st.warning("⚠️ No papers found. Please run the search on the 'Search Engine' page first.")
    if st.button("Back to Search"):
        st.switch_page("search_engine.py")
else:
    papers = st.session_state.all_papers
    idea = st.session_state.get("search_idea", "General Research")
    openai_key = st.session_state.get("openai_key")

    st.info(f"Loaded {len(papers)} papers from search for idea: **{idea}**")

    if st.button("🚀 Start AI Refinement"):
        if not openai_key:
            st.error("Please provide an OpenAI API Key.")
        else:
            client = OpenAI(api_key=openai_key)
            with st.status("Processing...", expanded=True):
                top_50 = llm_filter_stage_1(papers[:300], idea, client)
                scored_papers = llm_score_stage_2(top_50, idea, client)
                st.session_state.scored_papers = scored_papers
                # Reset selections on new run
                st.session_state.selected_paper_ids = set()
            st.rerun()

    # --- DISPLAY LOGIC ---
    if "scored_papers" in st.session_state:
        scored = st.session_state.scored_papers
        
        categories = {
            "Research Article": {"label": "Research Papers", "color": "blue"},
            "Review Paper": {"label": "Review Papers", "color": "green"},
            "Thesis": {"label": "Theses", "color": "orange"}
        }

        for cat_key, cat_info in categories.items():
            st.header(f"📂 {cat_info['label']}")
            
            # Filter papers for this category and sort by score
            cat_papers = sorted(
                [p for p in scored if p['category'] == cat_key], 
                key=lambda x: x.get('relevance_score', 0), 
                reverse=True
            )

            col_selected, col_candidates = st.columns([1, 1])

            with col_selected:
                st.subheader("✅ Selected")
                selected_in_cat = [p for p in cat_papers if p['id'] in st.session_state.selected_paper_ids]
                if not selected_in_cat:
                    st.caption("No papers selected yet.")
                for p in selected_in_cat:
                    st.info(f"**{p['relevance_score']}%** - {p['title']}")

            with col_candidates:
                st.subheader("🔍 Best Candidates (Not Selected)")
                remaining_in_cat = [p for p in cat_papers if p['id'] not in st.session_state.selected_paper_ids]
                
                # We limit the view as requested (e.g., top 30 research, 5 reviews, 5 thesis)
                limit = 30 if cat_key == "Research Article" else 5
                
                for p in remaining_in_cat[:limit]:
                    # Using checkboxes to move papers
                    if st.checkbox(f"{p['relevance_score']}% - {p['title']}", key=f"chk_{p['id']}"):
                        st.session_state.selected_paper_ids.add(p['id'])
                        st.rerun()

            st.divider()

        # Full list view at the bottom
        with st.expander("📋 View All Scored Data"):
            for p in scored:
                st.write(f"**{p['relevance_score']}%** | {p['category']} | {p['title']}")
