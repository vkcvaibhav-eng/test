import streamlit as st
import requests
import time
from pathlib import Path
import re
from urllib.parse import quote, urljoin
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import zipfile
import io

st.set_page_config(page_title="PDF Downloader", layout="wide")

# ==================== DOWNLOAD STRATEGIES ====================

def strategy_1_direct_link(paper):
    """Strategy 1: Direct PDF link from search results"""
    link = paper.get('link', '')
    
    # Check if already a PDF
    if link.endswith('.pdf'):
        return download_file(link, f"direct_{paper['id']}.pdf")
    
    # Try adding .pdf to known domains
    if 'arxiv.org' in link:
        arxiv_id = link.split('/')[-1]
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        return download_file(pdf_url, f"arxiv_{paper['id']}.pdf")
    
    return None

def strategy_2_unpaywall(paper):
    """Strategy 2: Unpaywall API - Best for DOI papers"""
    link = paper.get('link', '')
    
    # Extract DOI
    doi = None
    if 'doi.org/' in link:
        doi = link.split('doi.org/')[-1]
    elif paper.get('snippet') and '10.' in paper['snippet']:
        doi_match = re.search(r'10\.\d{4,}/[^\s]+', paper['snippet'])
        if doi_match:
            doi = doi_match.group()
    
    if doi:
        try:
            url = f"https://api.unpaywall.org/v2/{doi}?email=research@agriculture.com"
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                
                # Try all available locations
                if data.get('best_oa_location') and data['best_oa_location'].get('url_for_pdf'):
                    pdf_url = data['best_oa_location']['url_for_pdf']
                    return download_file(pdf_url, f"unpaywall_{paper['id']}.pdf")
                
                # Try other OA locations
                for loc in data.get('oa_locations', []):
                    if loc.get('url_for_pdf'):
                        result = download_file(loc['url_for_pdf'], f"unpaywall_alt_{paper['id']}.pdf")
                        if result:
                            return result
        except Exception as e:
            st.write(f"  Unpaywall error: {e}")
    
    return None

def strategy_3_core_api(paper, core_key=None):
    """Strategy 3: CORE API - 200M+ papers"""
    try:
        url = "https://api.core.ac.uk/v3/search/works"
        headers = {}
        if core_key:
            headers["Authorization"] = f"Bearer {core_key}"
        
        params = {"q": paper['title'], "limit": 5}
        response = requests.post(url, json=params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            results = response.json().get('results', [])
            for result in results:
                if result.get('downloadUrl'):
                    pdf = download_file(result['downloadUrl'], f"core_{paper['id']}.pdf")
                    if pdf:
                        return pdf
    except Exception as e:
        st.write(f"  CORE error: {e}")
    
    return None

def strategy_4_semantic_scholar(paper):
    """Strategy 4: Semantic Scholar API"""
    try:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": paper['title'],
            "fields": "openAccessPdf,isOpenAccess,externalIds",
            "limit": 3
        }
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            for item in data.get('data', []):
                if item.get('openAccessPdf') and item['openAccessPdf'].get('url'):
                    pdf = download_file(item['openAccessPdf']['url'], f"semantic_{paper['id']}.pdf")
                    if pdf:
                        return pdf
    except Exception as e:
        st.write(f"  Semantic Scholar error: {e}")
    
    return None

def strategy_5_google_scholar_scrape(paper, serp_key):
    """Strategy 5: Google Scholar via SerpAPI - Find [PDF] links"""
    try:
        from serpapi import GoogleSearch
        
        params = {
            "engine": "google_scholar",
            "q": paper['title'],
            "api_key": serp_key,
            "num": 5
        }
        
        search = GoogleSearch(params)
        results = search.get_dict()
        
        # Look for PDF links in results
        for res in results.get('organic_results', []):
            # Check for PDF resources
            if res.get('resources'):
                for resource in res['resources']:
                    if resource.get('file_format') == 'PDF' and resource.get('link'):
                        pdf = download_file(resource['link'], f"scholar_{paper['id']}.pdf")
                        if pdf:
                            return pdf
            
            # Check inline links
            if res.get('inline_links') and res['inline_links'].get('cited_by'):
                link = res['inline_links'].get('cited_by', {}).get('link')
                if link and '.pdf' in link:
                    pdf = download_file(link, f"scholar_inline_{paper['id']}.pdf")
                    if pdf:
                        return pdf
    except Exception as e:
        st.write(f"  Google Scholar error: {e}")
    
    return None

