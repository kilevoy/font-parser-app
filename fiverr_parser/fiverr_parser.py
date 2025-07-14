import json, os, re, sys, requests
from urllib.parse import urlparse, quote
from openai import OpenAI
from difflib import SequenceMatcher

APIFY_TOKEN = os.getenv('APIFY_TOKEN', '')  # токен из переменной окружения

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

# Affiliate config
AFFILIATE_BTA = os.getenv('FIVERR_BTA', '1048834')  # ваш ID
AFFILIATE_BRAND = os.getenv('FIVERR_BRAND', 'fp')   # fp = Fiverr Pro, fiverrmarketplace = обычный

APIFY_ACT_ID = os.getenv('APIFY_ACT_ID', 'L6I0baErLZR5rW2lN')  # Fiverr actor

class FiverrParser:
    def __init__(self):
        self.firecrawl_headers = {
            'Authorization': f'Bearer {APIFY_TOKEN}',
            'Content-Type': 'application/json'
        }
        try:
            self.openai = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        except Exception as e:
            print(f"Error initializing OpenAI client in FiverrParser: {str(e)}")
            self.openai = None

    def is_valid(self, url:str):
        p = urlparse(url)
        return p.netloc.endswith('fiverr.com') and '/gig/' not in p.path    # gig URLs are /username/title

    def apify_fetch(self, url:str):
        """Scrape Fiverr gig HTML via Apify actor run-sync-dataset-items."""
        # Документация: https://docs.apify.com/api/v2#/reference/actors/run-actor-and-get-dataset-items
        endpoint = (
            f"https://api.apify.com/v2/acts/{APIFY_ACT_ID}/run-sync-dataset-items"
            f"?token={APIFY_TOKEN}&format=json&clean=true&simplified=1"
        )
        payload = {"startUrls": [{"url": url}]}
        try:
            r = requests.post(endpoint, json=payload, timeout=90)
            if r.status_code == 200:
                items = r.json()
                if isinstance(items, list) and items:
                    return {"html": items[0].get("html",""), "markdown": items[0].get("markdown","")}
        except Exception:
            pass
        # Fallback – попробовать обычный GET (может не пройти Cloudflare, но попробуем)
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 200:
                return {"html": resp.text, "markdown": ""}
        except Exception:
            pass
        return {}

    def parse(self, url:str):
        if not self.is_valid(url):
            return {'error':'Invalid Fiverr URL'}
        data = self.apify_fetch(url)
        html = data.get('html','')
        md = data.get('markdown','')

        title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        title = re.sub('<[^>]+>','', title_match.group(1)).strip() if title_match else ''

        # если основные поля не найдены регулярками – используем OpenAI для структурного парсинга
        if not title:
            if not self.openai:
                title = 'Gig Title'
                desc = ''
                seller = 'seller'
                rating_val = None
                reviews = None
                images = []
                packages_json = []
            else:
                try:
                    md = data.get('markdown','')[:12000]
                    prompt = f"""You are given the raw markdown of a Fiverr gig page. Extract the following fields and return EXACT JSON with these keys:
{{
  \"gig_title\": \"...\",
  \"description\": \"...\",
  \"seller_username\": \"...\",
  \"package_prices\": [{{\"name\":\"Basic|Standard|Premium\",\"price\":\"$25\"}}],
  \"images\": [\"https://...\"],
  \"rating\": 4.9,
  \"reviews\": 153
}}

Only output JSON, no other text. Markdown:\n---\n{md}\n---"""
                    ai_resp = self.openai.chat.completions.create(model=MODEL,messages=[{"role":"user","content":prompt}],response_format={"type":"json_object"},temperature=0)
                    parsed = json.loads(ai_resp.choices[0].message.content)
                    title = parsed.get('gig_title','')
                    desc = parsed.get('description','')
                    seller = parsed.get('seller_username','')
                    rating_val = parsed.get('rating')
                    reviews = parsed.get('reviews')
                    images = parsed.get('images',[])
                    packages_json = parsed.get('package_prices',[])
                except Exception:
                    title = title or 'Gig Title'
                    desc = ''
                    seller = 'seller'
                    rating_val = None
                    reviews = None
                    images = []
                    packages_json = []
        else:
            desc_match = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', html)
            desc = desc_match.group(1) if desc_match else ''
            seller_match = re.search(r'@([A-Za-z0-9_]+)</a>', html)
            seller = seller_match.group(1) if seller_match else 'seller'
            rating = re.search(r'(\d\.\d)\s*\(<span[^>]*>(\d+,?\d*)', html)
            rating_val = float(rating.group(1)) if rating else None
            reviews = int(rating.group(2).replace(',','')) if rating else None
            images = re.findall(r'https://fiverr-res\.cloudinary\.com/[^"\']+\.(?:jpg|png)', html)
            images = list(dict.fromkeys(images))
            images = [img for img in images if not re.search(r'favicon|pdf_thumb|profile_small', img, re.I)]
            images = list(dict.fromkeys(images))[:15]
            packages = re.findall(r'"price":(\d+),"packageName":"(Basic|Standard|Premium)"', html)
            packages_json = [{"name":p[1],"price":f"${p[0]}"} for p in packages]

        about_text = self.extract_about_section(html, md)

        result = {
            'gig_title': title,
            'description': desc,
            'about': about_text,
            'seller': {'username': seller, 'rating': rating_val, 'reviews': reviews},
            'packages': packages_json,
            'images': images,
            'affiliate_url': self.build_affiliate_link(url)
        }

        # detect primary keyword from gig title (1-3 words)
        primary_kw = self.extract_primary_keyword(title)

        # AI enrich prompt using whatever title/desc we obtained
        result['sora_prompt'] = self.generate_prompt(title or 'Gig', desc or '', images[:3])

        # Pinterest SEO generate (dynamic keyword)
        result['pinterest_seo'] = self.generate_pinterest_seo(title or 'Gig', desc or '', about_text, primary_kw)
        return result

    def generate_prompt(self, title, description, refs):
        refs_txt = ', '.join(refs)
        prompt = f"Create an eye-catching vertical Pinterest Pin (9:16) advertising my creative service titled '{title}'. Use references {refs_txt} to match style. Highlight key benefits from description: {description[:200]} …. Add clear call-to-action 'Order Now'. Luxurious, professional design, sharp typography, high contrast, no watermark. #SORA_PROMPT"
        
        if not self.openai:
            return prompt
            
        try:
            res = self.openai.chat.completions.create(model=MODEL, messages=[{"role":"user","content":prompt}], temperature=0.8)
            return res.choices[0].message.content.strip()
        except Exception:
            return prompt

    def generate_pinterest_seo(self, gig_title, description, about_text, primary_keyword):
        """Generate TOP-TIER Pinterest SEO content using best practices."""
        
        prompt = f"""**TASK**: Act as a world-class Pinterest SEO and conversion copywriter. Create a high-click-through-rate Pin for the following creative service.

**CONTEXT**:
- Gig Title: {gig_title}
- Description Snippet: {description[:300]}
- About the Gig Snippet: {about_text[:600] if about_text else ''}
- Primary Keyword: {primary_keyword}

**RULES**:
1.  **Title (max 55 chars)**: MUST be compelling. Use numbers, power words (e.g., "Stunning," "Hand-Drawn"), or brackets. AVOID starting with "I will." Focus on the result or unique value.
2.  **Description (180-220 chars)**: MUST start with the primary keyword. Weave in benefits from the context, use social proof (like "100+ projects" if mentioned), and have a strong Call-To-Action.
3.  **Disclosure**: The description MUST end with the exact phrase "Please note: this is an affiliate link. #ad". No other hashtags.
4.  **Keywords**: Provide 5-8 highly relevant long-tail keywords.

**OUTPUT (Strict JSON)**:
{{
  "pin_title": "...",
  "pin_description": "...",
  "keywords_used": ["long-tail keyword 1", "long-tail keyword 2", "..."]
}}"""

        def _too_similar(a: str, b: str) -> bool:
            return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= 0.25

        def sanitize_title(t: str) -> str:
            t = re.sub(r"^(i will|i['']ll|we will)\s+", '', t, flags=re.I).strip()
            t = t[:55]
            if '–' in t or '-' in t:
                parts = re.split(r'–|-', t)
                if len(parts) > 1 and len(parts[-1].strip()) < 4:
                    t = parts[0].strip()
            if len(t) == 55 and ' ' in t:
                 t = t.rsplit(' ', 1)[0]
            return t.capitalize()

        if not self.openai:
            result = {}
        else:
            try:
                resp = self.openai.chat.completions.create(
                    model=MODEL,
                    messages=[{"role": "system", "content": "You are a Pinterest SEO expert following instructions precisely."}, {"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.8,
                    timeout=25.0
                )
                result = json.loads(resp.choices[0].message.content)
            except Exception:
                result = {}

        final_title = sanitize_title(result.get('pin_title', ''))
        if not final_title:
            final_title = f"{primary_keyword.capitalize()} - Hand-Crafted For You"
        result['pin_title'] = final_title

        desc_txt = result.get('pin_description', '')
        banned_phrases = ["fiverr freelancer will provide", "i will provide", gig_title.lower()]
        for phrase in banned_phrases:
            desc_txt = desc_txt.lower().replace(phrase, "").strip()

        if _too_similar(desc_txt, description) or len(desc_txt) < 120:
            try:
                rewrite_prompt = f"Rewrite this description to be unique and benefit-focused (180-220 chars), starting with '{primary_keyword}'. Context: {description} {about_text}"
                rewrite_resp = self.openai.chat.completions.create(
                    model=MODEL,
                    messages=[{"role":"user", "content": rewrite_prompt}],
                    temperature=0.9
                )
                desc_txt = rewrite_resp.choices[0].message.content.strip()
            except Exception:
                desc_txt = f"{primary_keyword.capitalize()}: Get a stunning, professionally made piece for your project. High-quality and delivered fast. Tap to order now!"

        disclosure = "Please note: this is an affiliate link."
        if disclosure.lower() not in desc_txt.lower():
            desc_txt = desc_txt.rstrip('. ') + f". {disclosure}"
        if '#ad' not in desc_txt.lower():
            desc_txt = desc_txt.rstrip('. ') + " #ad"
        
        result['pin_description'] = desc_txt[:500]

        keywords = result.get('keywords_used', [])
        if not keywords or len(keywords) < 3:
            keywords = [primary_keyword, "custom " + primary_keyword, "freelance artist", "digital art", "unique gift"]
        result['keywords_used'] = keywords[:8]

        return result

    def build_affiliate_link(self, gig_url:str):
        encoded = quote(gig_url, safe='')
        return f"https://go.fiverr.com/visit/?bta={AFFILIATE_BTA}&brand={AFFILIATE_BRAND}&landingPage={encoded}"

    def extract_primary_keyword(self, title:str)->str:
        """Return 1-3 word primary service keyword derived from the gig title."""
        # First, clean the title from standard Fiverr prefixes
        cleaned_title = re.sub(r"^(i will|i'll|i'll|we will)\s+", '', title, flags=re.I).strip()
        
        try:
            prompt = (
                "From the following creative service title, extract the core service keyword phrase (2-4 words, lowercase). "
                "Examples:\n"
                "- 'design a modern logo for your business' -> 'modern logo design'\n"
                "- 'create a stunning saas website ui' -> 'saas website ui'\n"
                "- 'be your professional video editor' -> 'professional video editor'\n"
                "Title: " + cleaned_title)
            resp = self.openai.chat.completions.create(model=MODEL, messages=[{"role":"user","content":prompt}], temperature=0, timeout=10)
            kw = resp.choices[0].message.content.strip().lower()
            kw = re.sub(r'[^a-zA-Z0-9\s-]', '', kw) # allow hyphens
            # sanity check
            if 0 < len(kw.split()) <= 4 and kw != "i will":
                return kw
        except Exception:
            pass # Fallback to heuristic below
            
        # New heuristic fallback – take the first 3 words of the cleaned title
        return ' '.join(cleaned_title.lower().split()[:3])

    def extract_about_section(self, html:str, md:str) -> str:
        """Return plain-text of the 'About This Gig' section if present."""
        about = ''
        if md:
            m = re.search(r'#+\s*About\s+This\s+Gig[^\n]*\n(.*?)(?:\n#+|$)', md, re.I|re.S)
            if m:
                about = m.group(1).strip()
        if not about and html:
            m = re.search(r'(?:About\s+This\s+Gig)[\s\S]{0,2000}?<[^>]*>([\s\S]*?)</div>', html, re.I)
            if m:
                raw = m.group(1)
                about = re.sub('<[^>]+>',' ', raw)
                about = re.sub(r'\s+',' ', about).strip()
        return about

if __name__ == '__main__':
    if len(sys.argv)<2:
        print('Usage: python fiverr_parser.py <fiverr_gig_url>'); sys.exit(1)
    parser = FiverrParser()
    data = parser.parse(sys.argv[1])
    print(json.dumps(data, ensure_ascii=False, indent=2)) 