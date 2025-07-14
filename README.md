# Font & Fiverr Parser

Веб-приложение для парсинга шрифтов с Creative Fabrica и Fiverr гигов с генерацией SEO-контента для Pinterest.

## Возможности

- 🔍 Парсинг шрифтов с Creative Fabrica
- 🎨 Извлечение изображений глифов и описаний
- 📌 Генерация SEO-контента для Pinterest
- 🎯 Парсинг Fiverr гигов
- 🤖 Интеграция с OpenAI для анализа контента

## Технологии

- **Backend**: Flask, Python 3.11
- **API**: Firecrawl, OpenAI
- **Frontend**: HTML, CSS, JavaScript
- **Deployment**: Heroku/Railway/Render

## Локальная установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/your-username/font-fiverr-parser.git
cd font-fiverr-parser
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Настройте переменные окружения (создайте файл `.env`):
```env
FIRECRAWL_API_KEY=your_firecrawl_api_key
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://hubai.loe.gg/v1
OPENAI_MODEL=gpt-4o-mini
```

4. Запустите приложение:
```bash
python app.py
```

5. Откройте браузер: http://localhost:5000

## Деплой на Heroku

1. Создайте аккаунт на [Heroku](https://heroku.com)

2. Установите Heroku CLI:
```bash
# Windows
winget install --id=Heroku.HerokuCLI
```

3. Войдите в Heroku:
```bash
heroku login
```

4. Создайте приложение:
```bash
heroku create your-app-name
```

5. Настройте переменные окружения:
```bash
heroku config:set FIRECRAWL_API_KEY=your_firecrawl_api_key
heroku config:set OPENAI_API_KEY=your_openai_api_key
heroku config:set OPENAI_BASE_URL=https://hubai.loe.gg/v1
heroku config:set OPENAI_MODEL=gpt-4o-mini
```

6. Деплойте приложение:
```bash
git add .
git commit -m "Initial commit"
git push heroku main
```

7. Откройте приложение:
```bash
heroku open
```

## Деплой на Railway

1. Создайте аккаунт на [Railway](https://railway.app)

2. Подключите GitHub репозиторий

3. Настройте переменные окружения в Railway Dashboard:
   - `FIRECRAWL_API_KEY`
   - `OPENAI_API_KEY`
   - `OPENAI_BASE_URL`
   - `OPENAI_MODEL`

4. Railway автоматически деплоит приложение

## Деплой на Render

1. Создайте аккаунт на [Render](https://render.com)

2. Создайте новый Web Service

3. Подключите GitHub репозиторий

4. Настройте:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`

5. Добавьте переменные окружения в Environment Variables

## API Endpoints

### Парсинг шрифта
```
POST /parse
Content-Type: application/json

{
  "font_url": "https://www.creativefabrica.com/product/font-name/"
}
```

### Парсинг Fiverr гига
```
POST /parse_fiverr
Content-Type: application/json

{
  "gig_url": "https://www.fiverr.com/username/service"
}
```

## Структура проекта

```
├── app.py                 # Основное Flask приложение
├── requirements.txt       # Зависимости Python
├── Procfile             # Конфигурация для Heroku
├── runtime.txt          # Версия Python
├── .gitignore          # Исключения Git
├── README.md           # Документация
├── templates/          # HTML шаблоны
├── static/            # CSS, JS, изображения
├── fiverr_parser/     # Парсер Fiverr
└── results/           # Результаты парсинга
```

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `FIRECRAWL_API_KEY` | API ключ Firecrawl | - |
| `OPENAI_API_KEY` | API ключ OpenAI | - |
| `OPENAI_BASE_URL` | Базовый URL OpenAI | https://hubai.loe.gg/v1 |
| `OPENAI_MODEL` | Модель OpenAI | gpt-4o-mini |
| `PORT` | Порт приложения | 5000 |

## Лицензия

MIT License

## Поддержка

Если у вас есть вопросы или проблемы, создайте Issue в репозитории. 