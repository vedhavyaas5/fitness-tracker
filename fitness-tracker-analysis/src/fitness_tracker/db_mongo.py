import os
from datetime import datetime
from typing import Optional, List, Dict, Any

# Use mongomock for development if MongoDB is not available
try:
    from pymongo import MongoClient
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/fitness_tracker")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    # Test connection
    client.admin.command('ping')
    print("Connected to MongoDB")
except Exception as e:
    print(f"MongoDB connection failed: {e}. Using mongomock instead.")
    import mongomock
    client = mongomock.MongoClient()

from bson.objectid import ObjectId

db = client.get_database("fitness_tracker")

# Collections
users_col = db["users"]
body_entries_col = db["body_entries"]
workouts_col = db["workouts"]
foods_col = db["foods"]
food_entries_col = db["food_entries"]
suggestions_col = db["suggestions"]
schedules_col = db["schedules"]


def ensure_db() -> None:
    """Create indexes for collections and seed admin"""
    # Users collection
    users_col.create_index("username", unique=True)
    
    # Body entries collection
    body_entries_col.create_index([("user_id", 1), ("date", -1)])
    
    # Workouts collection
    workouts_col.create_index([("user_id", 1), ("date", -1)])
    
    # Foods collection
    foods_col.create_index("name", unique=True)
    
    # Food entries collection
    food_entries_col.create_index([("user_id", 1), ("date", -1)])

    # Suggestions collection
    suggestions_col.create_index([("user_id", 1), ("created_at", -1)])

    # Schedules collection
    schedules_col.create_index([("user_id", 1), ("date", 1)])

    # Seed default admin if missing (dev-only)
    try:
        if not users_col.find_one({"username": "admin123"}):
            users_col.insert_one({
                "username": "admin123",
                # sha256("123456")
                "password_hash": "8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92",
                "goal": "cut",
                "role": "admin",
                "created_at": datetime.utcnow().isoformat(),
            })
    except Exception:
        pass


def get_user_by_username(username: str) -> Optional[Dict[Any, ...]]:
    """Get user by username"""
    user = users_col.find_one({"username": username})
    if user:
        return (user["_id"], user["username"], user.get("goal"), user["password_hash"], user.get("role", "user"))
    return None


def get_user_profile(user_id: Any) -> Optional[Dict[Any, ...]]:
    """Get user profile including age, gender, activity_level"""
    user = users_col.find_one({"_id": ObjectId(user_id) if isinstance(user_id, str) else user_id})
    if user:
        return (
            user["_id"],
            user["username"],
            user.get("goal"),
            user.get("age"),
            user.get("gender"),
            user.get("activity_level"),
        )
    return None


def create_user(
    username: str,
    password_hash: str,
    goal: str,
    age: Optional[int] = None,
    gender: Optional[str] = None,
    activity_level: Optional[str] = None,
    role: str = "user",
) -> None:
    """Create a new user"""
    users_col.insert_one(
        {
            "username": username,
            "password_hash": password_hash,
            "goal": goal,
            "age": age,
            "gender": gender,
            "activity_level": activity_level,
            "role": role,
            "created_at": datetime.utcnow().isoformat(),
        }
    )

def list_users() -> List[Dict[str, Any]]:
    users = list(users_col.find().sort("created_at", -1))
    return [
        (
            u["_id"],
            u.get("username"),
            u.get("goal"),
            u.get("age"),
            u.get("gender"),
            u.get("activity_level"),
            u.get("role", "user"),
            u.get("created_at"),
        )
        for u in users
    ]

def update_user_goal_activity(user_id: Any, goal: Optional[str] = None, activity_level: Optional[str] = None) -> None:
    updates: Dict[str, Any] = {}
    if goal:
        updates["goal"] = goal
    if activity_level:
        updates["activity_level"] = activity_level
    if updates:
        users_col.update_one({"_id": ObjectId(user_id) if isinstance(user_id, str) else user_id}, {"$set": updates})


