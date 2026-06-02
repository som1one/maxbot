# MaxBot

Сервис для обработки заявок из Max-мессенджера с FastAPI backend и PostgreSQL.

## Что внутри

- `bot`: Max-бот на `aiomax`
- `app`: FastAPI API для healthcheck и админских endpoint'ов
- `db`: PostgreSQL для заявок и настроек

## Быстрый старт локально

```bash
cp .env.example .env
docker compose --profile dev up -d --build
```

После запуска:

- API: `http://localhost:8000/health`
- MailHog: `http://localhost:8025`

## Основные переменные

- `BOT_TOKEN`: токен Max-бота
- `ADMIN_MAX_CHAT_ID`: чат для служебных уведомлений
- `DEFAULT_NOTIFICATION_EMAIL`: email для новых заявок
- `POSTGRES_*` или `DATABASE_URL`: подключение к PostgreSQL
- `SMTP_*`: SMTP-конфиг для отправки писем
- `EMAIL_ENABLED`: включает email-уведомления

## Запуск без Docker

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py backend
python main.py bot
```

Рекомендуемая версия Python для локального запуска: `3.12`.

## Полезные команды

```bash
docker compose ps
docker compose logs -f bot
docker compose logs -f backend
docker compose exec db psql -U "$POSTGRES_USER" "$POSTGRES_DB"
```

## Важно

- Не храните секреты в git. Используйте только локальный `.env`.
- Для production используйте [DEPLOYMENT.md](/Users/cultim/Documents/maxbot/DEPLOYMENT.md).
