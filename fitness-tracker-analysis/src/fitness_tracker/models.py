from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from . import db_mongo as db
from .analysis import bmi, bmr_mifflin_st_jeor


# ---------------------- Base log & subclasses ----------------------


@dataclass
class Log:
    """Base class for time-stamped, per-user logs.

    Subclasses should implement `save()` to persist themselves via the db layer.
    """

    user_id: Any
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    notes: Optional[str] = None

    def save(self) -> None:  # pragma: no cover - interface method
        raise NotImplementedError


@dataclass
class WorkoutLog(Log):
    """Represents a single workout entry for a user."""

    workout_type: str = "other"
    duration_min: int = 0
    calories_burned: float = 0.0

    def save(self) -> None:
        """Persist this workout via the db layer."""

        db.add_workout(
            user_id=self.user_id,
            date=self.date,
            workout_type=self.workout_type,
            duration_min=self.duration_min,
            calories_burned=self.calories_burned,
            notes=self.notes,
        )

    @classmethod
    def from_payload(cls, user_id: Any, payload: Dict[str, Any]) -> "WorkoutLog":
        """Factory to build from form or JSON payload.

        The caller is responsible for validating authentication; here we only
        normalize and coerce types.
        """

        date = (payload.get("date") or datetime.now().strftime("%Y-%m-%d")).strip()
        workout_type = (payload.get("workout_type") or "other").strip()

        try:
            duration = int(payload.get("duration_min", 0) or 0)
        except Exception:
            duration = 0

        # Allow caller to pass calories directly; otherwise approximate.
        calories_val = payload.get("calories_burned")
        try:
            if calories_val in (None, ""):
                calories = duration * 6.0  # simple heuristic used in app.py
            else:
                calories = float(calories_val)
        except Exception:
            calories = duration * 6.0

        notes = payload.get("notes") or None

        return cls(
            user_id=user_id,
            date=date,
            notes=notes,
            workout_type=workout_type,
            duration_min=duration,
            calories_burned=calories,
        )


