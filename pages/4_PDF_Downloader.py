import streamlit as st
import requests
import time
import re
from urllib.parse import quote, urljoin
import io

st.set_page_config(page_title="Internal PDF Fetcher", layout="wide")

# ==================== DOWNLOAD STRATEGIES ====================

def strategy_1_direct_link(paper):
    """Strategy 1: Direct PDF link from search results"""
    link = paper.get('link', '')
    if link.endswith('.pdf'):
        return download_file(link)
    if 'arxiv.org' in link:
        arxiv_id = link.split('/')[-1]
        return download_file(f"https://arxiv.org/pdf/{arxiv_id}.pdf")
    return None

def strategy_2_unpaywall(paper):
    """Strategy 2: Unpaywall API"""
    link = paper.get('link', '')
    doi = None
    if 'doi.org/' in link:
        doi = link.split('doi.org/')[-1]
    
    if doi:
        try:
            url = f"https://api.unpaywall.org/v2/{doi}?email=research@agriculture.com"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('best_oa_location') and data['best_oa_location'].get('url_for_pdf'):
                    return download_file(data['best_oa_location']['url_for_pdf'])
        except: pass
    return None

def strategy_3_core_api(paper, core_key=None):
    """Strategy 3: CORE API"""
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

def strategy_4_semantic_scholar(paper):
    """Strategy 4: Semantic Scholar API"""
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

def strategy_5_krishikosh_direct(paper):
    """Strategy 5: KrishiKosh specific handler"""
    link = paper.get('link', '')
    if 'krishikosh.egranth.ac.in' in link and '/handle/' in link:
        handle_id = link.split('/handle/')[-1]
        # Try constructing the standard bitstream URL for thesis.pdf
        try:
             # Most common pattern for KrishiKosh full text
             pdf_url = f"http://krishikosh.egranth.ac.in/bitstream/1/{handle_id}/1/thesis.pdf"
             res = download_file(pdf_url)
             if res: return res
        except: pass
    return None

def strategy_6_web_scraping_simple(paper):
    """Strategy 6: Simple scraping for href ending in .pdf"""
    link = paper.get('link', '')
    if not link: return None
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(link, headers=headers, timeout=10)
        # Find first link ending in .pdf
        matches = re.findall(r'href=["\'](http[^"\']+\.pdf)["\']', response.text)
        if matches:
            return download_file(matches[0])
    except: pass
    return None

# ==================== DOWNLOAD HELPER ====================

def download_file(url):
    """Helper to download and return bytes if it is a PDF"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200 and len(response.content) > 1000:
            if response.content.startswith(b'%PDF'):
                return response.content
    except: pass
    return None

# ==================== MAIN UI ====================

st.title("📥 Internal Paper Fetcher")
st.markdown("Fetching full-text PDFs into memory for **Analysis & Summarization** in the next step.")

# Initialize Session State for Downloads
if "downloaded_papers" not in st.session_state:
    st.session_state.downloaded_papers = {}  # Format: {paper_id: {'bytes': b'...', 'title': ...}}

if "selected_paper_ids" not in st.session_state or not st.session_state.selected_paper_ids:
    st.warning("⚠️ No papers selected. Please go back to Sorting.")
    if st.button("← Back to Sorting"):
        st.switch_page("pages/3_Sorting_and_Filtering.py")
    st.stop()

# Get selected papers objects
all_scored = st.session_state.get("scored_papers", [])
selected_papers = [p for p in all_scored if p['id'] in st.session_state.selected_paper_ids]

# Display Stats
col1, col2, col3 = st.columns(3)
col1.metric("Selected Papers", len(selected_papers))
already_downloaded = len([p for p in selected_papers if p['id'] in st.session_state.downloaded_papers])
col2.metric("Ready in Memory", already_downloaded)
col3.metric("Pending", len(selected_papers) - already_downloaded)

st.divider()

# API Keys (Optional)
with st.expander("⚙️ Connection Settings"):
    core_key = st.text_input("CORE API Key (Optional)", type="password", value=st.session_state.get("core_key", ""))

# ==================== EXECUTION LOGIC ====================

start_btn = st.button("🚀 Start Internal Fetching", type="primary", use_container_width=True)

if start_btn:
    progress_bar = st.progress(0)
    status_container = st.container(border=True)
    
    success_count = 0
    
    with status_container:
        for idx, paper in enumerate(selected_papers):
            # Skip if already in memory
            if paper['id'] in st.session_state.downloaded_papers:
                st.success(f"✅ Already Loaded: {paper['title']}")
                success_count += 1
                continue
            
            st.write(f"🔄 Fetching: **{paper['title'][:60]}...**")
            
            pdf_bytes = None
            used_strategy = "None"
            
            # 1. Direct
            if not pdf_bytes:
                pdf_bytes = strategy_1_direct_link(paper)
                used_strategy = "Direct Link"
            
            # 2. Unpaywall
            if not pdf_bytes:
                pdf_bytes = strategy_2_unpaywall(paper)
                used_strategy = "Unpaywall"
            
            # 3. CORE
            if not pdf_bytes:
                pdf_bytes = strategy_3_core_api(paper, core_key)
                used_strategy = "CORE API"
                
            # 4. Semantic Scholar
            if not pdf_bytes:
                pdf_bytes = strategy_4_semantic_scholar(paper)
                used_strategy = "Semantic Scholar"
                
            # 5. KrishiKosh (Theses)
            if not pdf_bytes:
                pdf_bytes = strategy_5_krishikosh_direct(paper)
                used_strategy = "KrishiKosh Direct"
                
            # 6. Simple Scraping
            if not pdf_bytes:
                pdf_bytes = strategy_6_web_scraping_simple(paper)
                used_strategy = "Web Scrape"
            
            # SAVE TO MEMORY
            if pdf_bytes:
                st.session_state.downloaded_papers[paper['id']] = {
                    'title': paper['title'],
                    'category': paper.get('category', 'Research'),
                    'bytes': pdf_bytes,
                    'source': used_strategy,
                    'file_size': f"{len(pdf_bytes)/1024/1024:.2f} MB"
                }
                st.caption(f"Success via {used_strategy}")
                success_count += 1
            else:
                st.error(f"❌ Failed to fetch PDF source.")
                
            progress_bar.progress((idx + 1) / len(selected_papers))
            time.sleep(0.5)

    st.success(f"🎉 Fetching Complete! {success_count}/{len(selected_papers)} papers are in memory.")
    st.rerun() # Rerun to update the "Proceed" state

# ==================== NEXT STEP NAVIGATION ====================

if len(st.session_state.downloaded_papers) > 0:
    st.divider()
    st.subheader("🏁 Ready for Analysis")
    st.write(f"You have **{len(st.session_state.downloaded_papers)}** full-text papers stored in memory.")
    
    if st.button("📖 Proceed to Reading & Summary", type="primary", use_container_width=True):
        st.switch_page("pages/5_Paper_Reading.py")
