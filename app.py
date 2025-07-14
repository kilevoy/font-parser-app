from flask import Flask, render_template, request, jsonify
import json
import re
import requests
import os
from openai import OpenAI
from urllib.parse import urlparse
# Импорт парсера Fiverr гигов
from fiverr_parser.fiverr_parser import FiverrParser

# Конфигурация с поддержкой переменных окружения
FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
FIRECRAWL_BASE_URL = os.environ.get("FIRECRAWL_BASE_URL", "https://api.firecrawl.dev/v1")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://hubai.loe.gg/v1")
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

# Создаём Flask-приложение и насильно выключаем debug на уровне конфигурации,
# чтобы переменные окружения FLASK_DEBUG/FLASK_ENV не смогли вновь включить режим разработки
app = Flask(__name__)
app.config['ENV'] = 'production'
app.config['DEBUG'] = False

class FontWebParser:
    def __init__(self):
        self.firecrawl_headers = {
            "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
            "Content-Type": "application/json"
        }
        # Полностью отключаем OpenAI для тестирования
        self.openai_client = None
        print("OpenAI client completely disabled for testing")
    
    def parse_font_from_url(self, font_url):
        """Парсинг шрифта по URL"""
        try:
            # Валидация URL
            if not self.is_valid_cf_url(font_url):
                return {"error": "Некорректная ссылка на Creative Fabrica"}
            
            # Формируем URL для specimen страницы
            specimen_url = self.get_specimen_url(font_url)
            
            # Парсим основную страницу
            main_data = self.firecrawl_scrape(font_url)
            if not main_data:
                return {"error": "Не удалось загрузить основную страницу"}
            
            # Парсим specimen страницу
            specimen_data = self.firecrawl_scrape(specimen_url)
            if not specimen_data:
                return {"error": "Не удалось загрузить specimen страницу"}
            
            # Извлекаем данные
            font_info = self.extract_font_name_description(main_data)
            # Извлекаем главное превью изображения
            main_preview = self.extract_main_preview_image(main_data)
            # Извлекаем изображения глифов с обеих страниц и объединяем
            glyphs_specimen = self.extract_all_glyph_images(specimen_data)
            glyphs_main = self.extract_all_glyph_images(main_data)

            combined_list = []
            if main_preview:
                combined_list.append(main_preview)
            combined_list.extend(glyphs_specimen)
            combined_list.extend([img for img in glyphs_main if img not in combined_list])

            all_glyph_images = combined_list  # без ограничения количества
            
            # Генерируем все блоки
            result = {
                'font_name': font_info['name'],
                'description': font_info['description'],
                'all_glyph_images': all_glyph_images,
                'font_url': font_url,
                'affiliate_url': self.get_affiliate_url(font_url)
            }
            
            # Добавляем SEO и JSON контент
            result['pinterest_seo'] = self.generate_pinterest_seo(
                result['font_name'], 
                result['description']
            )
            result['pinterest_json'] = self.generate_pinterest_json_format(
                result['font_name'],
                result['pinterest_seo']['pin_description'],
                font_url
            )
            result['image_prompt'] = self.generate_image_prompt(result['font_name'], result['description'], all_glyph_images)
            
            return result
            
        except Exception as e:
            return {"error": f"Ошибка парсинга: {str(e)}"}
    
    def is_valid_cf_url(self, url):
        """Проверка корректности URL Creative Fabrica"""
        parsed = urlparse(url)
        return (parsed.netloc == 'www.creativefabrica.com' and 
                '/product/' in parsed.path)
    
    def get_specimen_url(self, font_url):
        """Получение URL specimen страницы"""
        if font_url.endswith('/'):
            return f"{font_url}view/specimen/"
        else:
            return f"{font_url}/view/specimen/"
    
    def get_affiliate_url(self, font_url):
        """Получение партнерской ссылки"""
        if font_url.endswith('/'):
            return f"{font_url}ref/8035929/?campaign=aut"
        else:
            return f"{font_url}/ref/8035929/?campaign=aut"
    
    def firecrawl_scrape(self, url):
        """Скрапинг через Firecrawl"""
        scrape_payload = {
            "url": url,
            "formats": ["html", "markdown"],
            "waitFor": 6000,
            "timeout": 45000
        }
        
        try:
            response = requests.post(
                f"{FIRECRAWL_BASE_URL}/scrape",
                headers=self.firecrawl_headers,
                json=scrape_payload,
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('data', {})
            else:
                return None
                
        except Exception as e:
            return None
    
    def extract_font_name_description(self, main_data):
        """Извлечение названия и описания шрифта"""
        content = main_data.get('markdown', '') or main_data.get('html', '')
        
        prompt = f"""Найди ТОЧНОЕ название шрифта и его описание в JSON формате:

{{
  "name": "Точное название шрифта",
  "description": "Полное описание шрифта и его особенностей"
}}

Контент: {content[:20000]}"""

        if not self.openai_client:
            return {
                "name": "Font Name",
                "description": "Beautiful typography font"
            }

        try:
            response = self.openai_client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "Извлекай точное название шрифта и его описание в JSON формате."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            print(f"OpenAI API error: {str(e)}")
            return {
                "name": "Font Name",
                "description": "Beautiful typography font"
            }
    
    def extract_all_glyph_images(self, specimen_data):
        """Извлечение всех изображений с глифами"""
        content = specimen_data.get('html', '') or specimen_data.get('markdown', '')
        
        # 1. URL из html/markdown
        image_pattern = r'https://[^"\'>\s]+\.(?:jpg|png|webp)'
        found_images = re.findall(image_pattern, content, flags=re.IGNORECASE)

        # 2. Масив images, который возвращает Firecrawl (содержит уже абсолютные ссылки)
        found_images.extend(specimen_data.get('images', []))
        
        # Дополнительно парсим srcset / data-src атрибуты
        srcset_matches = re.findall(r'srcset=["\']([^"\']+)["\']', content, flags=re.IGNORECASE)
        for srcset in srcset_matches:
            for part in srcset.split(','):
                url_part = part.strip().split(' ')[0]
                if url_part.startswith('https://'):
                    found_images.append(url_part)
        
        # Убираем дубликаты
        found_images = list(set(found_images))
        
        # Ищем изображения с глифами по ключевым словам
        glyph_keywords = ['glyph', 'allglyph', 'allglyphs', 'character', 'alphabet', 'specimen', 'font']
        
        glyph_images = []
        
        # Сначала добавляем изображения с высоким приоритетом ('allglyph', 'allglyphs')
        for img in found_images:
            img_lower = img.lower()
            if 'allglyph' in img_lower or 'allglyphs' in img_lower:
                glyph_images.append(img)
        
        # Затем добавляем изображения с обычным приоритетом
        for img in found_images:
            img_lower = img.lower()
            if img not in glyph_images:
                for keyword in glyph_keywords:
                    if keyword in img_lower:
                        glyph_images.append(img)
                        break
        
        # Формируем финальный список: сначала выбранные по ключевым словам,
        # затем остальные (если ещё не попали), сохраняя порядок.
        final_images = glyph_images + [img for img in found_images if img not in glyph_images]

        # Вторая стадия – если ничего не нашли, пробуем взять все images и отфильтровать по размеру glyph (обычно >400px ширина),
        # но Firecrawl не несёт размеров, поэтому fallback ограничимся первыми 20 картинками.
        if not final_images and specimen_data.get('images'):
            final_images = specimen_data['images'][:20]

        # Ограничиваем общее количество до 60, чтобы не перегружать фронт
        if len(final_images) > 60:
            final_images = final_images[:60]

        return final_images  # без ограничений количества
    
    def generate_pinterest_seo(self, font_name, description):
        """Генерация Pinterest SEO контента"""
        prompt = f"""**PINTEREST SEO OPTIMIZATION PROMPT**

**TASK**: Create SEO-optimized Pinterest pin titles and descriptions in English

**CONTEXT**: You are a Pinterest SEO expert creating content for font design/typography niche.

**INPUT PROVIDED**:
- Main keyword: {font_name}
- Target audience: Graphic designers, crafters, DIY enthusiasts, small business owners

**Font Information**:
- Font Name: {font_name}
- Description: {description[:300]}

Provide response in JSON format:
{{
  "pin_titles": [
    "Title option 1",
    "Title option 2", 
    "Title option 3"
  ],
  "pin_description": "Complete optimized description",
  "keywords_used": ["keyword1", "keyword2", "keyword3"],
  "optimization_notes": "Brief explanation of SEO choices"
}}"""

        if not self.openai_client:
            return {
                "pin_titles": [
                    f"Beautiful {font_name} - Perfect Typography",
                    f"Download {font_name} - Stunning Font Design", 
                    f"Creative {font_name} - Typography Collection"
                ],
                "pin_description": f"Discover the amazing {font_name}! Perfect for your design projects.",
                "keywords_used": ["font", "typography", "design"],
                "optimization_notes": "Basic SEO structure"
            }

        try:
            response = self.openai_client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a Pinterest SEO expert. Create highly optimized Pinterest content in JSON format."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            print(f"OpenAI API error in generate_pinterest_seo: {str(e)}")
            return {
                "pin_titles": [
                    f"Beautiful {font_name} - Perfect Typography",
                    f"Download {font_name} - Stunning Font Design", 
                    f"Creative {font_name} - Typography Collection"
                ],
                "pin_description": f"Discover the amazing {font_name}! Perfect for your design projects.",
                "keywords_used": ["font", "typography", "design"],
                "optimization_notes": "Basic SEO structure"
            }
    
    def generate_pinterest_json_format(self, font_name, description, main_url):
        """Генерация блока 5 в формата JSON для Pinterest"""
        prompt = f"""**PINTEREST JSON FORMAT GENERATOR**

**TASK**: Generate Pinterest pin data in strict JSON format for font typography content

**INPUT**:
- Font Name: {font_name}
- Description: {description[:300]}
- Link: {main_url}

**OUTPUT FORMAT**: Strict JSON with these exact fields in this order:
{{
  "category": "Font category (Script, Sans Serif, Display, etc.)",
  "title": "Engaging title with font name",
  "description": "Compelling description highlighting font features and use cases",
  "alt_text": "Descriptive alt text for accessibility describing the font style and appearance",
  "hashtags": [
    "#fontname",
    "#typography",
    "#design",
    "#fonts",
    "#creativefonts",
    "#relevant_category"
  ],
  "link": "{self.get_affiliate_url(main_url)}"
}}"""

        if not self.openai_client:
            return {
                "category": "Typography",
                "title": f"{font_name} - Beautiful Typography Font",
                "description": f"Discover the amazing {font_name}! Perfect for your design projects.",
                "alt_text": f"{font_name} font preview showing elegant typography design and character set",
                "hashtags": [
                    "#fonts",
                    "#typography", 
                    "#design",
                    "#creativefonts",
                    "#fontdownload",
                    "#designresources"
                ],
                "link": self.get_affiliate_url(main_url)
            }

        try:
            response = self.openai_client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a Pinterest marketing expert. Generate Pinterest pin data in strict JSON format with exact field order including alt_text."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Принудительно устанавливаем правильный порядок полей
            ordered_result = {
                "category": result.get("category", "Typography"),
                "title": result.get("title", f"{font_name} - Beautiful Typography Font"),
                "description": result.get("description", f"Discover the amazing {font_name}! Perfect for your design projects."),
                "alt_text": result.get("alt_text", f"{font_name} font preview showing elegant typography design and character set"),
                "hashtags": result.get("hashtags", [
                    "#fonts",
                    "#typography", 
                    "#design",
                    "#creativefonts",
                    "#fontdownload",
                    "#designresources"
                ]),
                "link": self.get_affiliate_url(main_url)
            }
            
            return ordered_result
            
        except Exception as e:
            print(f"OpenAI API error in generate_pinterest_json_format: {str(e)}")
            return {
                "category": "Typography",
                "title": f"{font_name} - Beautiful Typography Font",
                "description": f"Discover the amazing {font_name}! Perfect for your design projects.",
                "alt_text": f"{font_name} font preview showing elegant typography design and character set",
                "hashtags": [
                    "#fonts",
                    "#typography", 
                    "#design",
                    "#creativefonts",
                    "#fontdownload",
                    "#designresources"
                ],
                "link": self.get_affiliate_url(main_url)
            }
    
    def generate_image_prompt(self, font_name, description, glyph_images):
        """Генерация промпта для создания изображения с учетом стиля шрифта"""
        # Анализируем стиль шрифта
        font_style = self.analyze_font_style(font_name)

        # Подготовим ссылки на первые две картинки для reference
        ref1 = glyph_images[0] if glyph_images else ""
        ref2 = glyph_images[1] if len(glyph_images) > 1 else ""
        ref_preview = glyph_images[2] if len(glyph_images) > 2 else ""

        prompt = f"""#SORA_PROMPT\nGenerate a stunning vertical Pinterest Pin 9:16 that instantly stands out as an advertisement for the \"{font_name}\" font.\n\nReference glyph images: [REF_GLYPH_1]({ref1}) and [REF_GLYPH_2]({ref2}). If needed, use product preview [REF_PREVIEW]({ref_preview}) for overall style guidance. Replicate glyph shapes precisely.\n\nScene: highly polished, {font_style} vibe with luxurious composition. Central focus: the word \"{font_name}\" written in its genuine font style, large and crisp. Add subtle tagline like \"Download the font now!\" beneath. Background should complement the font's mood based on this description: {description[:300]}. Use rich colours, professional lighting, depth of field, elegant props. No watermarks or logos. Output: one breathtaking frame suitable for Pinterest advertising."""

        if not self.openai_client:
            # Fallback: базовый шаблон
            base_prompt = f"Elegant Pinterest pin featuring the word '{font_name}' in its real font style, {font_style} themed, high-end look, professional lighting, aesthetic composition, vertical 9:16, no branding, no watermark."
            return base_prompt

        try:
            response = self.openai_client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You create highly detailed, vivid image generation prompts."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"OpenAI API error in generate_image_prompt: {str(e)}")
            # Fallback: базовый шаблон
            base_prompt = f"Elegant Pinterest pin featuring the word '{font_name}' in its real font style, {font_style} themed, high-end look, professional lighting, aesthetic composition, vertical 9:16, no branding, no watermark."
            return base_prompt
    
    def analyze_font_style(self, font_name):
        """Анализ стиля шрифта по названию"""
        name_lower = font_name.lower()
        
        # Бизнес/корпоративные
        if any(word in name_lower for word in ['business', 'corporate', 'professional', 'office', 'modern', 'clean', 'minimal']):
            return 'business'
        
        # Свадебные/романтические
        elif any(word in name_lower for word in ['wedding', 'romantic', 'love', 'elegant', 'bride', 'marriage']):
            return 'wedding'
        
        # Винтажные/ретро
        elif any(word in name_lower for word in ['vintage', 'retro', 'classic', 'old', 'antique', 'historic']):
            return 'vintage'
        
        # Игривые/детские
        elif any(word in name_lower for word in ['fun', 'playful', 'kid', 'child', 'cartoon', 'comic', 'cute']):
            return 'playful'
        
        # Готические/темные
        elif any(word in name_lower for word in ['gothic', 'dark', 'horror', 'metal', 'rock', 'black']):
            return 'gothic'
        
        # Скриптовые/каллиграфические
        elif any(word in name_lower for word in ['script', 'calligraphy', 'handwritten', 'brush', 'signature']):
            return 'script'
        
        # Декоративные/художественные
        elif any(word in name_lower for word in ['decorative', 'artistic', 'creative', 'design', 'fancy']):
            return 'decorative'
        
        # По умолчанию - современный
        else:
            return 'modern'
    
    def get_style_specific_prompt(self, style):
        """Получение стиль-специфичного промпта"""
        style_prompts = {
            'business': '''Scene: Professional, clean workspace with modern elements like laptop, tablet, business cards, geometric shapes, or architectural lines. Minimal and sophisticated.

Color palette: Professional colors - navy blue, charcoal gray, white, silver accents. Clean and corporate feel.
Lighting: Bright, even lighting with sharp shadows for professionalism.
Elements: Geometric frames, clean lines, minimal decorations, professional tools.''',

            'wedding': '''Scene: Soft and elegant flatlay with romantic elements like flowers (roses, peonies), silk ribbons, lace, pearls, or vintage paper.

Color palette: Gentle, romantic tones - blush pink, cream, ivory, soft gold, lavender.
Lighting: Soft natural lighting with dreamy, warm glow.
Elements: Floral arrangements, delicate ribbons, vintage details, romantic textures.''',

            'vintage': '''Scene: Nostalgic background with vintage elements like old books, antique frames, aged paper, vintage stamps, or retro objects.

Color palette: Warm vintage tones - sepia, burnt orange, deep brown, cream, muted gold.
Lighting: Warm, nostalgic lighting with aged feel and soft vignetting.
Elements: Antique frames, old textures, vintage ornaments, classic decorations.''',

            'playful': '''Scene: Fun, colorful background with playful elements like colorful shapes, toys, bright patterns, or creative materials.

Color palette: Bright, cheerful colors - rainbow tones, vibrant pink, electric blue, sunny yellow, lime green.
Lighting: Bright, energetic lighting with vivid colors and high contrast.
Elements: Colorful shapes, fun patterns, creative tools, playful decorations.''',

            'gothic': '''Scene: Dark, mysterious background with gothic elements like black textures, metallic accents, dark fabrics, or architectural details.

Color palette: Dark, dramatic colors - deep black, dark purple, blood red, silver, charcoal.
Lighting: Dramatic lighting with strong contrasts and mysterious shadows.
Elements: Dark textures, metallic frames, gothic ornaments, dramatic decorations.''',

            'script': '''Scene: Artistic workspace with calligraphy tools like pens, ink, paper, or handwriting elements.

Color palette: Classic calligraphy colors - deep black ink, warm beige paper, gold accents, rich brown.
Lighting: Soft, artistic lighting highlighting the craftsmanship.
Elements: Calligraphy tools, ink bottles, elegant paper, artistic frames.''',

            'decorative': '''Scene: Creative, artistic background with decorative elements like patterns, textures, artistic tools, or design materials.

Color palette: Rich, artistic colors - jewel tones, deep purple, emerald green, gold, artistic accents.
Lighting: Creative lighting that highlights artistic details and textures.
Elements: Artistic patterns, decorative frames, creative textures, design elements.''',

            'modern': '''Scene: Contemporary, clean background with modern elements like sleek surfaces, minimal decorations, or tech-inspired details.

Color palette: Modern colors - clean white, soft gray, accent colors (blue, green, or orange).
Lighting: Clean, contemporary lighting with subtle shadows.
Elements: Modern geometric shapes, clean lines, minimal decorative elements.'''
        }
        
        return style_prompts.get(style, style_prompts['modern'])

    def extract_main_preview_image(self, main_data):
        """Пытаемся достать главное превью-шапку шрифта (hero image)"""
        html = main_data.get('html', '') or ''
        # 1) meta og:image
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
        if m:
            return m.group(1)

        # 2) twitter:image
        m = re.search(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
        if m:
            return m.group(1)

        # 3) первый img с классом product-image / attachment-* in HTML
        m = re.search(r'<img[^>]+src=["\']([^"\']+\.(?:jpg|png|webp))["\'][^>]*(?:class=["\'][^"\']*(?:product|attachment)[^"\']*["\'])', html, flags=re.IGNORECASE)
        if m:
            return m.group(1)

        # 4) Firecrawl images list – берём первую картинку с ключевыми словами preview / product
        images_list = main_data.get('images', [])
        for url in images_list:
            if any(k in url.lower() for k in ['preview', 'product', 'hero', 'cover']):
                return url
        if images_list:
            return images_list[0]
        return None

# Создаем экземпляр парсера
parser = FontWebParser()
# Экземпляр парсера Fiverr - полностью отключаем для тестирования
# fiverr_parser_instance = FiverrParser()
fiverr_parser_instance = None
print("FiverrParser completely disabled for testing")
print("All OpenAI clients disabled to prevent initialization errors")

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/parse', methods=['POST'])
def parse_font():
    """API для парсинга шрифта"""
    data = request.get_json()
    font_url = data.get('font_url', '').strip()
    
    if not font_url:
        return jsonify({"error": "Введите ссылку на шрифт"})
    
    result = parser.parse_font_from_url(font_url)
    return jsonify(result)

# Новый эндпоинт для парсинга Fiverr Gig
@app.route('/parse_fiverr', methods=['POST'])
def parse_fiverr():
    """API для парсинга Fiverr Gig"""
    data = request.get_json()
    gig_url = data.get('gig_url', '').strip()

    if not gig_url:
        return jsonify({"error": "Введите ссылку на Fiverr gig"})

    if fiverr_parser_instance is None:
        return jsonify({"error": "Fiverr parser temporarily disabled for testing"})

    result = fiverr_parser_instance.parse(gig_url)
    return jsonify(result)

if __name__ == '__main__':
    # Получаем порт из переменной окружения или используем 5000 по умолчанию
    port = int(os.environ.get("PORT", 5000))
    # Запуск без режима debug и без авто-перезапуска, чтобы устранить бесконечный watchdog-reload
    app.run(debug=False, host='0.0.0.0', port=port, use_reloader=False) 