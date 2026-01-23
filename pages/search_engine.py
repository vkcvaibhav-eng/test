# search_engine.py

import streamlit as st
import requests
import json
import time
from serpapi import GoogleSearch
from openai import OpenAI

# --- CONFIGURATION & SESSION STATE ---
st.set_page_config(page_title="AgriResearch Finder v1.3", layout="wide")

# INTEGRATION: Retrieve the payloads passed from the Dashboard 
passed_payload = st.session_state.get("search_payload", {
    "general": ["Amrasca biguttula management", "Cotton pest control strategies", "Sucking pest dynamic South Asia"],
    "review": "Amrasca biguttula biguttula management review paper",
    "thesis": "Amrasca biguttula control thesis site:krishikosh.egranth.ac.in"
})

# --- CORE SEARCH FUNCTIONS ---

def search_serpapi(query, api_key):
    # Standard search for general papers
    params = {"engine": "google_scholar", "q": query, "api_key": api_key, "num": 10}
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
                    "source": "Google Scholar (General)"
                })
        return papers
    except: return []

def search_semantic_scholar_basic(query):
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&limit=10&fields=title,url,abstract,year"
    try:
        response = requests.get(url, timeout=10)
        papers = []
        if response.status_code == 200:
            data = response.json()
            for res in data.get("data", []):
                papers.append({
                    "title": f"{res.get('title')} ({res.get('year', '')})", 
                    "link": res.get("url"), 
                    "snippet": res.get("abstract"), 
                    "source": "Semantic Scholar"
                })
        return papers
    except: return []

def search_openalex(query):
    url = f"https://api.openalex.org/works?search={query}&per-page=10"
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
    except: return []

def search_krishikosh_layer(query, api_key):
    # Ensure the query targets the specific site if not already present
    if "site:krishikosh" not in query:
        full_query = f"{query} site:krishikosh.egranth.ac.in"
    else:
        full_query = query
        
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
    except: return []

def search_review_layer(query, api_key):
    # Specifically adds review-centric keywords if missing
    full_query = f"{query} review \"state of the art\""
    params = {"engine": "google_scholar", "q": full_query, "api_key": api_key, "num": 10}
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        return [{
            "title": res.get("title"), 
            "link": res.get("link"), 
            "snippet": res.get("snippet"), 
            "source": "Review Paper (Scholar)"
        } for res in results.get("organic_results", [])]
    except: return []

# --- UI WORKFLOW ---

st.title("🌾 Agri-Research Paper Engine v1.3")

with st.sidebar:
    st.header("Credentials")
    serp_key = st.text_input("SerpAPI Key", type="password", value=st.session_state.get("serpapi_key", ""))
    openai_key = st.text_input("OpenAI Key", type="password", value=st.session_state.get("openai_key", ""))
    semantic_key = st.text_input("Semantic Scholar Key (Optional)", type="password", value=st.session_state.get("semantic_key", ""))
    
    st.info("The search strategy below was auto-generated from your dashboard idea.")

# --- SEARCH STRATEGY INPUTS ---
with st.container(border=True):
    st.subheader("🔍 Search Strategy")
    st.caption("Modify these generated queries if needed before running the search.")
    
    col_gen, col_spec = st.columns([1, 1])
    
    with col_gen:
        st.markdown("**1. General Research (3 Short Sentences)**")
        # Load the 3 sentences into 3 text inputs
        gen_1 = st.text_input("Query 1", value=passed_payload["general"][0] if len(passed_payload["general"]) > 0 else "")
        gen_2 = st.text_input("Query 2", value=passed_payload["general"][1] if len(passed_payload["general"]) > 1 else "")
        gen_3 = st.text_input("Query 3", value=passed_payload["general"][2] if len(passed_payload["general"]) > 2 else "")
        
    with col_spec:
        st.markdown("**2. Specialized Search**")
        review_q = st.text_area("Review Paper Strategy", value=passed_payload["review"], height=68)
        thesis_q = st.text_area("KrishiKosh Thesis Strategy", value=passed_payload["thesis"], height=68)

if st.button("🚀 Run Multi-Layer Search", type="primary"):
    if not serp_key:
        st.error("SerpAPI key is required.")
    else:
        all_results = []
        seen = set()
        
        # 1. GENERAL LAYER (Using the 3 short sentences)
        with st.status("Running General Research Layer...", expanded=True) as status:
            general_queries = [q for q in [gen_1, gen_2, gen_3] if q]
            
            for q in general_queries:
                st.write(f"Searching: {q}")
                # Parallel-ish execution of sources
                s1 = search_serpapi(q, serp_key)
                s2 = search_openalex(q)
                s3 = search_semantic_scholar_basic(q)
                
                # Combine results
                for p in s1 + s2 + s3:
                    if p['title'] and p['title'].lower() not in seen:
                        all_results.append(p)
                        seen.add(p['title'].lower())
            status.update(label="✅ General Layer Complete", state="complete", expanded=False)

        # 2. REVIEW PAPER LAYER
        with st.status("Running Review Paper Layer...", expanded=True) as status:
            if review_q:
                st.write(f"Hunting Reviews: {review_q}")
                r_results = search_review_layer(review_q, serp_key)
                for res in r_results:
                    if res['title'].lower() not in seen:
                        all_results.append(res)
                        seen.add(res['title'].lower())
            status.update(label="✅ Review Layer Complete", state="complete", expanded=False)

        # 3. THESIS LAYER
        with st.status("Running KrishiKosh Thesis Layer...", expanded=True) as status:
            if thesis_q:
                st.write(f"Digging Theses: {thesis_q}")
                t_results = search_krishikosh_layer(thesis_q, serp_key)
                for res in t_results:
                    if res['title'].lower() not in seen:
                        all_results.append(res)
                        seen.add(res['title'].lower())
            status.update(label="✅ Thesis Layer Complete", state="complete", expanded=False)

        # --- SAVE RESULTS ---
        st.session_state.all_papers = all_results
        
        # We save the original idea string just for reference if needed
        st.session_state.search_idea = passed_payload["review"] 
        
        st.success(f"🎉 Search Complete! Found {len(all_results)} unique documents.")
        
        # Display Results grouped
        tabs = st.tabs(["All Results", "Reviews", "Theses"])
        
        with tabs[0]:
            for res in all_results:
                with st.expander(f"[{res['source']}] {res['title']}"):
                    st.write(res['snippet'])
                    st.markdown(f"[🔗 Open Link]({res['link']})")

        with tabs[1]:
            reviews = [r for r in all_results if "Review" in r['source'] or "review" in r['title'].lower()]
            if not reviews: st.info("No explicit review papers identified.")
            for res in reviews:
                st.markdown(f"- [{res['title']}]({res['link']})")

        with tabs[2]:
            theses = [r for r in all_results if "KrishiKosh" in r['source']]
            if not theses: st.info("No theses found.")
            for res in theses:
                st.markdown(f"- [{res['title']}]({res['link']})")
