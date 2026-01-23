import streamlit as st
import requests
import json
import time
from serpapi import GoogleSearch
from openai import OpenAI

# --- CONFIGURATION & SESSION STATE ---
st.set_page_config(page_title="AgriResearch Finder v1.4", layout="wide")

# 1. Retrieve the Core Idea (for generating general queries)
core_idea = st.session_state.get("passed_idea", "Cotton Pest Management")

# 2. Retrieve Specific Payloads (for the specialized layers)
# We default to empty if not set, and handle generation if needed
passed_payload = st.session_state.get("search_payload", {
    "review": f"{core_idea} review paper state of art",
    "thesis": f"{core_idea} thesis site:krishikosh.egranth.ac.in"
})

# --- HELPER: LLM QUERY GENERATOR (Restored) ---
def generate_queries_llm(idea, client, count=5):
    """Generates exactly 'count' number of search queries based on the idea."""
    prompt = f"""
    Generate {count} distinct, technical search queries for academic databases about: "{idea}".
    Output ONLY a JSON object with a key "queries" containing the list of strings.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        return data.get("queries", [idea])
    except:
        return [idea] * count

# --- CORE SEARCH FUNCTIONS ---

def search_serpapi(query, api_key):
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
        response = requests.get(url, timeout=5)
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
        response = requests.get(url, timeout=5)
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
    if "review" not in query.lower():
        full_query = f"{query} review state of art"
    else:
        full_query = query
    params = {"engine": "google_scholar", "q": full_query, "api_key": api_key, "num": 10}
    try:
        search = GoogleSearch(
