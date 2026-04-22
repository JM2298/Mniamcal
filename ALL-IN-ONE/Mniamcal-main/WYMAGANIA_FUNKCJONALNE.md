# Wymagania funkcjonalne - Dieta Studencka

## 1. Cel dokumentu
Dokument definiuje wymagania funkcjonalne systemu Dieta Studencka.
Wymagania opisane nizej odpowiadaja aktualnemu zakresowi backendu (Django/DRF/Channels) oraz aplikacji klienckich (web i mobile).

## 2. Zakres systemu
System obejmuje:
- uwierzytelnianie i konto uzytkownika,
- zarzadzanie rodzina i zaproszeniami,
- przeglad diet i posilkow,
- kalendarz posilkow rodziny,
- generowanie i obsluge list zakupow,
- magazyn (lodowke) rodziny,
- powiadomienia push i realtime websocket,
- ustawienia konta zwiazane z obsluga listy zakupow.

## 3. Role
- Gosc: przeglada publiczne zasoby diet/posilkow i moze sie zalogowac.
- Uzytkownik zalogowany: korzysta z funkcji konta, rodziny, kalendarza, list zakupow i magazynu.
- Zalozyciel rodziny: tworzy rodzine i zaprasza czlonkow.
- Czlonek rodziny: korzysta z funkcji rodziny i moze opuscic rodzine.

## 4. Wymagania funkcjonalne

### 4.1 Konto, logowanie i tokeny
- FR-001: System musi umozliwiac rejestracje konta przez username, first_name, opcjonalny email i haslo.
- FR-002: System musi odrzucac rejestracje, jezeli username juz istnieje.
- FR-003: System musi umozliwiac logowanie username + haslo.
- FR-004: System musi zwracac access i refresh token po poprawnym logowaniu.
- FR-005: System musi zwracac blad logowania dla niepoprawnych danych.
- FR-006: System musi obslugiwac logowanie przez Firebase ID token (Google/Firebase).
- FR-007: System musi tworzyc lokalne konto przy pierwszym poprawnym logowaniu OAuth, jezeli uzytkownik nie istnieje.
- FR-008: System musi umozliwiac odswiezenie tokenu access na podstawie refresh tokenu.
- FR-009: System musi udostepniac endpoint auth/me z profilem uzytkownika i kontekstem rodziny/diety.
- FR-010: System musi wymagac autoryzacji JWT dla endpointow prywatnych.

### 4.2 Ustawienia konta
- FR-011: System musi umozliwiac zapis i odczyt zgody na powiadomienia push.
- FR-012: System musi umozliwiac zapis i odczyt ustawienia podawania wielkosci opakowania na liscie zakupow.
- FR-013: System musi obslugiwac czesciowa aktualizacje ustawien konta (zmiana jednego pola bez nadpisywania pozostalych).
- FR-014: Domyslnie, dla nowego uzytkownika, ustawienia push i podawania wielkosci opakowania musza byc wlaczone.

### 4.3 Rodzina i czlonkostwo
- FR-015: System musi umozliwiac utworzenie rodziny przez zalogowanego uzytkownika.
- FR-016: Uzytkownik moze byc zalozycielem maksymalnie jednej rodziny.
- FR-017: Przy tworzeniu rodziny system musi zapisac zalozyciela, domyslny sklep i PIN rodziny.
- FR-018: System musi udostepniac dane czlonkostwa zalogowanego uzytkownika w rodzinie.
- FR-019: System musi umozliwiac ustawienie kalorycznosci diety dla czlonka rodziny.
- FR-020: System musi zwracac liste czlonkow rodziny wraz z rolami i przypisanymi dietami.
- FR-021: System musi pozwalac czlonkowi (nie-zalozycielowi) opuscic rodzine.
- FR-022: System nie moze pozwolic zalozycielowi opuscic rodziny operacja leave.
- FR-023: System musi umozliwiac zaproszenie do rodziny przez email.
- FR-024: System musi umozliwiac akceptacje zaproszenia przez token.
- FR-025: System musi walidowac waznosc tokenu zaproszenia (czas i integralnosc).
- FR-026: System nie moze tworzyc duplikatow czlonkostwa dla tego samego uzytkownika i rodziny.

### 4.4 Diety i posilki
- FR-027: System musi udostepniac publiczna, stronicowana liste diet.
- FR-028: System musi udostepniac publiczna, stronicowana liste kalorii diet.
- FR-029: System musi umozliwiac filtrowanie kalorii diet po dieta-id.
- FR-030: System musi udostepniac publiczna, stronicowana liste posilkow.
- FR-031: System musi umozliwiac filtrowanie posilkow po parametrach diety, kalorycznosci, nazwy i pory posilku.
- FR-032: System musi umozliwiac filtrowanie posilkow po czasie przygotowania.
- FR-033: System musi umozliwiac sortowanie posilkow po cenie (najtansze/najdrozsze).
- FR-034: System musi zwracac szczegoly posilku, skladniki i wartosci odzywcze, gdy dane sa dostepne.
- FR-035: System musi udostepniac uproszczona liste produktow (products/simplified) do wykorzystania w interfejsach klienckich.

### 4.5 Kalendarz posilkow rodziny
- FR-036: System musi umozliwiac dodanie zaplanowanego posilku rodziny dla wskazanej daty.
- FR-037: Dla obiadu system musi planowac posilek dla wszystkich czlonkow rodziny.
- FR-038: Dla sniadania i kolacji system musi planowac posilek dla zalogowanego uzytkownika.
- FR-039: Dla obiadu system musi skalowac ilosci skladnikow na podstawie kalorycznosci czlonkow rodziny.
- FR-040: System nie moze pozwolic na wiecej niz jeden obiad tej samej rodziny tego samego dnia.
- FR-041: System musi walidowac istnienie wskazanego posilek_w_diecie_id.
- FR-042: System musi umozliwiac oznaczenie zaplanowanego posilku jako zjedzony.
- FR-043: Oznaczenie jako zjedzony musi aktualizowac stan magazynu rodziny zgodnie z wykorzystanymi skladnikami.

