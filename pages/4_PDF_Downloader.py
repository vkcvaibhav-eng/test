import streamlit as st
import requests
import time
import re
from serpapi import GoogleSearch

st.set_page_config(page_title="Internal PDF Fetcher", layout="wide")

# ==================== DOWNLOAD STRATEGIES ====================

def strategy_1_core_api(paper, core_key=None):
    """Strategy 1: CORE API (Official Open Access)"""
    if not core_key: return None
    try:
        url = "https://api.core.ac.uk/v3/search/works"
        headers = {"Authorization": f"Bearer {core_key}"}
        # Search by title
        params = {"q": paper['title'], "limit": 1}
        response = requests.post(url, json=params, headers=headers, timeout=10)
        if response.status_code == 200:
            results = response.json().get('results', [])
            if results and results[0].get('downloadUrl'):
                return download_file(results[0]['downloadUrl'])
    except: pass
    return None

def strategy_2_serpapi_scholar(paper, serp_key=None):
    """
    Strategy 2: Google Scholar via SerpAPI (The 'Heavy Hitter')
    Finds direct [PDF] links hosted on ResearchGate, Universities, etc.
    """
    if not serp_key: return None
    try:
        params = {
            "engine": "google_scholar",
            "q": paper['title'],
            "api_key": serp_key,
            "num": 1
        }
        search = GoogleSearch(params)
        results = search.get_dict()
        
        if "organic_results" in results:
            for res in results["organic_results"]:
                # Check for "resources" (the [PDF] link on the right side)
                if "resources" in res:
                    for resource in res["resources"]:
                        if resource.get("file_format") == "PDF" and resource.get("link"):
                            return download_file(resource["link"])
                
                # Check for inline links
                if "inline_links" in res and "cited_by" in res["inline_links"]:
                     # Sometimes PDF links are buried here, but 'resources' is the main one
                     pass
    except Exception as e:
        # st.error(f"SerpAPI Error: {e}") 
        pass
    return None

def strategy_3_krishikosh_smart(paper):
    """Strategy 3: Smart KrishiKosh Scraper for Theses"""
    link = paper.get('link', '')
    
    # Only run if it looks like a KrishiKosh handle
    if 'krishikosh.egranth.ac.in' in link or 'handle' in link:
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            # 1. Go to the handle page
            response = requests.get(link, headers=headers, timeout=10)
            
            # 2. Look for the "bitstream" links in the HTML
            # Pattern: /bitstream/handle/123456789/1234/thesis.pdf?sequence=1
            matches = re.findall(r'href=["\'](/bitstream/[^"\']+\.pdf[^"\']*)["\']', response.text)
            
            # 3. Sort matches (prefer 'thesis.pdf' or larger files usually at the end)
            for match in matches:
                # Construct full URL
                full_url = f"https://krishikosh.egranth.ac.in{match}" if match.startswith('/') else match
                
                # Try downloading
                file_data = download_file(full_url)
                if file_data:
                    return file_data
        except: pass
    return None

def strategy_4_unpaywall(paper):
    """Strategy 4: Unpaywall API (DOI resolver)"""
    link = paper.get('link', '')
    doi = None
    
    # Extract DOI from link or snippet
    if 'doi.org/' in link:
        doi = link.split('doi.org/')[-1]
    
    if doi:
        try:
            url = f"https://api.unpaywall.org/v2/{doi}?email=research@university.edu"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Check best location
                if data.get('best_oa_location') and data['best_oa_location'].get('url_for_pdf'):
                    return download_file(data['best_oa_location']['url_for_pdf'])
                # Check other locations
                for loc in data.get('oa_locations', []):
                     if loc.get('url_for_pdf'):
                        return download_file(loc['url_for_pdf'])
        except: pass
    return None

def strategy_5_semantic_scholar(paper):
    """Strategy 5: Semantic Scholar Public API"""
    try:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {"query": paper['title'], "fields": "openAccessPdf", "limit": 1}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('data') and data['data'][0].get('openAccessPdf'):
                return download_file(data['data'][0]['openAccessPdf']['url'])
    except: pass
    return None

def strategy_6_general_scrape(paper):
    """Strategy 6: Fallback - Check if the main link is a PDF"""
    link = paper.get('link', '')
    if not link: return None
    
    # Case A: Link is already a PDF
    if link.lower().endswith('.pdf'):
        return download_file(link)
        
    # Case B: Link is arXiv
    if 'arxiv.org' in link:
        arxiv_id = link.split('/')[-1]
        return download_file(f"https://arxiv.org/pdf/{arxiv_id}.pdf")
        
    return None

# ==================== DOWNLOAD HELPER ====================