def strategy_6_researchgate_scrape(paper):
    """Strategy 6: ResearchGate search and scrape"""
    try:
        # Search ResearchGate
        search_url = f"https://www.researchgate.net/search/publication?q={quote(paper['title'])}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(search_url, headers=headers, timeout=15)
        
        # Look for PDF links in the response
        pdf_pattern = r'https://www\.researchgate\.net/[^"]*\.pdf'
        matches = re.findall(pdf_pattern, response.text)
        
        for match in matches[:3]:
            pdf = download_file(match, f"rg_{paper['id']}.pdf", headers=headers)
            if pdf:
                return pdf
    except Exception as e:
        st.write(f"  ResearchGate error: {e}")
    
    return None

def strategy_7_krishikosh_direct(paper):
    """Strategy 7: KrishiKosh specific handler for Indian theses"""
    link = paper.get('link', '')
    
    if 'krishikosh.egranth.ac.in' in link:
        try:
            # KrishiKosh URLs pattern: /handle/1/12345
            if '/handle/' in link:
                handle_id = link.split('/handle/')[-1]
                
                # Try common KrishiKosh PDF patterns
                pdf_patterns = [
                    f"http://krishikosh.egranth.ac.in/bitstream/1/{handle_id}/1/thesis.pdf",
                    f"http://krishikosh.egranth.ac.in/bitstream/1/{handle_id}/2/thesis.pdf",
                    f"http://krishikosh.egranth.ac.in/bitstream/handle/1/{handle_id}/thesis.pdf",
                ]
                
                for pdf_url in pdf_patterns:
                    pdf = download_file(pdf_url, f"krishikosh_{paper['id']}.pdf")
                    if pdf:
                        return pdf
                
                # Scrape the page for bitstream links
                response = requests.get(link, timeout=15)
                bitstream_pattern = r'/bitstream/[^"\'>\s]+'
                matches = re.findall(bitstream_pattern, response.text)
                
                for match in matches:
                    full_url = urljoin(link, match)
                    if '.pdf' in full_url.lower():
                        pdf = download_file(full_url, f"krishikosh_scraped_{paper['id']}.pdf")
                        if pdf:
                            return pdf
        except Exception as e:
            st.write(f"  KrishiKosh error: {e}")
    
    return None

def strategy_8_sci_hub(paper, doi=None):
    """Strategy 8: Sci-Hub (LAST RESORT - use carefully)"""
    # Extract DOI if not provided
    if not doi:
        link = paper.get('link', '')
        if 'doi.org/' in link:
            doi = link.split('doi.org/')[-1]
    
    if doi:
        try:
            # Sci-Hub mirrors (these change frequently)
            mirrors = [
                "https://sci-hub.se",
                "https://sci-hub.st",
                "https://sci-hub.ru",
            ]
            
            for mirror in mirrors:
                try:
                    url = f"{mirror}/{doi}"
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    response = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
                    
                    # Look for PDF iframe or direct link
                    pdf_pattern = r'(https?://[^"\'>\s]+\.pdf[^"\'>\s]*)'
                    matches = re.findall(pdf_pattern, response.text)
                    
                    for match in matches:
                        if 'sci-hub' in match or 'twin.sci-hub' in match:
                            pdf = download_file(match, f"scihub_{paper['id']}.pdf", headers=headers)
                            if pdf:
                                st.warning("⚠️ Downloaded via Sci-Hub - Check copyright laws in your country")
                                return pdf
                except:
                    continue
        except Exception as e:
            st.write(f"  Sci-Hub error: {e}")
    
    return None

