# Wymagania niefunkcjonalne - Dieta Studencka

## 1. Cel dokumentu
Dokument definiuje mierzalne wymagania niefunkcjonalne (NFR) dla aktualnej wersji systemu Dieta Studencka.
Zakres obejmuje backend Django/DRF/Channels oraz srodowisko uruchomieniowe Docker Compose (PostgreSQL, Redis, Celery, Nginx).

## 2. Kontekst i zalozenia
- Wymagania dotyczace obecnego etapu projektu (bez pelnego stacku observability typu Prometheus/Grafana).
- KPI maja charakter bazowy (baseline) i moga byc zaostrzane po zebraniu pomiarow.
- Wymagania musza byc weryfikowalne przez testy, logi, healthchecki i procedury operacyjne.

## 3. Dostepnosc i niezawodnosc

### NFR-001
- Opis: API backendu musi byc dostepne stabilnie dla klientow web/mobile.
- Metryka: miesieczny uptime endpointu zdrowia API.
- Prog akceptacji: >= 99.5% w skali miesiaca.
- Sposob weryfikacji: cykliczny probe HTTP (np. co 60 s) na endpoint zdrowia, raport miesieczny.

### NFR-002
- Opis: Serwisy kontenerowe musza automatycznie wracac po awarii procesu.
- Metryka: procent serwisow krytycznych z polityka auto-restart.
- Prog akceptacji: 100% serwisow krytycznych (`web`, `db`, `redis`, `celery_worker`, `celery_beat`, `nginx`) ma `restart: unless-stopped`.
- Sposob weryfikacji: przeglad `docker-compose.yml` + test restartu procesu w kontenerze.

### NFR-003
- Opis: Aplikacja web nie moze startowac przed gotowoscia bazy danych.
- Metryka: procent uruchomien, w ktorych `web` startuje po statusie healthy `db`.
- Prog akceptacji: 100%.
- Sposob weryfikacji: inspekcja `depends_on.condition: service_healthy` + testy wielokrotnego `docker compose up`.

### NFR-004
- Opis: System musi byc odporny na chwilowa niedostepnosc DB podczas startu.
- Metryka: maksymalny czas oczekiwania aplikacji na DB.
- Prog akceptacji: do 10 minut (`DB_WAIT_MAX_ATTEMPTS=300`, interval 2 s).
- Sposob weryfikacji: test startu przy opoznionym podniesieniu DB, analiza logow `entrypoint`.

## 4. Wydajnosc i skalowalnosc

### NFR-005
- Opis: Odpowiedz API dla endpointow listujacych musi byc szybka przy typowym obciazeniu.
- Metryka: latency p95 dla zapytan GET list (diety, posilki, produkty uproszczone).
- Prog akceptacji: p95 <= 600 ms dla 20 RPS (lokalne/stage, bez cold startu).
- Sposob weryfikacji: test obciazeniowy (np. k6/Locust), raport p50/p95/p99.

### NFR-006
- Opis: Operacje mutujace dane rodziny i list zakupow musza odpowiadac przewidywalnie.
- Metryka: latency p95 dla kluczowych POST/PATCH.
- Prog akceptacji: p95 <= 900 ms dla 10 RPS.
- Sposob weryfikacji: scenariusz testu obciazeniowego na endpointach mutujacych.

### NFR-007
- Opis: Realtime dla listy zakupow musi dostarczac aktualizacje bez istotnego opoznienia.
- Metryka: czas od zapisu zmiany do odbioru eventu websocket.
- Prog akceptacji: p95 <= 1.5 s.
- Sposob weryfikacji: test integracyjny klient websocket + znacznik czasu serwer/klient.

### NFR-008
- Opis: Odczyty listowe API musza byc stronicowane.
- Metryka: procent endpointow listowych z aktywna paginacja.
- Prog akceptacji: 100% endpointow listowych zwraca wyniki stronicowane.
- Sposob weryfikacji: przeglad konfiguracji DRF + testy integracyjne odpowiedzi listowych.

## 5. Bezpieczenstwo

### NFR-009
- Opis: Endpointy prywatne musza wymagac uwierzytelnienia JWT.
- Metryka: procent endpointow prywatnych odrzucajacych brak/niepoprawny token.
- Prog akceptacji: 100%.
- Sposob weryfikacji: testy automatyczne 401/403 dla endpointow prywatnych.

### NFR-010
- Opis: Dostep miedzydomenowy musi byc ograniczony do zaufanych originow.
- Metryka: zgodnosc konfiguracji CORS z lista dozwolonych originow.
- Prog akceptacji: 100% originow spoza whitelisty odrzucane.
- Sposob weryfikacji: testy preflight/Origin + przeglad `CORS_ALLOWED_ORIGINS`.

