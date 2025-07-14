# Fiverr Gig Parser 🟣

Мини-проект, повторяющий логику *Font Parser*, но для услуг (gigs) на Fiverr.com.

## Возможности
1. Принимает URL gig-а Fiverr (например `https://www.fiverr.com/username/awesome-logo-design`).
2. Через Firecrawl загружает HTML страницы.
3. Извлекает:
   * Заголовок Gig-а
   * Описание
   * Категорию / подкатегорию
   * Никнейм продавца, рейтинг, число отзывов
   * Пакеты и цены (Basic / Standard / Premium)
   * Главные изображения / видео превью
4. Вызывает OpenAI для генерации:
   * SEO-описания пина Pinterest (если нужно)
   * Sora-ready prompt для рекламного видео/баннера Gig-а
5. Возвращает JSON с полной структурой.

## Быстрый старт (локально)
```bash
cd fiverr_parser
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python fiverr_parser.py "https://www.fiverr.com/username/awesome-logo-design"
```

### Пример вывода
```json
{
  "gig_title": "I will design an awesome unique logo",
  "description": "Looking for a standout logo …",
  "seller": {
    "username": "design_guru",
    "rating": 4.9,
    "reviews": 812
  },
  "packages": [
    { "name": "Basic", "price": "$10", "delivery": "2 days" },
    …
  ],
  "images": [ "https://fiverr-res.cloudinary.com/…/main.jpg", …],
  "pinterest_seo": { … },
  "sora_prompt": "#SORA_PROMPT …"
}
```

## Интеграция с n8n
* Аналогично предыдущему проекту: Cron → HTTP Request (Firecrawl Search по Fiverr категории) → Function pick → локальный `/fiverr_parse` → Google Sheets.

## TODO
- [ ] Добавить Flask-эндпоинт (если нужен).
- [ ] Расширить парсинг FAQ и галереи. 