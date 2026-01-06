import streamlit as st
import json
from openai import OpenAI

# Page Configuration
st.set_page_config(page_title="Refinement & Scoring", layout="wide")

# --- CORE FUNCTIONS ---

def llm_filter_stage_1(papers, idea, client):
    """Stage 1: GPT-4o-mini rough sort."""
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
    """Stage 2: GPT-4o precision scoring."""
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
        try:
            res = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            data = json.loads(res.choices[0].message.content)
            # Ensure we update the actual paper object
            p_updated = p.copy()
            p_updated['relevance_score'] = data.get('score', 0)
            p_updated['category'] = data.get('category', 'Research Article')
            refined_papers.append(p_updated)
        except:
            continue
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
        
        with st.status("Processing Stage 1...", expanded=True):
            st.session_state.top_50 = llm_filter_stage_1(papers[:300], idea, client)
        
        with st.status("Processing Stage 2...", expanded=True):
            # We save directly to session state so it persists!
            st.session_state.scored_papers = llm_score_stage_2(st.session_state.top_50, idea, client)
        
        st.rerun() # Refresh to show results

    # --- SELECTION & DISPLAY LOGIC ---
    if "scored_papers" in st.session_state:
        scored = st.session_state.scored_papers
        
        # We use .lower() and 'in' to make matching more flexible (e.g., "Research paper" matches "research article")
        research_articles = sorted([p for p in scored if "research" in p['category'].lower()], 
                                   key=lambda x: x['relevance_score'], reverse=True)
        
        review_papers = sorted([p for p in scored if "review" in p['category'].lower()], 
                               key=lambda x: x['relevance_score'], reverse=True)
        
        theses = sorted([p for p in scored if "thesis" in p['category'].lower() or "dissertation" in p['category'].lower()], 
                        key=lambda x: x['relevance_score'], reverse=True)

        # Precise Selection (10/2/2)
        final_selection = research_articles[:10] + review_papers[:2] + theses[:2]

        st.divider()
        st.header("🎯 Final Selection")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Research Articles", f"{len(research_articles[:10])}/10")
        col2.metric("Review Papers", f"{len(review_papers[:2])}/2")
        col3.metric("Theses/Dissertations", f"{len(theses[:2])}/2")

        if not final_selection:
            st.error("The AI scored the papers, but none met the relevance or category criteria. Try lowering the score threshold.")
        else:
            for p in final_selection:
                with st.expander(f"[{p['category']}] {p['title']} - Score: {p['relevance_score']}%"):
                    st.write(p.get('snippet', 'No snippet.'))
                    st.markdown(f"[Link to Paper]({p.get('link', '#')})")

    # Display Stage 1 results if they exist
    if "top_50" in st.session_state:
        with st.expander("View Stage 1 Candidates (Initial 50)"):
            for p in st.session_state.top_50:
                st.write(f"• {p['title']}")
