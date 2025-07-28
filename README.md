# System Zarządzania Reklamami Multimedialnymi

Aplikacja umożliwia zarządzanie reklamami (obrazy, filmy) w strukturze: **sklepy → działy → stoiska**. Użytkownicy mają różne role i uprawnienia. System pozwala na zarządzanie treściami, ich prezentację w formie karuzeli oraz obsługę odtwarzaczy przez API.

---

## 1. Wstęp

System służy do zarządzania i prezentowania reklam multimedialnych w środowisku sklepowym. Pozwala na elastyczne zarządzanie treściami i ich prezentacją.

---

## 2. Architektura

- **Backend:** Django 5.x, Django REST Framework
- **Frontend:** HTML5, Bootstrap 5, JavaScript (jQuery, Chart.js)
- **Baza danych:** SQLite (domyślnie) lub PostgreSQL
- **Przechowywanie plików:** lokalny filesystem (`MEDIA_ROOT`)
- **Autoryzacja:** Django Auth + Token Auth (dla API)

---

## 3. Modele danych

- **Store (Sklep):**
  - `name` – nazwa sklepu
  - `location` – lokalizacja
  - `created_at`, `updated_at`
- **Department (Dział):**
  - `name` – nazwa działu
  - `store` – FK do Store
  - `created_at`, `updated_at`
- **Stand (Stoisko):**
  - `name` – nazwa stoiska
  - `department` – FK do Department
  - `display_time` – domyślny czas wyświetlania materiału
  - `transition_animation` – efekt przejścia (fade, slide, zoom, flip, none)
  - `created_at`, `updated_at`
- **AdvertisementMaterial (Materiał reklamowy):**
  - `stand` – FK do Stand
  - `material_type` – obraz/film
  - `file` – plik multimedialny
  - `order` – kolejność
  - `status` – aktywny/nieaktywny
  - `duration` – czas wyświetlania
  - `created_at`, `updated_at`
- **PlayerStatus:**
  - `stand` – FK do Stand (OneToOne)
  - `is_online`, `last_seen`, `ip_address`, `user_agent`, `screen_resolution`, `version`, `errors`
- **User (Custom):**
  - `role` – superadmin, store_admin, editor, player
  - `managed_store` – FK do Store (dla admina sklepu)
  - `managed_stand` – FK do Stand (dla edytora/odtwarzacza)
  - `access_token` – dla API

---

## 4. Role i uprawnienia

- **Superadmin:** pełny dostęp do wszystkiego
- **Administrator sklepu:** zarządza jednym sklepem i jego strukturą
- **Edytor stanowiska:** edycja tylko przypisanego stoiska i materiałów
- **Odtwarzacz (Player):** tylko pobieranie materiałów przez API

Uprawnienia wymuszane są przez mixiny (`SuperadminRequiredMixin`, `StoreAdminRequiredMixin`, `EditorRequiredMixin`, `StoreAccessMixin`) oraz w API przez `IsPlayerOrAdmin`.

---

## 5. Główne funkcjonalności

- Zarządzanie sklepami, działami, stoiskami (CRUD)
- Zarządzanie materiałami reklamowymi (dodawanie, edycja, usuwanie, zmiana kolejności drag & drop)
- Panel administratora sklepu – statystyki, szybkie akcje, monitoring odtwarzaczy
- Panel edytora – podgląd i zarządzanie materiałami na przypisanym stoisku
- Panel odtwarzacza – generowanie tokenu, QR, pobieranie konfiguracji
- Panel superadmina – monitoring wszystkich sklepów i odtwarzaczy
- Publiczne API – pobieranie materiałów dla odtwarzacza, raportowanie statusu, autoryzacja tokenem
- Animacje przejść – fade, slide, zoom, flip, none

---

## 6. API

- `GET /advertisements/api/stand/<stand_id>/`  
  Pobiera listę aktywnych materiałów dla stoiska (autoryzacja tokenem)
- `POST /advertisements/api/token/`  
  Pobiera token dla odtwarzacza (login, hasło)
- `POST /advertisements/api/player/status/`  
  Raportuje status odtwarzacza (heartbeat)
- `GET /advertisements/api/player/status/<stand_id>/`  
  Pobiera status odtwarzacza (dla panelu admina)

---

## 7. Szablony i widoki

- **Panel logowania/rejestracji:** `login.html`, `register.html`
- **Dashboardy:**
  - Superadmin: `dashboard_superadmin.html`
  - Admin sklepu: `dashboard_store_admin.html`
  - Edytor: `dashboard_editor.html`
  - Odtwarzacz: `dashboard_player.html`
- **Zarządzanie sklepami:** `store_list.html`, `store_form.html`, `store_detail.html`, `store_confirm_delete.html`
- **Zarządzanie działami:** `department_form.html`, `department_confirm_delete.html`
- **Zarządzanie stoiskami:** `stand_form.html`, `stand_confirm_delete.html`
- **Materiały:** `stand_materials.html`, `material_form.html`, `material_confirm_delete.html`
- **Odtwarzacz:** `player.html`

---

## 8. Walidacja i bezpieczeństwo

- Walidacja typów i rozmiarów plików (FileExtensionValidator, limit 10MB)
- Ograniczenie dostępu do widoków i API na podstawie roli użytkownika
- Przechowywanie plików w katalogu `MEDIA_ROOT` (dostęp tylko dla uprawnionych)

---

## 9. Instalacja i uruchomienie

1. **Klonowanie repozytorium**
2. **Instalacja zależności**
   ```sh
   pip install -r req.txt
