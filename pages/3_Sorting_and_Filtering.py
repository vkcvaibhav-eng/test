import streamlit as st
import json
import hashlib
from openai import OpenAI

# Page Configuration
st.set_page_config(page_title="Refinement & Scoring", layout="wide")

# --- CORE FUNCTIONS ---

def generate_paper_id(title):
    """Generates a stable unique ID based on the title text."""
    return hashlib.md5(title.encode('utf-8')).hexdigest()

def llm_filter_stage_1(papers, idea, client):
    """Stage 1: GPT-4o-mini rough sort to find top 50."""
    prompt = f"""
    Search Idea: {idea}
    Task: Review these papers and pick the TOP 50 most likely to be relevant. 
    Return ONLY a JSON object with a key "indices" containing a list of numbers.
    Papers: {[{'idx': i, 'title': p['title'], 'type': p.get('type', 'Unknown')} for i, p in enumerate(papers)]}
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    data = json.loads(response.choices[0].message.content)
    
    # FIX 1: Use set() to remove duplicate indices returned by the LLM
    indices = sorted(list(set(data.get("indices", [])))) 
    
    return [papers[i] for i in indices if i < len(papers)]

def llm_score_stage_2(papers, idea, client):
    """Stage 2: GPT-4o final relevance scoring and classification."""
    refined_papers = []
    progress_bar = st.progress(0)
    
    for i, p in enumerate(papers):
        # DETECT EXISTING CATEGORY FROM SEARCH ENGINE
        existing_type = p.get('type', None) 
        
        prompt = f"""
        Idea: {idea}
        Paper Title: {p['title']}
        Snippet: {p.get('snippet', 'N/A')}
        Existing Category: {existing_type if existing_type else "Unknown"}
        
        Task: 
        1. Score relevance (0-100).
        2. Classify ONLY as one of: 'Research', 'Review', 'Thesis'.
        IMPORTANT: If 'Existing Category' is provided (Review or Thesis), YOU MUST KEEP IT unless it is clearly wrong.
        
        Return JSON: {{"score": 85, "category": "Research"}}
        """
        
        try:
            res = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            data = json.loads(res.choices[0].message.content)
            
            # Create a new dict object
            new_paper = p.copy() 
            new_paper['relevance_score'] = data.get('score', 0)
            
            # LOGIC: If search engine explicitly said "Thesis" or "Review", prioritize that over LLM guess
            if existing_type in ['Thesis', 'Review']:
                new_paper['category'] = existing_type
            else:
                new_paper['category'] = data.get('category', 'Research')
            
            # FIX 2: Stable ID
            new_paper['id'] = f"{i}_{generate_paper_id(p['title'])}"
            
            refined_papers.append(new_paper)
            
        except Exception as e:
            pass # Skip on error
            
        progress_bar.progress((i + 1) / len(papers))
        
    return refined_papers

# --- UI SECTION ---

st.title("⚖️ Paper Scoring & Selection Dashboard")

if "selected_paper_ids" not in st.session_state:
    st.session_state.selected_paper_ids = set()

if "all_papers" not in st.session_state or not st.session_state.all_papers:
    st.warning("⚠️ No papers found. Please run the search on the 'Search Engine' page first.")
    if st.button("Back to Search"):
        st.switch_page("pages/search_engine.py")
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
                # Only take the first 300 to stay within context limits
                top_candidates = llm_filter_stage_1(papers[:300], idea, client)
                scored_papers = llm_score_stage_2(top_candidates, idea, client)
                st.session_state.scored_papers = scored_papers
                st.session_state.selected_paper_ids = set() 
            st.rerun()

    # --- DISPLAY LOGIC ---
    if "scored_papers" in st.session_state:
        scored = st.session_state.scored_papers
        
        # DEFINED CATEGORIES (Must match Search Engine & LLM Output)
        categories = [
            {"key": "Research", "label": "Research Papers", "limit": 30},
            {"key": "Review", "label": "Review Papers", "limit": 5},
            {"key": "Thesis", "label": "Theses", "limit": 5}
        ]

        for cat in categories:
            st.header(f"📂 {cat['label']}")
            
            # Filter papers by category
            cat_papers = sorted(
                [p for p in scored if p.get('category') == cat['key']], 
                key=lambda x: x.get('relevance_score', 0), 
                reverse=True
            )

            col_selected, col_candidates = st.columns([1, 1])

            with col_selected:
                st.subheader(f"✅ Selected {cat['label']}")
                selected_in_cat = [p for p in cat_papers if p['id'] in st.session_state.selected_paper_ids]
                
                if not selected_in_cat:
                    st.caption("No papers selected.")
                
                for p in selected_in_cat:
                    cols = st.columns([0.85, 0.15])
                    cols[0].info(f"**{p['relevance_score']}%** - {p['title']}")
                    if cols[1].button("🗑️", key=f"rem_{cat['key']}_{p['id']}"):
                        st.session_state.selected_paper_ids.remove(p['id'])
                        st.rerun()

            with col_candidates:
                st.subheader(f"🔍 Best {cat['limit']} Candidates")
                remaining_in_cat = [p for p in cat_papers if p['id'] not in st.session_state.selected_paper_ids]
                display_list = remaining_in_cat[:cat['limit']]
                
                if not display_list:
                    if len(cat_papers) == 0:
                         st.warning(f"No papers found for category: {cat['key']}")
                    else:
                        st.caption("All candidates selected.")
                
                for p in display_list:
                    # FIX 3: Ensured the checkbox key is unique by including category and ID
                    is_selected = p['id'] in st.session_state.selected_paper_ids
                    if st.checkbox(f"{p['relevance_score']}% - {p['title']}", 
                                   value=is_selected,
                                   key=f"chk_{cat['key']}_{p['id']}"):
                        if p['id'] not in st.session_state.selected_paper_ids:
                            st.session_state.selected_paper_ids.add(p['id'])
                            st.rerun()
                    elif is_selected:
                        st.session_state.selected_paper_ids.remove(p['id'])
                        st.rerun()

            st.divider()

    # --- INTEGRATION: PAGE 4 NAVIGATION ---
    st.markdown("### 🏁 Final Step")
    if st.session_state.get("selected_paper_ids"):
        st.success(f"Ready! You have selected {len(st.session_state.selected_paper_ids)} papers.")
        if st.button("🚀 Proceed to Page 4: PDF Downloader", type="primary"):
            st.switch_page("pages/4_PDF_Downloader.py") 
    else:
        st.warning("Please select at least one paper to continue.")