@dataclass
class FoodLog(Log):
    """Represents a food intake entry for a user."""

    food_id: Any = None
    quantity: float = 0.0
    calories_consumed: float = 0.0

    def save(self) -> None:
        """Persist this food entry via the db layer."""

        db.add_food_entry(
            user_id=self.user_id,
            date=self.date,
            food_id=self.food_id,
            quantity=self.quantity,
            calories_consumed=self.calories_consumed,
            notes=self.notes,
        )

    @classmethod
    def manual_entry(
        cls,
        user_id: Any,
        date: Optional[str],
        name: str,
        quantity: float,
        calories_per_unit: float,
        unit: str = "grams",
        protein_g: Optional[float] = None,
        carbs_g: Optional[float] = None,
        fat_g: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> "FoodLog":
        """Create (and ensure) a manual food in the catalog and a corresponding log.

        This mirrors the "manual_" flow in app.py but encapsulates it.
        """

        # Upsert-ish behavior: reuse if existing, otherwise create.
        food = db.get_food_by_name(name)
        if not food:
            db.add_food(
                name=name,
                calories_per_unit=calories_per_unit,
                unit=unit,
                protein_g=protein_g,
                carbs_g=carbs_g,
                fat_g=fat_g,
            )
            food = db.get_food_by_name(name)
        if not food:
            raise ValueError("Unable to create or retrieve manual food entry")

        # food tuple layout: (id, name, calories_per_unit, unit, protein_g, carbs_g, fat_g)
        food_id = food[0]
        date_str = date or datetime.now().strftime("%Y-%m-%d")
        calories_consumed = calories_per_unit * quantity

        return cls(
            user_id=user_id,
            date=date_str,
            notes=notes,
            food_id=food_id,
            quantity=quantity,
            calories_consumed=calories_consumed,
        )

    @classmethod
    def from_catalog_item(
        cls,
        user_id: Any,
        date: Optional[str],
        food_record: Tuple[Any, str, float, str, Any, Any, Any],
        quantity: float,
        notes: Optional[str] = None,
    ) -> "FoodLog":
        """Build a log from an existing food catalog record.

        `food_record` is expected to match the tuple layout returned by
        `db.get_food_by_id` / `db.get_all_foods`.
        """

        food_id, _name, calories_per_unit, _unit, _p, _c, _f = food_record
        date_str = date or datetime.now().strftime("%Y-%m-%d")
        calories_consumed = float(calories_per_unit) * quantity

        return cls(
            user_id=user_id,
            date=date_str,
            notes=notes,
            food_id=food_id,
            quantity=quantity,
            calories_consumed=calories_consumed,
        )


# ---------------------- User & Admin domain objects ----------------------


@dataclass
class User:
    """Domain model for an authenticated user.

    This class encapsulates profile data and common high-level operations that
    involve multiple db calls (e.g., building a dashboard view).
    """

    id: Any
    username: str
    goal: str = "cut"  # "bulk" or "cut"
    age: Optional[int] = None
    gender: Optional[str] = None
    activity_level: Optional[str] = None
    role: str = "user"

    # ---------- Construction helpers ----------

    @classmethod
    def from_profile(cls, user_id: Any) -> Optional["User"]:
        """Load a user from the db using the profile view.

        This uses `db.get_user_profile`, which returns a tuple
        (id, username, goal, age, gender, activity_level) or None.
        """

        profile = db.get_user_profile(user_id)
        if not profile:
            return None

        uid, username, goal, age, gender, activity_level = profile

        # Try to discover role from the main lookup; fall back to "user".
        base = db.get_user_by_username(username)
        role = base[4] if base and len(base) >= 5 else "user"

        return cls(
            id=uid,
            username=username,
            goal=goal,
            age=age,
            gender=gender,
            activity_level=activity_level,
            role=role,
        )

    # ---------- Business logic helpers ----------

    def is_admin(self) -> bool:
        return self.role == "admin"

    def maintenance_calories(self) -> Optional[int]:
        """Estimate maintenance calories from the latest body entry.

        Returns an integer kcal/day or None if not enough data is available.
        """

        entries = db.list_body_entries(self.id, limit=1)
        if not entries:
            return None

        latest = entries[0]
        # SQLite adapter returns (date, weight, height, ...), Mongo adapter mirrors this
        date_str, weight, height, *_rest = latest

        if not (self.age and self.gender and weight and height):
            return None

        bmr = bmr_mifflin_st_jeor(weight, height, self.age, self.gender)
        if not bmr:
            return None

        activity_multipliers = {
            "sedentary": 1.2,
            "lightly_active": 1.375,
            "moderately_active": 1.55,
            "very_active": 1.725,
            "extra_active": 1.9,
        }
        return round(bmr * activity_multipliers.get(self.activity_level or "sedentary", 1.2))

    def recent_body_entries(self, limit: int = 5) -> List[Tuple[Any, ...]]:
        return db.list_body_entries(self.id, limit=limit)

    def recent_workouts(self, limit: int = 5) -> List[Tuple[Any, ...]]:
        return db.list_workouts(self.id, limit=limit)

    def calories_for_date(self, date: Optional[str] = None) -> Dict[str, float]:
        """Return calories burned/consumed for a given date (default: today)."""

        date_str = date or datetime.now().strftime("%Y-%m-%d")
        burned = db.get_calories_burned_today(self.id, date_str)
        consumed = db.get_calories_consumed_today(self.id, date_str)
        return {"date": date_str, "burned": burned, "consumed": consumed}

    def log_body(
        self,
        weight_kg: float,
        height_cm: float,
        bodyfat_pct: Optional[float] = None,
        water_l: Optional[float] = None,
        date: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Optional[float]]:
        """Create a body entry and return derived metrics (e.g., BMI)."""

        date_str = date or datetime.now().strftime("%Y-%m-%d")
        db.add_body_entry(
            user_id=self.id,
            date=date_str,
            weight=weight_kg,
            height=height_cm,
            bodyfat=bodyfat_pct,
            water_l=water_l,
            notes=notes,
        )
        return {"bmi": bmi(weight_kg, height_cm)}

    def log_workout_from_payload(self, payload: Dict[str, Any]) -> WorkoutLog:
        """Create and persist a WorkoutLog from an incoming payload."""

        log = WorkoutLog.from_payload(self.id, payload)
        log.save()
        return log

    def log_food_from_manual(
        self,
        name: str,
        quantity: float,
        calories_per_unit: float,
        unit: str = "grams",
        protein_g: Optional[float] = None,
        carbs_g: Optional[float] = None,
        fat_g: Optional[float] = None,
        date: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> FoodLog:
        """Create and persist a manual FoodLog (and catalog item if needed)."""

        log = FoodLog.manual_entry(
            user_id=self.id,
            date=date,
            name=name,
            quantity=quantity,
            calories_per_unit=calories_per_unit,
            unit=unit,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            notes=notes,
        )
        log.save()
        return log

    def log_food_from_catalog(
        self,
        food_id: Any,
        quantity: float,
        date: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> FoodLog:
        """Create and persist a FoodLog from an existing food catalog item."""

        food = db.get_food_by_id(food_id)
        if not food:
            raise ValueError("Food not found")

        log = FoodLog.from_catalog_item(
            user_id=self.id,
            date=date,
            food_record=food,
            quantity=quantity,
            notes=notes,
        )
        log.save()
        return log

    def delete_food_entry(self, entry_id: Any) -> None:
        db.delete_food_entry(entry_id)

    def suggestions(self, limit: int = 20) -> List[Tuple[str, Optional[str], Optional[str]]]:
        return db.list_suggestions(self.id, limit=limit)

    def schedules(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Tuple[str, str, Optional[str]]]:
        return db.list_schedules(self.id, start_date=start_date, end_date=end_date)


@dataclass
class Admin(User):
    """Admin user with additional management capabilities.

    This is a thin wrapper on top of `User` that exposes higher-level admin
    actions in terms of the underlying db operations.
    """

    role: str = "admin"

    # ---------- Construction helpers ----------

    @classmethod
    def from_username(cls, username: str) -> Optional["Admin"]:
        record = db.get_user_by_username(username)
        if not record or len(record) < 5:
            return None
        user_id, uname, goal, _pw_hash, role = record
        if role != "admin":
            return None

        # Try to enrich with profile data where available
        profile = db.get_user_profile(user_id)
        if profile:
            _pid, _pname, pgoal, age, gender, activity_level = profile
            return cls(
                id=user_id,
                username=uname,
                goal=pgoal or goal,
                age=age,
                gender=gender,
                activity_level=activity_level,
                role=role,
            )

        return cls(id=user_id, username=uname, goal=goal, role=role)

    # ---------- Admin capabilities ----------

    def list_users(self) -> List[Tuple[Any, str, Any, Any, Any, Any, str, Any]]:
        """Return the admin dashboard summary of users.

        Mirrors the tuple layout constructed in app.py's admin dashboard:
        (id, username, goal, age, gender, activity_level, role, created_at).
        """

        return db.list_users()

    def update_user(
        self,
        user_id: Any,
        goal: Optional[str] = None,
        activity_level: Optional[str] = None,
    ) -> None:
        db.update_user_goal_activity(user_id, goal=goal, activity_level=activity_level)

    def send_suggestion(self, user_id: Any, text: str) -> None:
        db.add_suggestion(user_id=user_id, text=text, author=self.username)

    def schedule_item(
        self,
        user_id: Any,
        title: str,
        date: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        date_str = date or datetime.now().strftime("%Y-%m-%d")
        db.add_schedule(user_id=user_id, date=date_str, title=title, notes=notes)

    def assign_workout_plan(
        self,
        user_id: Any,
        plan_name: str,
        exercises: List[Dict[str, Any]],
        date: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        """Assign a structured workout plan as a scheduled item.

        `exercises` is a list of dicts with keys like {"exercise", "sets", "reps"}.
        This mirrors the behavior of the `/admin/assign-workout` route in app.py
        but encapsulates the formatting and persistence here.
        """

        date_str = date or datetime.now().strftime("%Y-%m-%d")

        workout_text = f"Workout Plan: {plan_name}\n\n"
        for item in exercises:
            ex = item.get("exercise")
            sets = item.get("sets")
            reps = item.get("reps")
            if ex:
                workout_text += f"• {ex}: {sets} sets × {reps} reps\n"

        if notes:
            workout_text += f"\nNotes: {notes}"

        db.add_schedule(user_id=user_id, date=date_str, title=plan_name, notes=workout_text)
