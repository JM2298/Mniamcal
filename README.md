# Mniamcal

# INSTRUKCJA PIERWSZE URUCHOMIENIE 

make up-build
make makemigrations
make migrate
make superuser
make import-sql
## i powinno dzialac

## Natepnie jesli chceemy uruchomic projekt starczy tylko to (Uruchamianie wszystkiego w okreslonym profilu)

make up - uruchamia backend + webapp2 w tle
make run - buduje i uruchamia backend + webapp2 w tle
make up-backend - uruchamia tylko backend
make run-stronka - uruchamia wszystko + stronka
make run-frontend - uruchamia wszystko + webapp2 w trybie podgladu logow

# WAŻNE ADRESY

http://localhost:8000/admin/ - backend panel admina
http://localhost:8000/docs/redoc/ - opisane api
http://localhost:3000 - frontend webpapp2
http://localhost:5001 - frontend mniamCal




