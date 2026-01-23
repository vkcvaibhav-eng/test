import streamlit as st
import requests
import json
from serpapi import GoogleSearch
from openai import OpenAI

# --- CONFIGURATION & SESSION STATE ---
st.set_page_config(page_title="AgriResearch Finder v1.3", layout="wide")

# INTEGRATION: Retrieve the idea passed from the Dashboard 
passed_idea = st.session_state.get("passed_idea", "Amrasca biguttula biguttula management in South Asia")

# Persistent memory of the code versions
if "code_history" not in st.session_state:
    st.session_state.code_history = []

# --- CORE FUNCTIONS ---

def search_serpapi(query, api_key):
    params = {"engine": "google_scholar", "q": query, "api_key": api_key, "num": 10}
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        papers = []
        if "organic_results" in results:
            for res in results["organic_results"]:
                papers.append({"title": res.get("title"), "link": res.get("link"), "snippet": res.get("snippet"), "source": "Google Scholar"})
        return papers
    except: return []

def search_semantic_scholar_basic(query):
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&limit=10&fields=title,url,abstract"
    try:
        response = requests.get(url, timeout=10)
        papers = []
        if response.status_code == 200:
            data = response.json()
            for res in data.get("data", []):
                papers.append({"title": res.get("title"), "link": res.get("url"), "snippet": res.get("abstract"), "source": "Semantic Scholar"})
        return papers
    except: return []

def search_openalex(query):
    url = f"https://api.openalex.org/works?search={query}"
    try:
        response = requests.get(url, timeout=10)
        papers = []
        if response.status_code == 200:
            data = response.json()
            for res in data.get("results", []):
                papers.append({"title": res.get("display_name"), "link": res.get("doi") or res.get("id"), "snippet": "Source: OpenAlex Repository", "source": "OpenAlex"})
        return papers
    except: return []

def search_semantic_scholar_authenticated(query, api_key):
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&limit=10&fields=title,url,abstract,citationCount,year"
    headers = {"x-api-key": api_key}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return [{"title": f"{res.get('title')} ({res.get('year', 'N/A')})", "link": res.get("url"), "snippet": f"Citations: {res.get('citationCount', 0)} | {res.get('abstract', '')}", "source": "Semantic Scholar (Auth)"} for res in data.get("data", [])]
    except: pass
    return []

def search_krishikosh_layer(query, api_key):
    full_query = f"{query} site:krishikosh.egranth.ac.in"
    params = {"engine": "google", "q": full_query, "api_key": api_key, "num": 10}
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        return [{"title": res.get("title"), "link": res.get("link"), "snippet": res.get("snippet"), "source": "KrishiKosh Thesis"} for res in results.get("organic_results", [])]
    except: return []

def generate_queries_llm(idea, client, mode="research"):
    """
    Modes: 
    - 'research': Technical, specific, experimental.
    - 'review': Broad, 'overview', 'advancements', 'state of art'.
    - 'thesis': Very broad, Indian context, crop specific.
    """
    if mode == 'thesis':
        prompt = f"Generate 5 broad thesis-style search queries for Indian Agri Universities (KrishiKosh) about: {idea}. Focus on crop names and broad topics. JSON list key: 'queries'."
    elif mode == 'review':
        prompt = f"Generate 5 search queries specifically to find Review Papers and Literature Reviews about: {idea}. Use terms like 'Review of', 'Status of', 'Advances in'. JSON list key: 'queries'."
    else: # research
        prompt = f"Generate 5 technical search queries for high-impact experimental research journals about: {idea}. JSON list key: 'queries'."
        
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"})
    return json.loads(response.choices[0].message.content).get("queries", [idea])

# --- UI WORKFLOW ---

st.title("🌾 Agri-Research Search Engine")
st.markdown(f"**Core Idea:** _{passed_idea}_")

with st.sidebar:
    st.header("Credentials")
    serp_key = st.text_input("SerpAPI Key", type="password", value=st.session_state.get("serpapi_key", ""))
    openai_key = st.text_input("OpenAI Key", type="password", value=st.session_state.get("openai_key", ""))
    semantic_key = st.text_input("Semantic Scholar Key (Optional)", type="password", value=st.session_state.get("semantic_key", ""))
    
    st.divider()
    st.header("🎚️ Query Meters")
    st.info("Adjust how many queries run for each finding style.")
    
    num_research = st.slider("Research Paper Queries", 0, 10, 3, help="Finds experimental/original research.")
    num_review = st.slider("Review Paper Queries", 0, 10, 2, help="Finds literature reviews and overviews.")
    num_thesis = st.slider("KrishiKosh Queries", 0, 10, 2, help="Finds Indian MSc/PhD theses.")

