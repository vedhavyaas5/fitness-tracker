# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project overview

This repo is a small Flask-based web application for tracking health metrics, logging workouts, computing BMI/BMR, estimating maintenance calories, and visualizing progress. The core business logic lives under `src/fitness_tracker`, while `app.py` wires that logic into HTTP routes and templates.

## How to run the app

### Environment setup

The app targets Python 3 with dependencies managed via `pip`.

Typical workflow:

1. (Optional but recommended) Create a virtualenv, e.g. on most systems:
   - `python -m venv .venv`
   - Activate it for your shell (on PowerShell: `.venv/Scripts/Activate.ps1`).
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Run the development server:
   - `python app.py`
4. Visit the app in a browser at `http://127.0.0.1:5000/`.

There is no separate build step; this is a plain Flask app run directly by the Python interpreter.

### Database and persistence

The active persistence layer used by the app is MongoDB, via `src/fitness_tracker/db_mongo.py`:

- `app.py` imports `db_mongo` as `db` and calls `db.ensure_db()` at startup to create indexes and seed a default admin user.
- `db_mongo.py` tries to connect to a real MongoDB instance using the `MONGO_URI` environment variable (defaulting to `mongodb://localhost:27017/fitness_tracker`). If connection fails, it transparently falls back to an in-memory `mongomock` client.

Practical implications for agents:

- For ephemeral local development you can simply run `python app.py`; the app will use `mongomock` if no MongoDB server is available.
- To exercise a real MongoDB backend, set `MONGO_URI` before running the app. For example:
  - POSIX shells: `MONGO_URI="mongodb://localhost:27017/fitness_tracker" python app.py`
  - PowerShell: `$env:MONGO_URI = "mongodb://localhost:27017/fitness_tracker"; python app.py`

There is a legacy SQLite-based implementation in `src/fitness_tracker/db.py` that is not currently wired into `app.py`. New backend-related work should target the MongoDB implementation in `db_mongo.py` unless you are explicitly refactoring storage.

### Tests and linting

As of this snapshot, the repository does not contain an explicit test suite (no `tests/` package, pytest configuration, or tox/CI scripts) and there is no configured linter or formatter.

If you introduce tests or linting, prefer to:

- Add a dedicated test runner (e.g. `pytest`) and document the canonical commands here.
- Add any lint/format commands (e.g. `ruff`, `flake8`, `black`) and update this section with the exact CLI invocations.

## High-level architecture

### Top-level structure

- `app.py`
  - Creates the Flask `app` instance and sets `app.secret_key` for session management.
  - Imports the domain logic (`bmi`, `bmr_mifflin_st_jeor`) from `src/fitness_tracker/analysis.py`.
  - Imports the data-access layer as `db` from `src/fitness_tracker/db_mongo.py`.
  - Calls `db.ensure_db()` on startup to initialize indexes and seed a development admin user.
  - Defines all HTTP routes, grouping them into:
    - Authentication (`/`, `/register`, `/login`, `/logout`).
    - User dashboard and core flows (`/dashboard`, `/body`, `/workout`, `/body/log`, `/workout/log`).
    - Food logging and nutrition (`/food/log`, `/food/add`, `/api/foods`, `/api/food-entries`, `/api/food-entries/<entry_id>` DELETE).
    - Suggestions and schedules (`/suggestions`, `/schedules`).
    - Admin functionality (`/admin/login`, `/admin`, `/admin/user/update`, `/admin/suggest`, `/admin/schedule`, `/admin/assign-workout`).
  - Uses Jinja2 templates under `templates/` and static assets under `static/` for the UI.

### Domain logic (`src/fitness_tracker/analysis.py`)

- Encapsulates key fitness calculations that should be reused across routes:
  - `bmi(weight_kg, height_cm)` computes BMI with basic error handling and returns a rounded value or `None`.
  - `bmr_mifflin_st_jeor(weight_kg, height_cm, age, sex)` computes BMR using the Mifflin–St Jeor equation and returns `None` for unsupported/invalid sex values.
- `app.py` calls these helpers during registration and when building dashboard/food views to compute BMI and maintenance calories.

