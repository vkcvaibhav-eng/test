import streamlit as st
import json
from openai import OpenAI

# Page Configuration
st.set_page_config(page_title="Refinement & Scoring", layout="wide")

# --- AI Logic Functions ---

def llm_filter_stage_1(papers, idea, client):
    """Stage 1: GPT-4o-mini rough sort to find top 50."""
    # We send only titles to save tokens and speed up the 'rough' sort
    prompt = f"""
    Search Idea: {idea}
    Task: Review these papers and pick the TOP 50 most likely to be relevant. 
    Return ONLY a JSON list of indices.
    Example Format: {{"indices": [0, 5, 12, ...]}}
    
    Papers: {[{"idx": i, "title": p['title']} for i, p in enumerate(papers)]}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a research assistant. Return valid JSON only."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        indices = data.get("indices", [])
        return [papers[i] for i in indices if i < len(papers)]
    except Exception as e:
        st.error(f"Stage 1 Error: {e}")
        return []

def llm_score_stage_2(papers, idea, client):
    """Stage 2: GPT-4o final relevance scoring and classification."""
    refined_papers = []
    progress_bar = st.progress(0)
    
    for i, p in enumerate(papers):
        prompt = f"""
        Research Idea: {idea}
        Paper Title: {p['title']}
        Snippet: {p['snippet']}
        
        Task:
        1. Score relevance (0-100) based on the Idea.
        2. Classify as 'Research Article', 'Review Paper', or 'Thesis'.
        
        Rules for Classification:
        - 'Thesis': If it mentions dissertation, thesis, or university department.
        - 'Review Paper': If it mentions literature review, systematic review, or meta-analysis.
        - 'Research Article': Standard experimental or theoretical studies.

        Return ONLY JSON: {{"score": 85, "category": "Research Article"}}
        """
        try:
            res = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            data = json.loads(res.choices[0].message.content)
            
            # Update paper object
            p['relevance_score'] = data.get('score', 0)
            p['category'] = data.get('category', 'Research Article')
            
            # Only keep high relevance papers for the final pool
            if p['relevance_score'] >= 70: 
                refined_papers.append(p)
                
        except Exception as e:
            continue
            
        progress_bar.progress((i + 1) / len(papers))
    
    return refined_papers

# --- UI Layout ---

st.title("⚖️ Paper Scoring & Selection")

if "all_papers" not in st.session_state:
    st.warning("⚠️ No papers found. Please run the search on the Search Engine page first.")
else:
    papers = st.session_state.all_papers
    idea = st.session_state.search_idea
    openai_key = st.session_state.get("openai_key")

    if st.button("🚀 Start AI Refinement"):
        if not openai_key:
            st.error("Missing OpenAI API Key.")
        else:
            client = OpenAI(api_key=openai_key)
            
            # --- STAGE 1: ROUGH SORT ---
            with st.status("Stage 1: GPT-4o-mini filtering titles...", expanded=True) as status:
                top_50 = llm_filter_stage_1(papers[:300], idea, client)
                st.session_state.top_50 = top_50
                status.update(label=f"Stage 1 Complete: Found {len(top_50)} candidates.", state="complete")
            
            # --- STAGE 2: PRECISION SCORING ---
            with st.status("Stage 2: GPT-4o detailed classification...", expanded=True) as status:
                scored_papers = llm_score_stage_2(top_50, idea, client)
                st.session_state.scored_papers = scored_papers
                status.update(label="Stage 2 Complete!", state="complete")

    # --- RESULTS DISPLAY ---
    # We put this outside the button block so results stay on screen
    
    if "scored_papers" in st.session_state:
        all_scored = st.session_state.scored_papers
        
        # 1. Filter by category
        articles = [p for p in all_scored if p['category'] == "Research Article"]
        reviews = [p for p in all_scored if p['category'] == "Review Paper"]
        theses = [p for p in all_scored if p['category'] == "Thesis"]
        
        # 2. Sort by relevance within categories
        articles = sorted(articles, key=lambda x: x['relevance_score'], reverse=True)
        reviews = sorted(reviews, key=lambda x: x['relevance_score'], reverse=True)
        theses = sorted(theses, key=lambda x: x['relevance_score'], reverse=True)

        # 3. Final Selection Logic (5 Research, 2 Reviews, 3 Theses)
        final_selection = articles[:5] + reviews[:2] + theses[:3]

        st.divider()
        st.header("🎯 Final Paper Selection")
        
        # Show Metrics for Transparency
        m1, m2, m3 = st.columns(3)
        m1.metric("Research Articles", f"{len(articles[:5])}/5")
        m2.metric("Review Papers", f"{len(reviews[:2])}/2")
        m3.metric("Theses/Dissertations", f"{len(theses[:3])}/3")

        if len(final_selection) < 10:
            st.warning(f"Could only find {len(final_selection)} high-relevance papers matching your mix. Try broadening your search.")

        # 4. Display the papers
        for p in final_selection:
            with st.expander(f"[{p['category']}] {p['title']} (Score: {p['relevance_score']}%)"):
                st.markdown(f"**Relevance Score:** {p['relevance_score']}/100")
                st.write(p['snippet'])
                st.markdown(f"[🔗 Read Full Paper]({p['link']})")

    # Optional: Display the Stage 1 results if Stage 2 hasn't run or if user wants to see them
    elif "top_50" in st.session_state:
        with st.expander("Show Stage 1 Results (Candidate Pool)"):
            for p in st.session_state.top_50:
                st.write(f"- {p['title']}")