### NFR-011
- Opis: Ochrona CSRF musi byc poprawnie skonfigurowana dla zaufanych domen.
- Metryka: zgodnosc `CSRF_TRUSTED_ORIGINS` z domenami wdrozeniowymi.
- Prog akceptacji: 100% domen produkcyjnych i stagingowych zdefiniowane jawnie.
- Sposob weryfikacji: przeglad ustawien + testy formularzy/operacji wymagajacych CSRF.

### NFR-012
- Opis: Sekrety aplikacji nie moga byc hardkodowane dla produkcji.
- Metryka: procent sekretow krytycznych pobieranych z env.
- Prog akceptacji: 100% (`SECRET_KEY`, `JWT_SIGNING_KEY`, hasla DB, hasla SMTP) z env na prod.
- Sposob weryfikacji: przeglad konfiguracji i pipeline deploymentu.

### NFR-013
- Opis: System musi wymuszac podstawowa polityke jakosci hasel.
- Metryka: aktywnosc walidatorow hasel Django.
- Prog akceptacji: 4/4 domyslnych walidatorow aktywne.
- Sposob weryfikacji: przeglad `AUTH_PASSWORD_VALIDATORS` + testy negatywne rejestracji.

## 6. Integralnosc i trwalosc danych

### NFR-014
- Opis: Dane PostgreSQL musza przetrwac restart kontenerow.
- Metryka: utrata danych po `docker compose down` bez `-v`.
- Prog akceptacji: 0 utraconych rekordow.
- Sposob weryfikacji: test zapisu danych, restart stacku, ponowna weryfikacja rekordow.

### NFR-015
- Opis: Odtworzenie bazy z backupu musi byc wykonalne operacyjnie.
- Metryka: czas odtworzenia backupu (RTO).
- Prog akceptacji: RTO <= 60 min dla backupu do 5 GB.
- Sposob weryfikacji: cwiczenie DR raz na kwartal wedlug procedury restore.

### NFR-016
- Opis: Maksymalna akceptowalna utrata danych po awarii musi byc ograniczona.
- Metryka: RPO dla danych aplikacyjnych.
- Prog akceptacji: RPO <= 24 h.
- Sposob weryfikacji: harmonogram backupow + okresowe testy restore punktu w czasie.

### NFR-017
- Opis: Import `backup.sql` przy pustej bazie musi byc deterministyczny i jednokrotny.
- Metryka: liczba automatycznych importow przy pierwszej inicjalizacji wolumenu.
- Prog akceptacji: dokladnie 1 import na nowy wolumen DB.
- Sposob weryfikacji: test inicjalizacji nowego wolumenu + analiza logow Postgres.

## 7. Operacyjnosc i utrzymywalnosc

### NFR-018
- Opis: Krytyczne serwisy musza publikowac logi operacyjne do diagnostyki.
- Metryka: dostepnosc logow runtime dla `web`, `db`, `celery_worker`, `celery_beat`, `nginx`.
- Prog akceptacji: 100% krytycznych serwisow ma logi dostepne przez `docker compose logs`.
- Sposob weryfikacji: kontrola operacyjna po starcie i podczas scenariuszy bledow.

### NFR-019
- Opis: API musi posiadac aktualna dokumentacje kontraktu.
- Metryka: dostepnosc i zgodnosc schematu OpenAPI z endpointami.
- Prog akceptacji: 100% endpointow DRF objetych schematem `drf_spectacular`.
- Sposob weryfikacji: test generacji schematu i kontrola wybranych endpointow.

### NFR-020
- Opis: Zadania asynchroniczne musza byc wykonywane stabilnie.
- Metryka: status workerow Celery i heartbeat harmonogramu.
- Prog akceptacji: brak przerw pracy worker/beat > 5 min w czasie okna obserwacji 24 h.
- Sposob weryfikacji: logi Celery + kontrola zadania heartbeat.

## 8. Lokalizacja i czas

### NFR-021
- Opis: System musi zachowywac spojnosc czasowa i lokalizacyjna dla rynku PL.
- Metryka: zgodnosc ustawien i serializacji dat/czasu.
- Prog akceptacji: `LANGUAGE_CODE=pl-pl`, `TIME_ZONE=Europe/Warsaw`, `USE_TZ=True` aktywne w runtime.
- Sposob weryfikacji: testy konfiguracji i testy integracyjne endpointow zwracajacych daty.

## 9. Kryteria akceptacji dokumentu NFR
- Kazdy obszar krytyczny (security, availability, performance, backup/restore, operacyjnosc) ma co najmniej 1 mierzalny NFR.
- Kazdy NFR ma: identyfikator, opis, metryke, prog i sposob weryfikacji.
- NFR sa zgodne z aktualna architektura i konfiguracja repozytorium.
