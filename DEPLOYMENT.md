# Развертывание KVT Bot

## Подготовка к развертыванию

### 1. Настройка Docker Hub

1. Зарегистрируйтесь на [Docker Hub](https://hub.docker.com/)
2. Создайте репозиторий `kvt-bot`
3. В файле `deploy.sh` замените `your-dockerhub-username` на ваш username

### 2. Сборка и загрузка образа

```bash
# Сделайте скрипт исполняемым
chmod +x deploy.sh

# Запустите сборку и загрузку
./deploy.sh
```

### 3. Настройка переменных окружения

Создайте файл `.env` на сервере:

```env
# Telegram Bot
BOT_TOKEN=your_bot_token_here
ADMIN_CHAT_ID=your_admin_chat_id_here

# Email (уже настроены)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=sbcargobot@gmail.com
SMTP_PASSWORD=1Qqazxsw55
DEFAULT_NOTIFICATION_EMAIL=sb@sbcargo.ru
```

## Развертывание на сервере

### 1. Установка Docker и Docker Compose

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install docker.io docker-compose-plugin

# CentOS/RHEL
sudo yum install docker docker-compose-plugin
```

### 2. Запуск приложения

```bash
# Клонируйте репозиторий (или скопируйте файлы)
git clone <your-repo-url>
cd PythonProject

# Запустите приложение
docker-compose -f docker-compose.prod.yml up -d
```

### 3. Проверка работы

```bash
# Проверьте статус контейнеров
docker-compose -f docker-compose.prod.yml ps

# Посмотрите логи бота
docker-compose -f docker-compose.prod.yml logs -f bot
```

## Обновление

```bash
# Остановите приложение
docker-compose -f docker-compose.prod.yml down

# Обновите образ
docker-compose -f docker-compose.prod.yml pull

# Запустите заново
docker-compose -f docker-compose.prod.yml up -d
```

## Мониторинг

```bash
# Логи бота
docker-compose -f docker-compose.prod.yml logs -f bot

# Логи базы данных
docker-compose -f docker-compose.prod.yml logs -f postgres

# Статистика ресурсов
docker stats
```

## Резервное копирование

```bash
# Создание бэкапа базы данных
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U kvt kvtservice > backup.sql

# Восстановление из бэкапа
docker-compose -f docker-compose.prod.yml exec -T postgres psql -U kvt kvtservice < backup.sql
```
