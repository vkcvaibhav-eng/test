import streamlit as st
import requests
import json
import time
from serpapi import GoogleSearch
from openai import OpenAI

# --- CONFIGURATION & SESSION STATE ---
st.set_page_config(page_title="AgriResearch Finder v1.2", layout="wide")

# INTEGRATION: Retrieve the idea passed from the Dashboard 
# If no idea is passed, it uses your original default text
passed_idea = st.session_state.get("passed_idea", "Amrasca biguttula biguttula management in South Asia")

# Persistent memory of the code versions
if "code_history" not in st.session_state:
    st.session_state.code_history = [
        "v1.0: Core engine (Google Scholar, OpenAlex, Basic Semantic Scholar)",
        "v1.1: Added KrishiKosh & Auth-Semantic (Broken Core)",
        "v1.2: Fixed Core Workflow + Independent Layers"
    ]

# --- CORE FUNCTIONS FROM V1.0 (RE-STABILIZED) ---

def search_serpapi(query, api_key):
    """ORIGINAL V1.0 LOGIC: Searches Google Scholar via SerpAPI."""
    params = {
        "engine": "google_scholar",
        "q": query,
        "api_key": api_key,
        "num": 20
    }
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        papers = []
        if "organic_results" in results:
            for res in results["organic_results"]:
                papers.append({
                    "title": res.get("title"),
                    "link": res.get("link"),
                    "snippet": res.get("snippet"),
                    "source": "Google Scholar"
                })
        return papers
    except:
        return []

def search_semantic_scholar_basic(query):
    """ORIGINAL V1.0 LOGIC: Public Semantic Scholar API."""
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&limit=20&fields=title,url,abstract"
    try:
        response = requests.get(url, timeout=10)
        papers = []
        if response.status_code == 200:
            data = response.json()
            for res in data.get("data", []):
                papers.append({
                    "title": res.get("title"),
                    "link": res.get("url"),
                    "snippet": res.get("abstract"),
                    "source": "Semantic Scholar"
                })
        return papers
    except:
        return []

def search_openalex(query):
    """ORIGINAL V1.0 LOGIC: Search in OpenAlex."""
    url = f"https://api.openalex.org/works?search={query}"
    try:
        response = requests.get(url, timeout=10)
        papers = []
        if response.status_code == 200:
            data = response.json()
            for res in data.get("results", []):
                papers.append({
                    "title": res.get("display_name"),
                    "link": res.get("doi") or res.get("id"),
                    "snippet": "Source: OpenAlex Repository",
                    "source": "OpenAlex"
                })
        return papers
    except:
        return []

# --- NEW INDEPENDENT LAYERS (V1.2) ---

def search_semantic_scholar_authenticated(query, api_key):
    """NEW LAYER: Separated from basic logic to prevent failure."""
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&limit=20&fields=title,url,abstract,citationCount,year"
    headers = {"x-api-key": api_key}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return [{
                "title": f"{res.get('title')} ({res.get('year', 'N/A')})",
                "link": res.get("url"),
                "snippet": f"Citations: {res.get('citationCount', 0)} | {res.get('abstract', '')}",
                "source": "Semantic Scholar (Auth)"
            } for res in data.get("data", [])]
    except:
        pass
    return []

def search_krishikosh_layer(query, api_key):
    """NEW LAYER: KrishiKosh via SerpAPI Google Engine."""
    full_query = f"{query} site:krishikosh.egranth.ac.in"
    params = {"engine": "google", "q": full_query, "api_key": api_key, "num": 10}
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        return [{
            "title": res.get("title"),
            "link": res.get("link"),
            "snippet": res.get("snippet"),
            "source": "KrishiKosh Thesis"
        } for res in results.get("organic_results", [])]
    except:
        return []

# --- LLM ENGINE ---

def generate_queries_llm(idea, client, is_thesis=False):
    """Core Query Generation."""
    if is_thesis:
        prompt = f"Generate 10 broad thesis-style search queries for Indian Agri Universities about: {idea}. No 'site:' operators. JSON list."
    else:
        prompt = f"Generate 10 technical search queries for high-impact journals about: {idea}. JSON list."
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    key = "queries" if not is_thesis else "thesis_queries"
    return json.loads(response.choices[0].message.content).get(key, [idea])

# --- UI WORKFLOW ---

st.title("🌾 Agri-Research Paper Engine v1.2")

with st.sidebar:
    st.header("Credentials")
    serp_key = st.text_input("SerpAPI Key", type="password")
    openai_key = st.text_input("OpenAI Key", type="password")
    semantic_key = st.text_input("Semantic Scholar Key (Optional)", type="password")
    num_queries = st.slider("Query Variations", 1, 20, 5)

# INTEGRATION: Use the passed idea as the default value for the text area 
idea = st.text_area("Research Idea:", value=passed_idea)

if st.button("Run Search Engine"):
    if not serp_key or not openai_key:
        st.error("SerpAPI and OpenAI keys are required.")
    else:
        client = OpenAI(api_key=openai_key)
        all_results = []
        seen = set()

        # STEP 1: ORIGINAL V1.0 PIPELINE (Fixed)
        with st.status("Running Original Search Logic...", expanded=True):
            journal_queries = generate_queries_llm(idea, client)
            for q in journal_queries[:num_queries]:
                st.write(f"Searching: {q}")
                # Original core sources
                s1 = search_serpapi(q, serp_key)
                s2 = search_openalex(q)
                
                # Semantic Scholar Logic: Use Auth if key exists, otherwise use Basic
                if semantic_key:
                    s3 = search_semantic_scholar_authenticated(q, semantic_key)
                else:
                    s3 = search_semantic_scholar_basic(q)
                
                for p in s1 + s2 + s3:
                    if p['title'] and p['title'].lower() not in seen:
                        all_results.append(p)
                        seen.add(p['title'].lower())

        # STEP 2: KRISHIKOSH LAYER (Independent)
        with st.status("Searching KrishiKosh Theses...", expanded=False):
            thesis_queries = generate_queries_llm(idea, client, is_thesis=True)
            for tq in thesis_queries[:3]:
                t_results = search_krishikosh_layer(tq, serp_key)
                for tr in t_results:
                    if tr['title'].lower() not in seen:
                        all_results.append(tr)
                        seen.add(tr['title'].lower())

        st.success(f"Found {len(all_results)} total items.")
        for res in all_results:
            with st.expander(f"[{res['source']}] {res['title']}"):
                st.write(res['snippet'])
                st.write(f"[Link]({res['link']})")
# Inside the "Run Search Engine" button logic in search_engine.py
if st.button("Run Search Engine"):
    # ... (existing search code) ...
    
    # Save to session state for the next page
    st.session_state.all_papers = all_results
    st.session_state.search_idea = idea # The 3-line research idea
    st.success(f"Found {len(all_results)} items. Proceed to 'Sorting and Filtering' page.")
