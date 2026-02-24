.PHONY: up down logs migrate collectstatic rebuild

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

migrate:
	docker compose exec web python manage.py migrate

collectstatic:
	docker compose exec web python manage.py collectstatic --noinput

rebuild:
	docker compose up -d --build
