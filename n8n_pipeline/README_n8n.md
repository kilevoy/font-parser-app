# n8n Pipeline — автоматический парсер Creative Fabrica → Google Sheets

Этот workflow выполняет те же шаги, что и локальный *Font Parser*, но полностью автоматически внутри n8n.

## Что делает
1. **Cron Trigger** – раз в день (настройка) стартует процесс.
2. **HTTP Request → Firecrawl Search** – делает запрос к Firecrawl API и получает список актуальных ссылок на шрифты Creative Fabrica.
3. **Function "Pick URL"** – выбирает случайную ссылку или первую в списке.
4. **HTTP Request → Local Parser** – обращается к вашему локальному Flask-серверу `http://127.0.0.1:5000/parse` с полем `font_url`.
5. **Google Sheets** – добавляет новую строку в таблицу со всеми полями (название, описание, ссылки, glyph images, Sora-prompt, Pinterest JSON и т.д.).

## Как использовать
1. **Откройте UI n8n** (`http://SERVER:5678/`)
2. В левом меню нажмите *Import* и загрузите файл `font_parser_workflow.json` из этой папки.
3. Перейдите во вкладку *Credentials*:
   * Создайте **HTTP Basic Auth** credential → назовите `firecrawl`. Введите API-ключ в поле *Username*, оставьте *Password* пустым.
   * Создайте **Google Sheets OAuth2** credential (следуйте OAuth-мастеру).
4. В узле **HTTP Request (Firecrawl Search)** выберите credential `firecrawl`.
5. В узле **Google Sheets** укажите credential, Spreadsheet ID и название листа.
6. Активируйте workflow (тумблер *Active*).

## Параметры Cron
* *Mode*: Every Day
* *Hour*: 08:00 (можно изменить)

## Дополнительно
* Если хотите запускать workflow по веб-хуку, замените Cron на **Webhook Trigger** и вызывайте `POST /webhook/font` → `{ "url": "https://.../product/..." }`.
* При желании можно отправлять результат в Telegram, Discord или Slack — просто добавьте соответствующий узел после Google Sheets. 