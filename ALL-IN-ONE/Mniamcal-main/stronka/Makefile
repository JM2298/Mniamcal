.PHONY: start stop logs

start:
	docker-compose up -d --build --force-recreate --renew-anon-volumes

stop:
	docker-compose down

logs:
	docker-compose logs -f