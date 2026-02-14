import requests
import json
from datetime import datetime
import time

# --- CONFIGURATION ---
MY_PAPERS = {
    "paper1": "ARXIV:2109.15230",
    "paper2": "ARXIV:1805.07750",
    "paper3": "ARXIV:2503.06224",
    "paper4": "ARXIV:2012.02187"
}

def make_request(url, params, retries=3):
    """Robust request handler with retry logic."""
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                print(f"      ⏳ Rate limit hit. Waiting 5 seconds...")
                time.sleep(5)
                continue
            elif response.status_code == 404:
                return None
        except requests.exceptions.RequestException:
            time.sleep(1)
    return None

def get_direct_arxiv_pdf(paper_data):
    """
    FORCE construction of a direct ArXiv PDF link.
    Pattern: https://arxiv.org/pdf/XXXX.XXXX.pdf
    """
    if not paper_data: 
        return "#"

    # 1. Look for the ArXiv ID in externalIds
    external_ids = paper_data.get('externalIds', {})
    if external_ids and external_ids.get('ArXiv'):
        arxiv_id = external_ids['ArXiv']
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    
    # 2. Backup: Sometimes it's not in externalIds but the paperId itself is the ArXiv ID
    # (Semantic Scholar often uses the ArXiv ID as the paperId for arXiv papers)
    paper_id = paper_data.get('paperId', '')
    if paper_id and len(paper_id) > 5 and paper_id[0].isdigit() and '.' in paper_id:
         # Rough heuristic: if it looks like 2109.15230
         return f"https://arxiv.org/pdf/{paper_id}.pdf"

    # 3. Final Fallback: If absolutely no ArXiv ID is found, use the landing page
    return paper_data.get('url', '#')

def fetch_all_data():
    all_citations = []
    my_paper_details = {} 
    
    # Request 'externalIds' so we can extract the ArXiv number
    fields_query = "title,authors,year,abstract,url,externalIds"
    
    print(f"📨 Fetching metadata for {len(MY_PAPERS)} papers...")

    for internal_id, paper_uid in MY_PAPERS.items():
        print(f"🔎 Processing {internal_id} ({paper_uid})...")
        base_url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_uid}"
        
        # 1. Fetch YOUR paper's metadata
        p = make_request(base_url, {"fields": fields_query})
        
        if p:
            authors = p.get('authors', [])
            author_str = f"{authors[0]['name']} et al." if authors else "Me"
            
            # Use the direct link builder
            pdf_link = get_direct_arxiv_pdf(p)

            my_paper_details[internal_id] = {
                "title": p.get('title'),
                "author": author_str,
                "abstract": p.get('abstract', "No abstract found."),
                "link": pdf_link,
                "year": p.get('year')
            }
        else:
            print(f"   ⚠️ WARNING: Metadata missing for {paper_uid}")
            my_paper_details[internal_id] = {
                "title": f"Paper {internal_id} (Not Found)", "author": "Me", 
                "abstract": "Error fetching data.", "link": "#", "year": "N/A"
            }

        # 2. Fetch CITATIONS
        cite_data = make_request(f"{base_url}/citations", {"fields": fields_query, "limit": 50})
        
        if cite_data:
            citations_list = cite_data.get('data', [])
            print(f"   ✅ Found {len(citations_list)} citations.")
            
            for item in citations_list:
                cp = item.get('citingPaper')
                if not cp or not cp.get('title'): continue
                
                auth_list = cp.get('authors', [])
                auth_name = f"{auth_list[0]['name']} et al." if auth_list else "Unknown"
                
                # Use the direct link builder for citations too
                pdf_link = get_direct_arxiv_pdf(cp)

                all_citations.append({
                    "paperId": internal_id,
                    "author": auth_name,
                    "title": cp.get('title'),
                    "date": str(cp.get('year', '')),
                    "abstract": cp.get('abstract', "No abstract available."),
                    "link": pdf_link
                })
        
        time.sleep(1)

    # --- SAVE TO FILE ---
    now = datetime.now().strftime("%d %B %Y, %H:%M")
    try:
        with open("citations_data.js", "w") as f:
            f.write(f"const citations = {json.dumps(all_citations, indent=4)};\n")
            f.write(f"const myPaperDetails = {json.dumps(my_paper_details, indent=4)};\n")
            f.write(f"const lastUpdated = '{now}';")
        print(f"\n✅ Success! Data saved to citations_data.js")
    except Exception as e:
        print(f"❌ Error writing file: {e}")

if __name__ == "__main__":
    fetch_all_data()