### 4.6 Lista zakupow
- FR-044: System musi umozliwiac utworzenie listy zakupow z kalendarza dla zakresu dat data_od-data_do.
- FR-045: System musi walidowac, ze data_do >= data_od.
- FR-046: System musi zwracac blad, gdy w zakresie dat brak zaplanowanych posilkow.
- FR-047: System musi agregowac skladniki z posilkow do pozycji listy zakupow.
- FR-048: System musi uwzgledniac skalowanie skladnikow dla obiadow rodzinnych.
- FR-049: System musi odejmowac stan magazynu rodziny od ilosci wymaganej na liscie zakupow.
- FR-050: System musi normalizowac jednostki ilosci do spojnego formatu (g/ml).
- FR-051: System musi tworzyc unikalna nazwe listy zakupow, gdy wskazana nazwa juz istnieje.
- FR-052: System musi porzadkowac pozycje wg kategorii sklepu.
- FR-053: System musi udostepniac liste list zakupow rodziny wraz z licznikiem pozycji.
- FR-054: System musi umozliwiac usuniecie listy zakupow.
- FR-055: System musi umozliwiac oznaczenie produktu jako kupionego.
- FR-056: Oznaczenie produktu jako kupionego musi dodac produkt do magazynu rodziny.
- FR-057: System musi obslugiwac opcjonalny zapis wielkosci opakowania i jednostki podczas oznaczania produktu jako kupionego.
- FR-058: System musi zapamietywac ostatnia wielkosc opakowania produktu dla rodziny i podpowiadac ja przy kolejnych zakupach.
- FR-059: System musi obslugiwac oznaczenie kupna takze dla pozycji pochodzacej z widoku live (nieutrwalonej jako rekord pozycji listy).
- FR-060: Po zmianie ustawienia konta "podawanie wielkosci opakowania" aplikacja kliencka musi dzialac bez wymuszania dialogu rozmiaru opakowania.

### 4.7 Magazyn (lodowka) rodziny
- FR-061: System musi udostepniac liste produktow w magazynie rodziny.
- FR-062: System musi zwracac liczbe pozycji w magazynie oraz dane produktow (nazwa, ilosc, jednostka).
- FR-063: System musi udostepniac procent pokrycia posilkow skladnikami z lodowki.
- FR-064: System musi udostepniac liste mozliwych innych posilkow na podstawie aktualnych skladnikow w lodowce.
- FR-065: System musi umozliwiac wyzerowanie lodowki rodziny.
- FR-066: System musi umozliwiac aktualizacje ilosci konkretnego produktu w lodowce.
- FR-067: Ustawienie ilosci produktu w lodowce na 0 musi usuwac produkt z magazynu.

### 4.8 Powiadomienia push i realtime
- FR-068: System musi umozliwiac rejestracje i aktualizacje tokenu urzadzenia FCM dla zalogowanego uzytkownika.
- FR-069: System musi umozliwiac wysylke powiadomienia FCM na wskazany token lub aktywne tokeny uzytkownika.
- FR-070: System musi udostepniac websocket aktualizacji rodziny.
- FR-071: System musi emitowac zdarzenia websocket rodziny po kluczowych zmianach (tworzenie rodziny, zaproszenia, opuszczenie rodziny).
- FR-072: System musi udostepniac websocket live listy zakupow z subskrypcja po shopping_list_id.
- FR-073: Websocket live listy zakupow musi zwracac snapshot po subskrypcji oraz kolejne aktualizacje.
- FR-074: System musi emitowac aktualizacje live listy zakupow po zmianach kalendarza, zmianach diety czlonkow i oznaczeniu produktu jako kupionego.

### 4.9 Funkcje klientow (web/mobile)
- FR-075: Klient web musi obslugiwac logowanie Firebase i wymiane tokenu na JWT backendu.
- FR-076: Klient web musi umozliwiac przeglad diet/posilkow, zarzadzanie rodzina oraz zapis preferencji konta.
- FR-077: Klient mobile musi umozliwiac prace na zakladkach: konto, rodzina, kalendarz, lista zakupow, lodowka.
- FR-078: Klient mobile musi umozliwiac wyszukiwanie produktu w lodowce oraz aktualizacje ilosci produktem suwakiem.

## 5. Reguly walidacji biznesowej
- RV-001: Operacje rodzinne wymagaja istnienia aktywnego czlonkostwa, o ile nie dotycza tworzenia rodziny.
- RV-002: Operacje listy zakupow i magazynu musza dotyczyc danych rodziny zalogowanego uzytkownika.
- RV-003: Zakres dat dla tworzenia listy zakupow musi byc poprawny i kompletny.
- RV-004: Ujemne ilosci produktow nie sa dozwolone.
- RV-005: Jednostki ilosci musza byc zgodne ze wspieranym zakresem domeny (g/ml oraz pochodne mapowane do g/ml).

## 6. Uwagi do dalszego doprecyzowania
- W kolejnym etapie zaleca sie dopisanie priorytetow (MVP, SHOULD, COULD) do kazdego FR.
- Dla wdrozenia produkcyjnego zaleca sie przygotowanie kryteriow akceptacji UAT dla kazdego obszaru (konto, rodzina, kalendarz, zakupy, magazyn).