def strategy_9_web_scraping(paper):
    """Strategy 9: Generic web scraping for PDF links"""
    link = paper.get('link', '')
    if not link or link.endswith('.pdf'):
        return None
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(link, headers=headers, timeout=15)
        
        # Look for PDF links on the page
        pdf_patterns = [
            r'href=["\']([^"\']*\.pdf[^"\']*)["\']',
            r'(https?://[^\s<>"]+\.pdf)',
            r'data-url=["\']([^"\']*\.pdf[^"\']*)["\']',
        ]
        
        all_pdfs = []
        for pattern in pdf_patterns:
            matches = re.findall(pattern, response.text)
            all_pdfs.extend(matches)
        
        # Try each PDF link found
        for pdf_url in all_pdfs[:5]:
            # Make absolute URL
            if pdf_url.startswith('/'):
                pdf_url = urljoin(link, pdf_url)
            
            pdf = download_file(pdf_url, f"scraped_{paper['id']}.pdf", headers=headers)
            if pdf:
                return pdf
    except Exception as e:
        st.write(f"  Web scraping error: {e}")
    
    return None

# ==================== DOWNLOAD HELPER ====================

def download_file(url, filename, headers=None):
    """Actually download the file"""
    try:
        if headers is None:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        
        response = requests.get(url, headers=headers, timeout=30, stream=True)
        
        # Check if it's actually a PDF
        content_type = response.headers.get('Content-Type', '')
        if response.status_code == 200:
            # Read first few bytes
            content = b''
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
                if len(content) > 1024:  # Check first 1KB
                    break
            
            # PDF signature check
            if content.startswith(b'%PDF'):
                # Download full file
                response = requests.get(url, headers=headers, timeout=30)
                return response.content
            else:
                st.write(f"  ❌ Not a PDF: {content_type}")
    except Exception as e:
        st.write(f"  Download error: {e}")
    
    return None

# ==================== MAIN UI ====================

st.title("📥 Force PDF Downloader")
st.caption("Tries EVERY possible method to download your selected papers")

if "selected_paper_ids" not in st.session_state or not st.session_state.selected_paper_ids:
    st.warning("⚠️ No papers selected. Please go back to Page 3.")
    if st.button("← Back to Sorting"):
        st.switch_page("pages/3_Sorting_and_Filtering.py")
    st.stop()

# Get selected papers
all_scored = st.session_state.get("scored_papers", [])
selected_papers = [p for p in all_scored if p['id'] in st.session_state.selected_paper_ids]

st.success(f"✅ {len(selected_papers)} papers ready to download")

# Organize by category
research_papers = [p for p in selected_papers if p.get('category') == 'Research Article']
review_papers = [p for p in selected_papers if p.get('category') == 'Review Paper']
theses = [p for p in selected_papers if p.get('category') == 'Thesis']

col1, col2, col3 = st.columns(3)
col1.metric("Research Papers", len(research_papers))
col2.metric("Review Papers", len(review_papers))
col3.metric("Theses", len(theses))

# Settings
with st.expander("⚙️ Download Settings"):
    serp_key = st.text_input("SerpAPI Key (optional)", type="password", 
                             value=st.session_state.get("serpapi_key", ""))
    core_key = st.text_input("CORE API Key (optional - get free at core.ac.uk)", 
                             type="password")
    
    use_scihub = st.checkbox("⚠️ Use Sci-Hub as last resort (check local laws)", value=False)
    
    download_folder = st.text_input("Download folder name", value="downloaded_papers")

st.divider()

# ==================== DOWNLOAD EXECUTION ====================

