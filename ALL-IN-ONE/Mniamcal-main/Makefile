.DEFAULT_GOAL := help

COMPOSE := docker compose

MANAGE=$(COMPOSE) run --rm web python manage.py
WEB := web
DB := db
NGINX := nginx
NODE := node
CELERY_WORKER := celery_worker
CELERY_BEAT := celery_beat
REDIS := redis
BACKUP_DIR := backups
BACKUP_TS := $(shell powershell -NoProfile -Command "(Get-Date).ToString('yyyyMMdd_HHmmss')")
GRAPH_APP ?=
GRAPH_MODEL ?=
GRAPH_OUT ?= project_models.svg



.PHONY: help up up-full up-build down stop restart build ps logs logs-web logs-db \
	logs-nginx logs-celery logs-beat logs-redis shell-node shell-celery shell-web \
	shell-db migrate makemigrations check superuser inspectdb import-sql backup-db \
	reset-db collectstatic convert-images graphmodels test runserver run-frontend \
	fix-firebase start-all

help: ## Show available commands
	@echo "Available targets:"
	@echo "  make up             - Start containers in background"
	@echo "  make up-full        - Start containers with frontend profile (includes node)"
	@echo "  make up-build       - Build and start containers"
	@echo "  make down           - Stop and remove containers (keep volume)"
	@echo "  make stop           - Stop running containers"
	@echo "  make restart        - Restart running containers"
	@echo "  make build          - Build containers"
	@echo "  make ps             - Show container status"
	@echo "  make logs           - Show logs for all services"
	@echo "  make logs-web       - Show web logs"
	@echo "  make logs-db        - Show db logs"
	@echo "  make logs-nginx     - Show nginx logs"
	@echo "  make logs-celery    - Show celery worker logs"
	@echo "  make logs-beat      - Show celery beat logs"
	@echo "  make logs-redis     - Show redis logs"
	@echo "  make shell-node     - Open shell in node container"
	@echo "  make shell-celery   - Open shell in celery worker container"
	@echo "  make shell-web      - Open shell in web container"
	@echo "  make shell-db       - Open shell in db container"
	@echo "  make migrate        - Run Django migrations"
	@echo "  make makemigrations - Create Django migrations"
	@echo "  make check          - Run Django system check"
	@echo "  make superuser      - Create Django superuser"
	@echo "  make inspectdb      - Generate models to meals/models.py"
	@echo "  make convert-images - Convert base64 obraz_bitowy to media files"
	@echo "  make import-sql     - Import backup.sql into Postgres"
	@echo "  make backup-db      - Create SQL backup from Postgres to backups/"
	@echo "  make reset-db       - Recreate stack with fresh DB volume"
	@echo "  make graphmodels    - Generate models diagram (all apps / app / model)"
	@echo "    examples: make graphmodels"
	@echo "              make graphmodels GRAPH_APP=meals"
	@echo "              make graphmodels GRAPH_MODEL=meals.ProjektInflacjaMobilePosilkiwdiecie"

up: ## Start containers in background
	$(COMPOSE) up -d

up-full: ## Start containers with frontend profile (includes node)
	$(COMPOSE) --profile frontend up -d --remove-orphans --force-recreate

up-build: ## Build and start containers in background
	$(COMPOSE) up -d --build

down: ## Stop and remove containers
	$(COMPOSE) down

stop: ## Stop running containers
	$(COMPOSE) stop

restart: ## Restart running containers
	$(COMPOSE) restart

build: ## Build containers
	$(COMPOSE) build

ps: ## Show container status
	$(COMPOSE) ps

logs: ## Show logs for all services
	$(COMPOSE) logs -f

logs-web: ## Show web logs
	$(COMPOSE) logs -f $(WEB)

logs-db: ## Show db logs
	$(COMPOSE) logs -f $(DB)

logs-nginx: ## Show nginx logs
	$(COMPOSE) logs -f $(NGINX)

logs-celery: ## Show celery worker logs
	$(COMPOSE) logs -f $(CELERY_WORKER)

logs-beat: ## Show celery beat logs
	$(COMPOSE) logs -f $(CELERY_BEAT)

logs-redis: ## Show redis logs
	$(COMPOSE) logs -f $(REDIS)

shell-node: ## Open shell in node container
	$(COMPOSE) exec $(NODE) sh

shell-celery: ## Open shell in celery worker container
	$(COMPOSE) exec $(CELERY_WORKER) sh

shell-web: ## Open shell in web container
	$(COMPOSE) exec $(WEB) sh

shell-db: ## Open psql shell in db container
	$(COMPOSE) exec $(DB) psql -U myuser -d mydb

migrate: ## Run Django migrations
	$(COMPOSE) exec $(WEB) python manage.py migrate

makemigrations: ## Create Django migrations
	$(COMPOSE) exec $(WEB) python manage.py makemigrations

check: ## Run Django system check
	$(COMPOSE) exec $(WEB) python manage.py check

superuser: ## Create Django superuser
	$(COMPOSE) exec $(WEB) python manage.py createsuperuser

inspectdb: ## Generate models from DB schema into meals/models.py
	$(COMPOSE) exec $(WEB) sh -c "python manage.py inspectdb > meals/models.py"

import-sql: ## Import backup.sql into existing database
	$(COMPOSE) exec -T $(DB) psql -U myuser -d mydb < backup.sql

backup-db: ## Create SQL backup from Postgres into backups/backup_YYYYMMDD_HHMMSS.sql
	@powershell -NoProfile -Command "New-Item -ItemType Directory -Path '$(BACKUP_DIR)' -Force | Out-Null"
	$(COMPOSE) exec -T $(DB) sh -c "PGPASSWORD=$$POSTGRES_PASSWORD pg_dump -U $$POSTGRES_USER -d $$POSTGRES_DB" > $(BACKUP_DIR)/backup_$(BACKUP_TS).sql
	@echo "Backup saved: $(BACKUP_DIR)/backup_$(BACKUP_TS).sql"

reset-db: ## Recreate stack and force SQL import (removes DB volume)
	$(COMPOSE) down -v
	$(COMPOSE) up -d --build

collectstatic: ## Collect static files (if needed)
	$(COMPOSE) exec $(WEB) python manage.py collectstatic --noinput

convert-images: ## Convert base64 obraz_bitowy to files under media/posilki
	$(COMPOSE) exec $(WEB) python manage.py convert_obraz_bitowy_to_files


graphmodels:
	$(MANAGE) graph_models $(if $(GRAPH_MODEL),-a -I $(GRAPH_MODEL),$(if $(GRAPH_APP),$(GRAPH_APP),-a)) -o $(GRAPH_OUT)


test: ## Run tests
	$(COMPOSE) exec $(WEB) python manage.py test meals.tests --pattern="*.py"



runserver: ## Run Django development server
	$(COMPOSE) exec $(WEB) python manage.py runserver 0.0.0.0:8000



run-webapp2: ## Run only node container
	$(COMPOSE) --profile frontend up

run-stronka: ## Run only node container
	$(COMPOSE) --profile stronka up

	
