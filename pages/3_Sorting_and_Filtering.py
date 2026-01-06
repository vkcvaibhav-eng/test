import streamlit as st
import json
from openai import OpenAI

# Page Configuration
st.set_page_config(page_title="Refinement & Scoring", layout="wide")

# --- CORE FUNCTIONS (Unchanged as requested) ---

def llm_filter_stage_1(papers, idea, client):
    """Stage 1: GPT-4o-mini rough sort to find top 50."""
    prompt = f"""
    Search Idea: {idea}
    Task: Review these papers and pick the TOP 50 most likely to be relevant. 
    Return ONLY a JSON list of indices.
    Papers: {[{"idx": i, "title": p['title']} for i, p in enumerate(papers)]}
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    indices = json.loads(response.choices[0].message.content).get("indices", [])
    return [papers[i] for i in indices if i < len(papers)]

def llm_score_stage_2(papers, idea, client):
    """Stage 2: GPT-4o final relevance scoring and classification."""
    refined_papers = []
    for p in papers:
        prompt = f"""
        Idea: {idea}
        Paper Title: {p['title']}
        Snippet: {p['snippet']}
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
        # Store metadata regardless of score; we filter in the UI section
        p['relevance_score'] = data.get('score', 0)
        p['category'] = data.get('category', 'Research Article')
        refined_papers.append(p)
    return refined_papers

# --- UI SECTION ---

st.title("⚖️ Paper Scoring & Selection")

if "all_papers" not in st.session_state:
    st.warning("Please run the search on the Search Engine page first.")
else:
    papers = st.session_state.all_papers
    idea = st.session_state.search_idea
    openai_key = st.session_state.get("openai_key")

    if st.button("🚀 Start AI Refinement"):
        client = OpenAI(api_key=openai_key)
        
        with st.status("Stage 1: Rough Sorting (GPT-4o-mini)..."):
            top_50 = llm_filter_stage_1(papers[:300], idea, client)
            st.session_state.top_50 = top_50
        
        with st.status("Stage 2: Precision Scoring (GPT-4o)..."):
            scored_papers = llm_score_stage_2(top_50, idea, client)
            st.session_state.scored_papers = scored_papers

    # --- UPDATED SELECTION & DISPLAY LOGIC ---
    if "scored_papers" in st.session_state:
        scored = st.session_state.scored_papers
        
        # 1. Filter and Sort by Category (Highest scores first)
        research_articles = sorted([p for p in scored if p['category'] == "Research Article"], 
                                   key=lambda x: x['relevance_score'], reverse=True)
        
        review_papers = sorted([p for p in scored if p['category'] == "Review Paper"], 
                               key=lambda x: x['relevance_score'], reverse=True)
        
        theses = sorted([p for p in scored if p['category'] == "Thesis"], 
                        key=lambda x: x['relevance_score'], reverse=True)

        # 2. Precise Selection based on your requirements
        # Target: 10 Research, 2 Reviews, 2 Thesis
        final_articles = research_articles[:10]
        final_reviews = review_papers[:2]
        final_theses = theses[:2]
        
        all_final_papers = final_articles + final_reviews + final_theses

        st.divider()
        st.header("🎯 Final Selection")
        
        # Dashboard for selection status
        col1, col2, col3 = st.columns(3)
        col1.metric("Research Articles", f"{len(final_articles)}/10")
        col2.metric("Review Papers", f"{len(final_reviews)}/2")
        col3.metric("Theses/Dissertations", f"{len(final_theses)}/2")

        if len(all_final_papers) == 0:
            st.error("No papers matched the criteria. Try a different search idea.")
        else:
            # Displaying the papers
            for p in all_final_papers:
                with st.expander(f"[{p['category']}] {p['title']} - Score: {p['relevance_score']}%"):
                    st.write(f"**Source:** {p.get('link', 'N/A')}")
                    st.write(p.get('snippet', 'No snippet available.'))
                    st.markdown(f"[Link to Paper]({p.get('link', '#')})")

    # Show Stage 1 Candidates (Minimize if wanted)
    if "top_50" in st.session_state:
        with st.expander("View Stage 1 Candidates (Initial 50)"):
            for p in st.session_state.top_50:
                st.write(f"• {p['title']}")
