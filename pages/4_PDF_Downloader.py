import streamlit as st
import requests
import time
import re
from serpapi import GoogleSearch

st.set_page_config(page_title="Internal PDF Fetcher", layout="wide")

# ==================== HELPERS ====================

def download_file(url):
    """Helper to download and return bytes if it is a PDF"""
    try:
        # Mimic a real browser to avoid being blocked
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/pdf,application/x-download,text/html,application/xhtml+xml',
            'Referer': 'https://scholar.google.com/'
        }
        response = requests.get(url, headers=headers, timeout=25, verify=False, stream=True)
        
        # Check if content type is PDF
        content_type = response.headers.get('Content-Type', '').lower()
        if response.status_code == 200:
            if 'pdf' in content_type or response.content.startswith(b'%PDF'):
                if len(response.content) > 2000: # Ignore tiny error files
                    return response.content
    except: 
        pass
    return None

# ==================== DOWNLOAD STRATEGIES ====================

def strategy_1_serpapi_deep(paper, serp_key):
    """
    Strategy 1: SerpAPI 'Deep Search' (The Heavy Hitter).
    1. Checks the main result for a [PDF] link.
    2. If failed, it searches 'All Versions' (cluster_id) to find a free one.
    """
    if not serp_key: return None
    
    try:
        # STEP 1: Search for the specific title
        params = {
            "engine": "google_scholar",
            "q": paper['title'],
            "api_key": serp_key,
            "num": 1
        }
        search = GoogleSearch(params)
        results = search.get_dict()
        
        if "organic_results" not in results:
            return None

        primary_result = results["organic_results"][0]
        
        # Check 1: Does the main result have a direct PDF?
        if "resources" in primary_result:
            for resource in primary_result["resources"]:
                if resource.get("file_format") == "PDF" and resource.get("link"):
                    st.write(f"   ↳ Found direct link via SerpAPI...")
                    pdf = download_file(resource["link"])
                    if pdf: return pdf

        # Check 2: 'All Versions' Deep Dive (The "Forced" Method)
        # If we didn't find a PDF yet, check if there are other versions (e.g., "All 6 versions")
        cluster_id = primary_result.get("publication_info", {}).get("cites_id")
        if not cluster_id:
             # Fallback: sometimes cluster_id is elsewhere or named differently
             pass
        else:
            st.write(f"   ↳ Checking alternative versions...")
            # Search specifically within this cluster for anything with a PDF
            params_cluster = {
                "engine": "google_scholar",
                "q": "", # Empty q because we use cluster_id
                "cluster": cluster_id,
                "api_key": serp_key,
                "num": 5 # Check top 5 versions
            }
            search_cluster = GoogleSearch(params_cluster)
            cluster_results = search_cluster.get_dict()
            
            if "organic_results" in cluster_results:
                for res in cluster_results["organic_results"]:
                    if "resources" in res:
                        for resource in res["resources"]:
                            if resource.get("file_format") == "PDF" and resource.get("link"):
                                st.write(f"   ↳ Found free version in alternatives!")
                                pdf = download_file(resource["link"])
                                if pdf: return pdf

    except Exception as e:
        # st.write(f"SerpAPI Error: {e}")
        pass
    return None

def strategy_2_krishikosh_smart(paper):
    """Strategy 2: Smart KrishiKosh Scraper (Specific for Theses)"""
    link = paper.get('link', '')
    
    # Trigger only if domain matches or it's categorized as Thesis
    if 'krishikosh' in link or 'Thesis' in paper.get('category', ''):
        try:
            # If we have a handle link, scrape it
            if 'handle' in link:
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(link, headers=headers, timeout=15)
                # Look for bitstream links (standard DSpace pattern)
                # Matches: /bitstream/handle/123/456/thesis.pdf
                matches = re.findall(r'href=["\'](/bitstream/[^"\']+\.pdf[^"\']*)["\']', response.text)
                
                for match in matches:
                    full_url = f"https://krishikosh.egranth.ac.in{match}"
                    pdf = download_file(full_url)
                    if pdf: return pdf
            
            # Fallback: Try guessing the standard URL structure
            if '/handle/' in link:
                handle_id = link.split('/handle/')[-1]
                # Try ID/1 to ID/4
                for i in range(1, 4): 
                    guess_url = f"http://krishikosh.egranth.ac.in/bitstream/1/{handle_id}/{i}/thesis.pdf"
                    pdf = download_file(guess_url)
                    if pdf: return pdf
        except: pass
    return None

def strategy_3_core_api(paper, core_key=None):
    """Strategy 3: CORE API (Open Access)"""
    if not core_key: return None
    try:
        url = "https://api.core.ac.uk/v3/search/works"
        headers = {"Authorization": f"Bearer {core_key}"}
        params = {"q": paper['title'], "limit": 1}
        response = requests.post(url, json=params, headers=headers, timeout=10)
        if response.status_code == 200:
            results = response.json().get('results', [])
            if results and results[0].get('downloadUrl'):
                return download_file(results[0]['downloadUrl'])
    except: pass
    return None

