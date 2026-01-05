import streamlit as st
import json
from openai import OpenAI

st.set_page_config(page_title="Refinement & Scoring", layout="wide")

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
        if data['score'] >= 80:
            p['relevance_score'] = data['score']
            p['category'] = data['category']
            refined_papers.append(p)
    return refined_papers

# --- UI ---
st.title("⚖️ Paper Scoring & Selection")

if "all_papers" not in st.session_state:
    st.warning("Please run the search on the Search Engine page first.")
else:
    papers = st.session_state.all_papers
    idea = st.session_state.search_idea
    openai_key = st.session_state.get("openai_key") # Ensure this is saved in search_engine.py

    if st.button("Start AI Refinement"):
        client = OpenAI(api_key=openai_key)
        
        with st.status("Stage 1: Rough Sorting (GPT-4o-mini)..."):
            top_50 = llm_filter_stage_1(papers[:300], idea, client)
        
        with st.status("Stage 2: Precision Scoring (GPT-4o)..."):
            scored_papers = llm_score_stage_2(top_50, idea, client)

        # FINAL SELECTION LOGIC
        reviews = [p for p in scored_papers if p['category'] == "Review Paper"][:2]
        theses = [p for p in scored_papers if p['category'] == "Thesis"][:3]
        articles = [p for p in scored_papers if p['category'] == "Research Article"]
        
        if len(articles) < 10:
            st.error(f"Only found {len(articles)} research articles with >80% relevance. Min 10 required.")
        else:
            final_selection = reviews + theses + articles[:15] # Taking top articles
            st.success(f"Final Selection Complete: {len(final_selection)} papers.")
            
            for p in final_selection:
                with st.expander(f"[{p['category']}] {p['title']} - Score: {p['relevance_score']}%"):
                    st.write(p['snippet'])
                    st.write(f"[Link]({p['link']})")