def add_body_entry(
    user_id: Any,
    date: str,
    weight: float,
    height: float,
    bodyfat: Optional[float],
    water_l: Optional[float],
    notes: Optional[str],
) -> None:
    """Add a body entry"""
    body_entries_col.insert_one(
        {
            "user_id": ObjectId(user_id) if isinstance(user_id, str) else user_id,
            "date": date,
            "weight_kg": weight,
            "height_cm": height,
            "bodyfat_pct": bodyfat,
            "water_l": water_l,
            "notes": notes,
            "created_at": datetime.utcnow().isoformat(),
        }
    )


def list_body_entries(user_id: Any, limit: int = 20) -> List[Dict[Any, ...]]:
    """Get body entries for a user"""
    user_oid = ObjectId(user_id) if isinstance(user_id, str) else user_id
    entries = list(
        body_entries_col.find({"user_id": user_oid})
        .sort("date", -1)
        .limit(limit)
    )
    return [
        (e["date"], e["weight_kg"], e["height_cm"], e.get("bodyfat_pct"), e.get("water_l"), e.get("notes"))
        for e in entries
    ]


def add_workout(
    user_id: Any,
    date: str,
    workout_type: str,
    duration_min: int,
    calories_burned: float,
    notes: Optional[str],
) -> None:
    """Add a workout entry"""
    workouts_col.insert_one(
        {
            "user_id": ObjectId(user_id) if isinstance(user_id, str) else user_id,
            "date": date,
            "workout_type": workout_type,
            "duration_min": duration_min,
            "calories_burned": calories_burned,
            "notes": notes,
            "created_at": datetime.utcnow().isoformat(),
        }
    )


def list_workouts(user_id: Any, limit: int = 20) -> List[Dict[Any, ...]]:
    """Get workouts for a user"""
    user_oid = ObjectId(user_id) if isinstance(user_id, str) else user_id
    workouts = list(
        workouts_col.find({"user_id": user_oid})
        .sort("date", -1)
        .limit(limit)
    )
    return [
        (w["date"], w["workout_type"], w["duration_min"], w["calories_burned"], w.get("notes"))
        for w in workouts
    ]


def get_calories_burned_today(user_id: Any, date: str) -> float:
    """Get total calories burned for a specific date"""
    user_oid = ObjectId(user_id) if isinstance(user_id, str) else user_id
    result = workouts_col.aggregate(
        [
            {"$match": {"user_id": user_oid, "date": date}},
            {"$group": {"_id": None, "total": {"$sum": "$calories_burned"}}},
        ]
    )
    result_list = list(result)
    return result_list[0]["total"] if result_list else 0.0


def add_food(
    name: str,
    calories_per_unit: float,
    unit: str = "grams",
    protein_g: Optional[float] = None,
    carbs_g: Optional[float] = None,
    fat_g: Optional[float] = None,
) -> None:
    """Add a food item"""
    foods_col.insert_one(
        {
            "name": name,
            "calories_per_unit": calories_per_unit,
            "unit": unit,
            "protein_g": protein_g,
            "carbs_g": carbs_g,
            "fat_g": fat_g,
            "created_at": datetime.utcnow().isoformat(),
        }
    )


def get_all_foods() -> List[Dict[Any, ...]]:
    """Get all food items"""
    foods = list(foods_col.find().sort("name", 1))
    return [
        (
            food["_id"],
            food["name"],
            food["calories_per_unit"],
            food["unit"],
            food.get("protein_g"),
            food.get("carbs_g"),
            food.get("fat_g"),
        )
        for food in foods
    ]


def get_food_by_id(food_id: Any) -> Optional[Dict[Any, ...]]:
    """Get a food item by ID"""
    food = foods_col.find_one({"_id": ObjectId(food_id) if isinstance(food_id, str) else food_id})
    if food:
        return (
            food["_id"],
            food["name"],
            food["calories_per_unit"],
            food["unit"],
            food.get("protein_g"),
            food.get("carbs_g"),
            food.get("fat_g"),
        )
    return None


