import sqlite3
from datetime import datetime
from typing import Optional, Tuple, List, Any

DB_FILE = "fitness.db"


def ensure_db() -> None:
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            goal TEXT NOT NULL CHECK(goal IN ('bulk','cut')),
            age INTEGER,
            gender TEXT,
            activity_level TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS body_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            weight_kg REAL,
            height_cm REAL,
            bodyfat_pct REAL,
            water_l REAL,
            notes TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            workout_type TEXT,
            duration_min INTEGER,
            calories_burned REAL,
            notes TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS foods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            calories_per_unit REAL NOT NULL,
            unit TEXT NOT NULL DEFAULT 'grams',
            protein_g REAL,
            carbs_g REAL,
            fat_g REAL,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS food_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            food_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            calories_consumed REAL NOT NULL,
            notes TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(food_id) REFERENCES foods(id)
        )
        """
    )
    conn.commit()
    conn.close()


def connect():
    return sqlite3.connect(DB_FILE)


def get_user_by_username(username: str) -> Optional[Tuple[Any, ...]]:
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT id, username, goal, password_hash FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    return row


def get_user_profile(user_id: int) -> Optional[Tuple[Any, ...]]:
    """Get user profile including age, gender, activity_level"""
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT id, username, goal, age, gender, activity_level FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def create_user(username: str, password_hash: str, goal: str, age: Optional[int] = None, gender: Optional[str] = None, activity_level: Optional[str] = None) -> None:
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (username, password_hash, goal, age, gender, activity_level, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (username, password_hash, goal, age, gender, activity_level, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def add_body_entry(user_id: int, date: str, weight: float, height: float, bodyfat: Optional[float], water_l: Optional[float], notes: Optional[str]) -> None:
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO body_entries (user_id, date, weight_kg, height_cm, bodyfat_pct, water_l, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, date, weight, height, bodyfat, water_l, notes),
    )
    conn.commit()
    conn.close()


def list_body_entries(user_id: int, limit: int = 20) -> List[Tuple[Any, ...]]:
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT date, weight_kg, height_cm, bodyfat_pct, water_l, notes FROM body_entries WHERE user_id = ? ORDER BY date DESC LIMIT ?",
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def add_workout(user_id: int, date: str, workout_type: str, duration_min: int, calories_burned: float, notes: Optional[str]) -> None:
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO workouts (user_id, date, workout_type, duration_min, calories_burned, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, date, workout_type, duration_min, calories_burned, notes),
    )
    conn.commit()
    conn.close()


def list_workouts(user_id: int, limit: int = 20) -> List[Tuple[Any, ...]]:
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT date, workout_type, duration_min, calories_burned, notes FROM workouts WHERE user_id = ? ORDER BY date DESC LIMIT ?",
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_calories_burned_today(user_id: int, date: str) -> float:
    """Get total calories burned for a specific date"""
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT SUM(calories_burned) FROM workouts WHERE user_id = ? AND date = ?",
        (user_id, date),
    )
    result = cur.fetchone()
    conn.close()
    return result[0] if result[0] else 0.0


def add_food(name: str, calories_per_unit: float, unit: str = "grams", protein_g: Optional[float] = None, carbs_g: Optional[float] = None, fat_g: Optional[float] = None) -> None:
    """Add a food item to the database"""
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO foods (name, calories_per_unit, unit, protein_g, carbs_g, fat_g, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (name, calories_per_unit, unit, protein_g, carbs_g, fat_g, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_all_foods() -> List[Tuple[Any, ...]]:
    """Get all food items"""
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, calories_per_unit, unit, protein_g, carbs_g, fat_g FROM foods ORDER BY name ASC"
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_food_by_id(food_id: int) -> Optional[Tuple[Any, ...]]:
    """Get a food item by ID"""
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, calories_per_unit, unit, protein_g, carbs_g, fat_g FROM foods WHERE id = ?",
        (food_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def add_food_entry(user_id: int, date: str, food_id: int, quantity: float, calories_consumed: float, notes: Optional[str] = None) -> None:
    """Add a food entry for a user"""
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO food_entries (user_id, date, food_id, quantity, calories_consumed, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, date, food_id, quantity, calories_consumed, notes),
    )
    conn.commit()
    conn.close()


def get_food_entries_by_date(user_id: int, date: str) -> List[Tuple[Any, ...]]:
    """Get all food entries for a user on a specific date"""
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT fe.id, fe.date, f.name, fe.quantity, f.unit, fe.calories_consumed, fe.notes
        FROM food_entries fe
        JOIN foods f ON fe.food_id = f.id
        WHERE fe.user_id = ? AND fe.date = ?
        ORDER BY fe.id DESC
        """,
        (user_id, date),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_calories_consumed_today(user_id: int, date: str) -> float:
    """Get total calories consumed for a specific date"""
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT SUM(calories_consumed) FROM food_entries WHERE user_id = ? AND date = ?",
        (user_id, date),
    )
    result = cur.fetchone()
    conn.close()
    return result[0] if result[0] else 0.0


def delete_food_entry(entry_id: int) -> None:
    """Delete a food entry"""
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM food_entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
