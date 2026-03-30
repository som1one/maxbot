#!/bin/bash

# Скрипт для сборки и загрузки образа в Docker Hub

# Настройки
DOCKER_USERNAME="greenteeea"  # Замените на ваш Docker Hub username
IMAGE_NAME="kvt-bot"
TAG="latest"

echo "🔨 Сборка Docker образа..."
docker build -t $DOCKER_USERNAME/$IMAGE_NAME:$TAG .

if [ $? -eq 0 ]; then
    echo "✅ Образ успешно собран!"
    
    echo "📤 Загрузка образа в Docker Hub..."
    docker push $DOCKER_USERNAME/$IMAGE_NAME:$TAG
    
    if [ $? -eq 0 ]; then
        echo "✅ Образ успешно загружен в Docker Hub!"
        echo "🐳 Для запуска на сервере используйте:"
        echo "   docker-compose -f docker-compose.prod.yml up -d"
    else
        echo "❌ Ошибка при загрузке образа в Docker Hub"
        exit 1
    fi
else
    echo "❌ Ошибка при сборке образа"
    exit 1
fi
