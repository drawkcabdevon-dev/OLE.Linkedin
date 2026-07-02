.PHONY: build up down logs shell docker-build docker-up docker-down

# Local development
install:
	pip install -r requirements.txt

bot:
	python telegram_bot.py

# Docker
build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

shell:
	docker compose exec agent /bin/bash

# Deployment
docker-build:
	docker build -t ole-linkedin-agent .

docker-run:
	docker run -d \
		--name ole-linkedin-agent \
		--restart unless-stopped \
		--env-file .env \
		-v $(PWD)/data:/app/data \
		-v $(PWD)/assets:/app/assets \
		ole-linkedin-agent

docker-stop:
	docker stop ole-linkedin-agent && docker rm ole-linkedin-agent