def strategy_4_unpaywall(paper):
    """Strategy 4: Unpaywall (DOI Resolver)"""
    link = paper.get('link', '')
    doi = None
    if 'doi.org/' in link:
        doi = link.split('doi.org/')[-1]
    
    if doi:
        try:
            url = f"https://api.unpaywall.org/v2/{doi}?email=research@agri.com"
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data.get('best_oa_location', {}).get('url_for_pdf'):
                    return download_file(data['best_oa_location']['url_for_pdf'])
        except: pass
    return None

def strategy_5_fallback_scrape(paper):
    """Strategy 5: General 'Try everything' scrape"""
    link = paper.get('link', '')
    if not link: return None
    
    # 1. Is the link itself a PDF?
    if link.lower().endswith('.pdf'):
        return download_file(link)
        
    # 2. Is it arXiv?
    if 'arxiv.org' in link:
        arxiv_id = link.split('/')[-1]
        return download_file(f"https://arxiv.org/pdf/{arxiv_id}.pdf")

    return None

# ==================== MAIN UI ====================

st.title("📥 Ultimate PDF Fetcher")
st.markdown("""
Attempts to force-fetch full text using **Deep Search**.
For maximum success, enter a **SerpAPI Key** below.
""")

# Initialize Session State
if "downloaded_papers" not in st.session_state:
    st.session_state.downloaded_papers = {} 

if "selected_paper_ids" not in st.session_state or not st.session_state.selected_paper_ids:
    st.warning("⚠️ No papers selected.")
    st.stop()

# Get selected papers
all_scored = st.session_state.get("scored_papers", [])
selected_papers = [p for p in all_scored if p['id'] in st.session_state.selected_paper_ids]

# Stats
col1, col2, col3 = st.columns(3)
col1.metric("Selected", len(selected_papers))
already_in_mem = len([p for p in selected_papers if p['id'] in st.session_state.downloaded_papers])
col2.metric("Downloaded", already_in_mem)
col3.metric("Missing", len(selected_papers) - already_in_mem)

st.divider()

# API Key Inputs
with st.expander("⚙️ **Unlock 'Forced' Mode (API Keys)**", expanded=True):
    col_a, col_b = st.columns(2)
    with col_a:
        serp_key = st.text_input("SerpAPI Key (REQUIRED for 'Deep Search')", type="password", 
                                value=st.session_state.get("serpapi_key", ""),
                                help="Get this at serpapi.com. It finds hidden PDF links on Google Scholar.")
    with col_b:
        core_key = st.text_input("CORE API Key (Optional)", type="password", 
                                value=st.session_state.get("core_key", ""),
                                help="Get at core.ac.uk. Good for official Open Access.")

# ==================== EXECUTION ====================

if st.button("🚀 Start Forced Download", type="primary", use_container_width=True):
    
    progress_bar = st.progress(0)
    status_box = st.container(border=True)
    success_count = 0
    
    with status_box:
        for idx, paper in enumerate(selected_papers):
            if paper['id'] in st.session_state.downloaded_papers:
                success_count += 1
                continue
            
            st.write(f"🔎 **{paper['title'][:60]}...**")
            
            pdf_bytes = None
            method = "None"
            
            # --- PRIORITY 1: THESIS SPECIALIST ---
            if "Thesis" in paper.get('category', ''):
                pdf_bytes = strategy_2_krishikosh_smart(paper)
                method = "KrishiKosh Scraper"
            
            # --- PRIORITY 2: SERPAPI DEEP SEARCH (The "Forced" method) ---
            if not pdf_bytes and serp_key:
                pdf_bytes = strategy_1_serpapi_deep(paper, serp_key)
                method = "SerpAPI Deep Search"
            
            # --- PRIORITY 3: CORE / UNPAYWALL ---
            if not pdf_bytes:
                pdf_bytes = strategy_3_core_api(paper, core_key)
                method = "CORE API"
                
            if not pdf_bytes:
                pdf_bytes = strategy_4_unpaywall(paper)
                method = "Unpaywall"
            
            # --- PRIORITY 4: LAST RESORT ---
            if not pdf_bytes:
                pdf_bytes = strategy_5_fallback_scrape(paper)
                method = "Direct Scrape"
            
            # --- SAVE OR FAIL ---
            if pdf_bytes:
                st.session_state.downloaded_papers[paper['id']] = {
                    'title': paper['title'],
                    'category': paper.get('category', 'Research'),
                    'bytes': pdf_bytes,
                    'source': method,
                    'file_size': f"{len(pdf_bytes)/1024/1024:.2f} MB"
                }
                st.success(f"   ✅ Acquired via {method}")
                success_count += 1
            else:
                st.error("   ❌ Failed to locate full text.")
                
            progress_bar.progress((idx + 1) / len(selected_papers))
            
    st.success(f"🎉 Operation Complete! {success_count}/{len(selected_papers)} papers available.")
    if success_count > 0:
        time.sleep(1.5)
        st.rerun()

# ==================== NEXT STEP ====================

if len(st.session_state.downloaded_papers) > 0:
    st.divider()
    st.subheader("🏁 Ready for Analysis")
    st.write(f"**{len(st.session_state.downloaded_papers)}** papers are loaded in memory.")
    
    if st.button("📖 Proceed to Reading & Summary", type="primary", use_container_width=True):
        st.switch_page("pages/5_Paper_Reading.py")
