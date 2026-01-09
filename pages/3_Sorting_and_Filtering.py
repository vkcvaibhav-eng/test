import streamlit as st
import json
from openai import OpenAI

# Page Configuration
st.set_page_config(page_title="Refinement & Scoring", layout="wide")

# --- CORE FUNCTIONS (Logic from original file) ---

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
        p['relevance_score'] = data.get('score', 0)
        p['category'] = data.get('category', 'Research Article')
        refined_papers.append(p)
    return refined_papers

# --- UI SECTION (Integrated Dashboard) ---

st.title("⚖️ Paper Scoring & Selection Dashboard")

# Initialize Session States
if "manual_selection" not in st.session_state:
    st.session_state.manual_selection = []

if "all_papers" not in st.session_state:
    st.warning("Please run the search on the Search Engine page first.")
else:
    papers = st.session_state.all_papers
    idea = st.session_state.search_idea
    openai_key = st.session_state.get("openai_key")

    # Run AI Process
    if st.button("🚀 Start AI Refinement"):
        if not openai_key:
            st.error("Please provide an OpenAI API Key in the settings.")
        else:
            client = OpenAI(api_key=openai_key)
            
            with st.status("Stage 1: Rough Sorting (GPT-4o-mini)..."):
                # Filters down to top 50 based on original logic
                top_50 = llm_filter_stage_1(papers[:300], idea, client)
                st.session_state.top_50 = top_50
            
            with st.status("Stage 2: Precision Scoring (GPT-4o)..."):
                # Assigns scores and categories
                scored_papers = llm_score_stage_2(top_50, idea, client)
                st.session_state.scored_papers = scored_papers

    # Display Dashboard if papers have been scored
    if "scored_papers" in st.session_state:
        scored = st.session_state.scored_papers
        
        # 1. CATEGORIZATION & SORTING
        # Sorts by highest relevance score first
        research = sorted([p for p in scored if p['category'] == "Research Article"], 
                          key=lambda x: x['relevance_score'], reverse=True)
        reviews = sorted([p for p in scored if p['category'] == "Review Paper"], 
                         key=lambda x: x['relevance_score'], reverse=True)
        theses = sorted([p for p in scored if p['category'] == "Thesis"], 
                        key=lambda x: x['relevance_score'], reverse=True)

        st.header("📍 Selected Sources")
        
        # 2. TOP SELECTION COLUMNS (Automated based on your sketch)
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader(f"Research Papers ({min(len(research), 10)})")
            for i, p in enumerate(research[:10]): # Top 10
                st.info(f"**{i+1}.** {p['title']}  \n*Score: {p['relevance_score']}%*")

        with col2:
            st.subheader(f"Review Papers ({min(len(reviews), 2)})")
            for i, p in enumerate(reviews[:2]): # Top 2
                st.success(f"**{i+1}.** {p['title']}  \n*Score: {p['relevance_score']}%*")

        with col3:
            st.subheader(f"Theses ({min(len(theses), 3)})") # Top 3 based on your sketch
            for i, p in enumerate(theses[:3]):
                st.warning(f"**{i+1}.** {p['title']}  \n*Score: {p['relevance_score']}%*")

        st.divider()

        # 3. MANUALLY SELECTED SECTION
        st.subheader("➡️ Manually Selected")
        if st.session_state.manual_selection:
            for i, p in enumerate(st.session_state.manual_selection):
                with st.expander(f"✅ {p['title']} ({p['category']})"):
                    st.write(p.get('snippet', 'No snippet available.'))
                    if st.button("Remove", key=f"remove_{i}"):
                        st.session_state.manual_selection.pop(i)
                        st.rerun()
        else:
            st.info("No papers manually selected yet. Select papers from the list below.")

        st.divider()

        # 4. ALL SOURCES LIST (The Pool for Manual Selection)
        st.header("📋 All Sources (Top 50 Pool)")
        st.write("Click 'Add' to move a paper to the **Manually Selected** section.")
        
        for i, p in enumerate(scored):
            with st.container(border=True):
                c_text, c_btn = st.columns([0.85, 0.15])
                with c_text:
                    st.markdown(f"**{i+1}. {p['title']}**")
                    st.caption(f"Category: {p['category']} | Relevance: {p['relevance_score']}%")
                with c_btn:
                    if st.button("➕ Add", key=f"add_{i}"):
                        # Check if already added to avoid duplicates
                        if p['title'] not in [x['title'] for x in st.session_state.manual_selection]:
                            st.session_state.manual_selection.append(p)
                            st.rerun()
                        else:
                            st.toast("Already added!")

    # Show original Stage 1 candidates as a backup view
    elif "top_50" in st.session_state:
        with st.expander("View Stage 1 Candidates (Initial 50)"):
            for p in st.session_state.top_50:
                st.write(f"• {p['title']}")
