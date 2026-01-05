import streamlit as st
import requests
import json
from serpapi import GoogleSearch
from openai import OpenAI

st.set_page_config(page_title="AgriResearch Finder v1.2", layout="wide")

# --- INTEGRATION: Retrieve idea from Dashboard ---
passed_idea = st.session_state.get("passed_idea", "Amrasca biguttula biguttula management in South Asia")

# --- CORE FUNCTIONS ---
def search_serpapi(query, api_key):
    params = {"engine": "google_scholar", "q": query, "api_key": api_key, "num": 20}
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        return [{"title": res.get("title"), "link": res.get("link"), "snippet": res.get("snippet"), "source": "Google Scholar"} 
                for res in results.get("organic_results", [])]
    except: return []

def search_openalex(query):
    url = f"https://api.openalex.org/works?search={query}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return [{"title": res.get("display_name"), "link": res.get("doi") or res.get("id"), "snippet": "Source: OpenAlex Repository", "source": "OpenAlex"} 
                    for res in response.json().get("results", [])]
    except: return []

def generate_queries_llm(idea, client, is_thesis=False):
    prompt = f"Generate 10 technical search queries about: {idea}. JSON list."
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content).get("queries", [idea])

# --- UI ---
st.title("🌾 Agri-Research Paper Engine")

with st.sidebar:
    st.header("Credentials")
    serp_key = st.text_input("SerpAPI Key", type="password")
    openai_key = st.text_input("OpenAI Key", type="password", value=st.session_state.get("openai_key", ""))
    num_queries = st.slider("Query Variations", 1, 10, 3)

idea = st.text_area("Research Idea:", value=passed_idea)

if st.button("Run Search Engine"):
    if not serp_key or not openai_key:
        st.error("SerpAPI and OpenAI keys are required.")
    else:
        client = OpenAI(api_key=openai_key)
        all_results = []
        seen = set()

        with st.status("Searching...", expanded=True):
            queries = generate_queries_llm(idea, client)
            for q in queries[:num_queries]:
                st.write(f"Searching: {q}")
                results = search_serpapi(q, serp_key) + search_openalex(q)
                for p in results:
                    if p['title'] and p['title'].lower() not in seen:
                        all_results.append(p)
                        seen.add(p['title'].lower())

        # --- INTEGRATION: Save for Sorting Page ---
        st.session_state.all_papers = all_results
        st.session_state.search_idea = idea
        st.session_state.openai_key = openai_key 
        
        st.success(f"Found {len(all_results)} papers. Go to '3_Sorting_and_Filtering' to refine them.")
        
        for res in all_results:
            with st.expander(f"[{res['source']}] {res['title']}"):
                st.write(res['snippet'])
                st.write(f"[Link]({res['link']})")
