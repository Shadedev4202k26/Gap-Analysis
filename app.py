def get_strain_profile(api_key, strain_name):
    # Formulate exact AllBud URL pattern slug conventions
    formatted_slug = strain_name.strip().lower().replace(" ", "-")
    target_url = f"https://www.allbud.com/marijuana-strains/{formatted_slug}"
    
    scraped_html_context = ""
    
    # Attempt 1: Standard request with advanced browser headers
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        }
        response = requests.get(target_url, headers=headers, timeout=8)
        
        # If Cloudflare blocks it (403), we handle it in the fallback block
        if response.status_code == 200 and "cloudflare" not in response.text.lower():
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # AllBud DOM Targets: Check both class variations and standard tags
            lineage_element = soup.find(class_="lineage") or soup.find(class_="genetics")
            description_element = soup.find(id="strain-description") or soup.find(class_="description")
            
            extracted_text = []
            if lineage_element:
                extracted_text.append(f"Direct Lineage Section: {lineage_element.get_text(strip=True)}")
            if description_element:
                extracted_text.append(f"Main Description Narrative: {description_element.get_text(strip=True)}")
                
            scraped_html_context = "\n".join(extracted_text)
    except Exception:
        pass

    # Attempt 2: Heavy Fallback Engine (Engaged if Scraping is blocked or 404s)
    # We alter the search logic to extract the actual snippet instead of strict URL scraping
    if not scraped_html_context or len(scraped_html_context) < 30:
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                # Broaden the search constraint slightly so DuckDuckGo returns descriptive snippets
                fallback_query = f'site:allbud.com/marijuana-strains/ "{strain_name}"'
                search_results = [r for r in ddgs.text(fallback_query, max_results=3)]
                
                if search_results:
                    context_fragments = []
                    for result in search_results:
                        context_fragments.append(f"Source Snippet: {result['body']}")
                    scraped_html_context = "\n".join(context_fragments)
        except Exception as e:
            scraped_html_context = f"All retrieval vectors exhausted. Error: {str(e)}"

    # Process via Llama-3.3-70b to interpret the combined context data
    url = "https://api.groq.com/openai/v1/chat/completions"
    api_headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    system_prompt = (
        "You are a factual cannabis data extraction parser. Your sole objective is formatting the provided text data into structured JSON.\n"
        "Analyze the provided text fragments, snippets, or descriptions carefully to isolate the true genetic lineage and strain characteristics.\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "1. Identify the direct parent strains (e.g., 'Wedding Cake X Gelato #33') if mentioned anywhere in the narrative or snippets.\n"
        "2. Look for keywords like 'cross between', 'hybrid of', 'parents', or 'lineage'.\n"
        "3. If the text does not explicitly reveal the parent genetics after deep inspection, return 'Proprietary / Unverified Genetics' for the lineage value.\n"
        "4. Filter out any noise, such as lists of unrelated similar strains or dispensary ads.\n\n"
        "Return ONLY a clean, valid JSON object containing exactly these keys: 'classification', 'lineage', 'terpenes', 'flavor', 'effects'."
    )
    
    payload = {
        "model": "llama-3.3-70b-versatile", 
        "messages": [
            {"role": "system", "content": system_prompt}, 
            {"role": "user", "content": f"Raw Retrieved Data:\n{scraped_html_context}\n\nTarget Strain to Extract: {strain_name}"}
        ], 
        "temperature": 0.0
    }
    
    try:
        res = requests.post(url, headers=api_headers, json=payload, timeout=12)
        if res.status_code == 200:
            content = res.json()['choices'][0]['message']['content'].strip()
            if "{" in content and "}" in content: 
                content = content[content.find("{"):content.rfind("}") + 1]
            return json.loads(content)
    except Exception:
        pass
        
    return {"classification": "HYBRID", "lineage": "Proprietary / Unverified Genetics", "terpenes": "N/A", "flavor": "N/A", "effects": "N/A"}