def get_food_by_name(food_name: str) -> Optional[Dict[Any, ...]]:
    """Get a food item by name"""
    food = foods_col.find_one({"name": food_name})
    if food:
        return (
            food["_id"],
            food["name"],
            food["calories_per_unit"],
            food["unit"],
            food.get("protein_g"),
            food.get("carbs_g"),
            food.get("fat_g"),
        )
    return None


def add_food_entry(
    user_id: Any,
    date: str,
    food_id: Any,
    quantity: float,
    calories_consumed: float,
    notes: Optional[str] = None,
) -> None:
    """Add a food entry for a user"""
    food_entries_col.insert_one(
        {
            "user_id": ObjectId(user_id) if isinstance(user_id, str) else user_id,
            "date": date,
            "food_id": ObjectId(food_id) if isinstance(food_id, str) else food_id,
            "quantity": quantity,
            "calories_consumed": calories_consumed,
            "notes": notes,
            "created_at": datetime.utcnow().isoformat(),
        }
    )


def get_food_entries_by_date(user_id: Any, date: str) -> List[Dict[Any, ...]]:
    """Get all food entries for a user on a specific date"""
    user_oid = ObjectId(user_id) if isinstance(user_id, str) else user_id
    
    # Aggregation pipeline with lookup to join food data
    entries = list(
        food_entries_col.aggregate(
            [
                {"$match": {"user_id": user_oid, "date": date}},
                {
                    "$lookup": {
                        "from": "foods",
                        "localField": "food_id",
                        "foreignField": "_id",
                        "as": "food",
                    }
                },
                {"$unwind": "$food"},
                {"$sort": {"_id": -1}},
            ]
        )
    )
    
    return [
        (
            entry["_id"],
            entry["date"],
            entry["food"]["name"],
            entry["quantity"],
            entry["food"]["unit"],
            entry["calories_consumed"],
            entry.get("notes"),
        )
        for entry in entries
    ]


def get_calories_consumed_today(user_id: Any, date: str) -> float:
    """Get total calories consumed for a specific date"""
    user_oid = ObjectId(user_id) if isinstance(user_id, str) else user_id
    result = food_entries_col.aggregate(
        [
            {"$match": {"user_id": user_oid, "date": date}},
            {"$group": {"_id": None, "total": {"$sum": "$calories_consumed"}}},
        ]
    )
    result_list = list(result)
    return result_list[0]["total"] if result_list else 0.0


def delete_food_entry(entry_id: Any) -> None:
    """Delete a food entry"""
    food_entries_col.delete_one({"_id": ObjectId(entry_id) if isinstance(entry_id, str) else entry_id})


def add_suggestion(user_id: Any, text: str, author: str) -> None:
    suggestions_col.insert_one({
        "user_id": ObjectId(user_id) if isinstance(user_id, str) else user_id,
        "text": text,
        "author": author,
        "created_at": datetime.utcnow().isoformat(),
    })


def list_suggestions(user_id: Any, limit: int = 20) -> List[Dict[str, Any]]:
    user_oid = ObjectId(user_id) if isinstance(user_id, str) else user_id
    items = list(suggestions_col.find({"user_id": user_oid}).sort("created_at", -1).limit(limit))
    return [ (s.get("text"), s.get("author"), s.get("created_at")) for s in items ]


def add_schedule(user_id: Any, date: str, title: str, notes: Optional[str] = None) -> None:
    schedules_col.insert_one({
        "user_id": ObjectId(user_id) if isinstance(user_id, str) else user_id,
        "date": date,
        "title": title,
        "notes": notes,
        "created_at": datetime.utcnow().isoformat(),
    })


def list_schedules(user_id: Any, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
    user_oid = ObjectId(user_id) if isinstance(user_id, str) else user_id
    query: Dict[str, Any] = {"user_id": user_oid}
    if start_date or end_date:
        rng: Dict[str, Any] = {}
        if start_date:
            rng["$gte"] = start_date
        if end_date:
            rng["$lte"] = end_date
        query["date"] = rng
    items = list(schedules_col.find(query).sort("date", 1))
    return [ (s.get("date"), s.get("title"), s.get("notes")) for s in items ]
