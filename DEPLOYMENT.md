# Deployment Guide

## 1. Подготовка сервера

Подойдёт Ubuntu 22.04+ или Debian 12+.

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin git
sudo systemctl enable --now docker
```

Проверьте:

```bash
docker --version
docker compose version
```

## 2. Клонирование проекта

```bash
git clone <your-repo-url> maxbot
cd maxbot
```

## 3. Создание production-конфига

```bash
cp .env.example .env
```

Заполните минимум:

```env
ENV=production
TZ=Europe/Minsk

BOT_TOKEN=replace-with-real-token
ADMIN_MAX_CHAT_ID=replace-with-admin-chat-id

ADMIN_USERNAME=admin
ADMIN_PASSWORD=strong-random-password

POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=kvtservice
POSTGRES_USER=kvt
POSTGRES_PASSWORD=strong-random-db-password

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-smtp-login@example.com
SMTP_PASSWORD=your-smtp-password
SMTP_FROM=your-smtp-login@example.com
DEFAULT_NOTIFICATION_EMAIL=ops@example.com
EMAIL_ENABLED=true
STARTUP_EMAIL_TEST=false
```

## 4. Запуск

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## 5. Проверка

```bash
docker compose ps
docker compose logs -f bot
docker compose logs -f backend
curl http://127.0.0.1:8000/health
```

Ожидаемо:

- `db` в статусе `healthy`
- `backend` отвечает `{"status":"ok",...}`
- `bot` не падает и уходит в polling

## 6. Обновление

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## 7. Резервная копия БД

```bash
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup.sql
```

Восстановление:

```bash
docker compose exec -T db psql -U "$POSTGRES_USER" "$POSTGRES_DB" < backup.sql
```

## 8. Что проверить перед боем

- В git нет `.env`
- `BOT_TOKEN` и SMTP-пароли не старые, а перевыпущенные
- Запущен ровно один инстанс `bot`
- Новая заявка доходит и в Max/админ-чат, и на email