if st.button("🚀 START FORCE DOWNLOAD", type="primary"):
    
    # Create download folder
    output_dir = Path(download_folder)
    output_dir.mkdir(exist_ok=True)
    
    results = {
        'success': [],
        'failed': []
    }
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, paper in enumerate(selected_papers):
        status_text.write(f"📄 **Processing ({idx+1}/{len(selected_papers)}):** {paper['title'][:60]}...")
        
        with st.expander(f"[{paper.get('category', 'Unknown')}] {paper['title']}", expanded=False):
            st.write(f"**Score:** {paper.get('relevance_score', 'N/A')}%")
            st.write(f"**Source:** {paper.get('source', 'N/A')}")
            
            pdf_content = None
            successful_strategy = None
            
            # Try all strategies in order
            strategies = [
                ("Direct Link", lambda: strategy_1_direct_link(paper)),
                ("Unpaywall", lambda: strategy_2_unpaywall(paper)),
                ("CORE API", lambda: strategy_3_core_api(paper, core_key)),
                ("Semantic Scholar", lambda: strategy_4_semantic_scholar(paper)),
            ]
            
            if serp_key:
                strategies.append(("Google Scholar", lambda: strategy_5_google_scholar_scrape(paper, serp_key)))
            
            strategies.extend([
                ("ResearchGate", lambda: strategy_6_researchgate_scrape(paper)),
                ("KrishiKosh Direct", lambda: strategy_7_krishikosh_direct(paper)),
                ("Web Scraping", lambda: strategy_9_web_scraping(paper)),
            ])
            
            if use_scihub:
                strategies.append(("Sci-Hub", lambda: strategy_8_sci_hub(paper)))
            
            # Execute strategies
            for strategy_name, strategy_func in strategies:
                st.write(f"  🔄 Trying: **{strategy_name}**")
                try:
                    pdf_content = strategy_func()
                    if pdf_content:
                        successful_strategy = strategy_name
                        st.success(f"  ✅ Success via {strategy_name}!")
                        break
                except Exception as e:
                    st.write(f"  ❌ {strategy_name} failed: {e}")
                
                time.sleep(0.5)  # Rate limiting
            
            # Save the PDF
            if pdf_content:
                # Clean filename
                safe_title = re.sub(r'[^\w\s-]', '', paper['title'])[:100]
                safe_title = re.sub(r'\s+', '_', safe_title)
                
                category_folder = output_dir / paper.get('category', 'Unknown').replace(' ', '_')
                category_folder.mkdir(exist_ok=True)
                
                filename = f"{safe_title}_{paper['id']}.pdf"
                filepath = category_folder / filename
                
                with open(filepath, 'wb') as f:
                    f.write(pdf_content)
                
                results['success'].append({
                    'paper': paper,
                    'filepath': str(filepath),
                    'strategy': successful_strategy
                })
                
                st.download_button(
                    label="💾 Download PDF",
                    data=pdf_content,
                    file_name=filename,
                    mime="application/pdf",
                    key=f"download_{paper['id']}"
                )
            else:
                st.error("❌ All strategies failed")
                results['failed'].append(paper)
        
        progress_bar.progress((idx + 1) / len(selected_papers))
    
    # ==================== RESULTS SUMMARY ====================
    
    st.divider()
    st.header("📊 Download Summary")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("✅ Successfully Downloaded", len(results['success']))
        if results['success']:
            for item in results['success']:
                st.success(f"✓ {item['paper']['title'][:50]}... via {item['strategy']}")
    
    with col2:
        st.metric("❌ Failed Downloads", len(results['failed']))
        if results['failed']:
            for paper in results['failed']:
                st.error(f"✗ {paper['title'][:50]}...")
    
    # Create ZIP of all downloads
    if results['success']:
        st.divider()
        st.subheader("📦 Bulk Download")
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for item in results['success']:
                zip_file.write(item['filepath'], arcname=Path(item['filepath']).name)
        
        st.download_button(
            label="📦 Download All as ZIP",
            data=zip_buffer.getvalue(),
            file_name="all_papers.zip",
            mime="application/zip"
        )
        
        st.success(f"✅ All papers saved to: `{output_dir.absolute()}`")