def download_file(url):
    """Helper to download and return bytes if it is a PDF"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Allow redirects is True by default in requests
        response = requests.get(url, headers=headers, timeout=20, verify=False) 
        
        if response.status_code == 200:
            # Check content type or signature
            if 'application/pdf' in response.headers.get('Content-Type', '') or response.content.startswith(b'%PDF'):
                if len(response.content) > 2000: # Ensure it's not a tiny error file
                    return response.content
    except: pass
    return None

# ==================== MAIN UI ====================

st.title("📥 Intelligent PDF Fetcher")
st.markdown("Fetching full-text PDFs into memory using **CORE, SerpAPI (Scholar), Unpaywall, and Smart Scraping**.")

# Initialize Session State
if "downloaded_papers" not in st.session_state:
    st.session_state.downloaded_papers = {} 

if "selected_paper_ids" not in st.session_state or not st.session_state.selected_paper_ids:
    st.warning("⚠️ No papers selected. Please go back to Sorting.")
    st.stop()

# Get selected papers
all_scored = st.session_state.get("scored_papers", [])
selected_papers = [p for p in all_scored if p['id'] in st.session_state.selected_paper_ids]

# Stats
col1, col2, col3 = st.columns(3)
col1.metric("Selected Papers", len(selected_papers))
already_in_mem = len([p for p in selected_papers if p['id'] in st.session_state.downloaded_papers])
col2.metric("Ready in Memory", already_in_mem)
col3.metric("Pending", len(selected_papers) - already_in_mem)

st.divider()

# API Key Inputs
with st.expander("⚙️ **Unlock Maximum Success (API Keys)**", expanded=True):
    col_a, col_b = st.columns(2)
    with col_a:
        core_key = st.text_input("CORE API Key (Excellent for OA)", type="password", 
                                value=st.session_state.get("core_key", ""))
    with col_b:
        serp_key = st.text_input("SerpAPI Key (Crucial for Paywalled/Hidden)", type="password", 
                                value=st.session_state.get("serpapi_key", ""))
        st.caption("ℹ️ Finds PDF links on Google Scholar (ResearchGate, Universities).")

# ==================== EXECUTION LOGIC ====================

start_btn = st.button("🚀 Start Deep Fetching", type="primary", use_container_width=True)

if start_btn:
    progress_bar = st.progress(0)
    status_container = st.container(border=True)
    success_count = 0
    
    with status_container:
        for idx, paper in enumerate(selected_papers):
            # Skip if done
            if paper['id'] in st.session_state.downloaded_papers:
                success_count += 1
                continue
            
            st.write(f"🔄 **{paper['title'][:50]}...**")
            
            pdf_bytes = None
            used_strategy = "None"
            
            # STRATEGY 1: KRISHIKOSH (If it's a thesis, prioritize this)
            if not pdf_bytes and "Thesis" in paper.get('category', ''):
                 pdf_bytes = strategy_3_krishikosh_smart(paper)
                 used_strategy = "KrishiKosh Smart"

            # STRATEGY 2: SERPAPI (Google Scholar - The Heavy Hitter)
            if not pdf_bytes:
                pdf_bytes = strategy_2_serpapi_scholar(paper, serp_key)
                used_strategy = "Google Scholar (SerpAPI)"
            
            # STRATEGY 3: CORE API
            if not pdf_bytes:
                pdf_bytes = strategy_1_core_api(paper, core_key)
                used_strategy = "CORE API"
                
            # STRATEGY 4: UNPAYWALL
            if not pdf_bytes:
                pdf_bytes = strategy_4_unpaywall(paper)
                used_strategy = "Unpaywall"
                
            # STRATEGY 5: SEMANTIC SCHOLAR
            if not pdf_bytes:
                pdf_bytes = strategy_5_semantic_scholar(paper)
                used_strategy = "Semantic Scholar"
                
            # STRATEGY 6: FALLBACK SCRAPE
            if not pdf_bytes:
                pdf_bytes = strategy_6_general_scrape(paper)
                used_strategy = "Direct Link"
            
            # SAVE RESULT
            if pdf_bytes:
                st.session_state.downloaded_papers[paper['id']] = {
                    'title': paper['title'],
                    'category': paper.get('category', 'Research'),
                    'bytes': pdf_bytes,
                    'source': used_strategy,
                    'file_size': f"{len(pdf_bytes)/1024/1024:.2f} MB"
                }
                st.success(f"   ✅ Found via {used_strategy}")
                success_count += 1
            else:
                st.error(f"   ❌ Could not find PDF")
                
            progress_bar.progress((idx + 1) / len(selected_papers))
            time.sleep(0.5)

    st.success(f"🎉 Process Complete! {success_count}/{len(selected_papers)} papers acquired.")
    if success_count > 0:
        time.sleep(1)
        st.rerun()

# ==================== NEXT STEP ====================

if len(st.session_state.downloaded_papers) > 0:
    st.divider()
    st.subheader("🏁 Ready for Analysis")
    st.write(f"**{len(st.session_state.downloaded_papers)}** papers are loaded in memory.")
    
    if st.button("📖 Proceed to Reading & Summary", type="primary", use_container_width=True):
        st.switch_page("pages/5_Paper_Reading.py")