When adding new features that need BMI/BMR or related calculations, prefer to extend this module instead of inlining formulas in view functions.

### Persistence layer (`src/fitness_tracker/db_mongo.py`)

This module provides a MongoDB-backed DAO-style API that mirrors the logical tables in the legacy SQLite backend:

- Users: `users_col`
  - Functions like `get_user_by_username`, `create_user`, `list_users`, and `update_user_goal_activity` encapsulate user CRUD and role/goal/activity tracking.
  - `ensure_db` seeds a development admin user (`username="admin123"`, password hash for `"123456"`, role `"admin"`).

- Body entries: `body_entries_col`
  - `add_body_entry`, `list_body_entries` manage weight/height/body fat/water logs and expose them to the app as simple tuples.

- Workouts: `workouts_col`
  - `add_workout`, `list_workouts`, and `get_calories_burned_today` track exercise sessions and calories burned per day.

- Foods and food entries: `foods_col`, `food_entries_col`
  - `add_food`, `get_all_foods`, `get_food_by_id`, `get_food_by_name` manage the catalog of foods.
  - `add_food_entry`, `get_food_entries_by_date`, and `get_calories_consumed_today` track user-specific intake, joining entries with food metadata.

- Coaching and scheduling: `suggestions_col`, `schedules_col`
  - `add_suggestion`, `list_suggestions` store short coach/admin suggestions associated with users.
  - `add_schedule`, `list_schedules` store per-user scheduled items (including structured workout plans, which are formatted into a readable text block before storage).

All public functions in this module are written so that `app.py` can treat document IDs as either raw ObjectIds or their string representations; conversion is handled internally.

### Legacy SQLite backend (`src/fitness_tracker/db.py`)

This module mirrors most of the same concepts (users, body entries, workouts, foods, food entries) but uses SQLite and SQL DDL instead of MongoDB. It is not currently imported by `app.py`, but the API shape is similar:

- `ensure_db()` creates tables and indexes.
- CRUD-style helpers (`create_user`, `add_body_entry`, `list_body_entries`, `add_workout`, `list_workouts`, `add_food`, `get_all_foods`, `get_food_by_id`, `add_food_entry`, `get_food_entries_by_date`, `get_calories_burned_today`, `get_calories_consumed_today`, `delete_food_entry`).

If you plan a storage refactor (e.g., moving back to SQLite or adding migrations), be aware of this parallel implementation.

### Web layer and sessions

- User sessions
  - Stored in `flask.session` as a small dict: `{id, username, goal, role}`.
  - `login` and `admin_login` set this structure; `logout` clears it.
  - `require_admin()` is a small helper that checks `session["user"]["role"] == "admin"` and is used before all admin routes.

- Templates and views
  - Each primary flow has a dedicated template in `templates/`:
    - Authentication: `index.html`, `login.html`, `register.html`.
    - Main experience: `dashboard.html`, `log_body.html`, `log_workout.html`, `log_food.html`.
    - Admin: `admin_login.html`, `admin_dashboard.html`.
  - `base.html` provides shared layout, and routes pass minimal, preprocessed data structures into templates (e.g., recent entries, workouts, calorie totals, maintenance calories).

- JSON APIs
  - Food/nutrition-related routes expose JSON endpoints for dynamic UIs or external clients:
    - `GET /api/foods` lists all foods as JSON.
    - `GET /api/food-entries?date=YYYY-MM-DD` returns entries for a specific date.
    - `DELETE /api/food-entries/<entry_id>` removes a specific entry.
  - Suggestions and schedules also have simple JSON-returning endpoints (`/suggestions`, `/schedules`) keyed by the current session user.

## Notes for future Warp agents

- When adding new features that touch persistence, extend `db_mongo.py` and reuse its ObjectId-handling patterns rather than bypassing it with raw PyMongo calls in `app.py`.
- Keep new fitness-related calculations in `src/fitness_tracker/analysis.py` so they stay reusable between the dashboard, registration, and any future APIs.
- Respect the existing session shape (`{"id", "username", "goal", "role"}`) and `require_admin()` when adding new protected routes or admin capabilities.