idea = st.text_area("Edit Research Idea (if needed):", value=passed_idea)

if st.button("Run Multi-Path Search"):
    if not serp_key or not openai_key:
        st.error("SerpAPI and OpenAI keys are required.")
    else:
        client = OpenAI(api_key=openai_key)
        all_results = []
        seen = set()
        
        # --- PATH 1: RESEARCH PAPERS ---
        if num_research > 0:
            with st.status(f"🔍 Searching Research Papers ({num_research} queries)...", expanded=True) as status:
                queries = generate_queries_llm(idea, client, mode="research")
                for q in queries[:num_research]:
                    st.write(f"Query: {q}")
                    # Use Scholar + OpenAlex + Semantic for Research
                    s1 = search_serpapi(q, serp_key)
                    s2 = search_openalex(q)
                    s3 = search_semantic_scholar_authenticated(q, semantic_key) if semantic_key else search_semantic_scholar_basic(q)
                    
                    for p in s1 + s2 + s3:
                        if p['title'] and p['title'].lower() not in seen:
                            p['type'] = 'Research'
                            all_results.append(p)
                            seen.add(p['title'].lower())
                status.update(label="✅ Research Papers Found!", state="complete", expanded=False)

        # --- PATH 2: REVIEW PAPERS ---
        if num_review > 0:
            with st.status(f"📚 Searching Review Papers ({num_review} queries)...", expanded=True) as status:
                queries = generate_queries_llm(idea, client, mode="review")
                for q in queries[:num_review]:
                    st.write(f"Query: {q}")
                    # Use Scholar + Semantic (Review papers often well indexed here)
                    s1 = search_serpapi(q, serp_key)
                    s3 = search_semantic_scholar_authenticated(q, semantic_key) if semantic_key else search_semantic_scholar_basic(q)
                    
                    for p in s1 + s3:
                        if p['title'] and p['title'].lower() not in seen:
                            p['type'] = 'Review'
                            all_results.append(p)
                            seen.add(p['title'].lower())
                status.update(label="✅ Review Papers Found!", state="complete", expanded=False)

        # --- PATH 3: KRISHIKOSH THESES ---
        if num_thesis > 0:
            with st.status(f"🎓 Searching KrishiKosh Theses ({num_thesis} queries)...", expanded=True) as status:
                queries = generate_queries_llm(idea, client, mode="thesis")
                for q in queries[:num_thesis]:
                    st.write(f"Query: {q}")
                    # Use Specialized KrishiKosh Layer
                    t_results = search_krishikosh_layer(q, serp_key)
                    for tr in t_results:
                        if tr['title'].lower() not in seen:
                            tr['type'] = 'Thesis'
                            all_results.append(tr)
                            seen.add(tr['title'].lower())
                status.update(label="✅ Theses Found!", state="complete", expanded=False)

        # --- SAVE & DISPLAY ---
        st.session_state.all_papers = all_results
        st.session_state.search_idea = idea
        
        st.divider()
        st.success(f"Total Unique Items Found: {len(all_results)}")
        
        # Display by Category Tabs
        tab1, tab2, tab3 = st.tabs(["Research Papers", "Review Papers", "Theses"])
        
        with tab1:
            research_papers = [p for p in all_results if p.get('type') == 'Research']
            st.write(f"Found: {len(research_papers)}")
            for res in research_papers:
                with st.expander(f"{res['title']}"):
                    st.caption(f"Source: {res['source']}")
                    st.write(res['snippet'])
                    st.write(f"[Link]({res['link']})")
                    
        with tab2:
            review_papers = [p for p in all_results if p.get('type') == 'Review']
            st.write(f"Found: {len(review_papers)}")
            for res in review_papers:
                with st.expander(f"{res['title']}"):
                    st.caption(f"Source: {res['source']}")
                    st.write(res['snippet'])
                    st.write(f"[Link]({res['link']})")

        with tab3:
            theses = [p for p in all_results if p.get('type') == 'Thesis']
            st.write(f"Found: {len(theses)}")
            for res in theses:
                with st.expander(f"{res['title']}"):
                    st.caption(f"Source: {res['source']}")
                    st.write(res['snippet'])
                    st.write(f"[Link]({res['link']})")
