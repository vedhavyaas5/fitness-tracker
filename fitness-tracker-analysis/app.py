from flask import Flask, request, redirect, session, jsonify, render_template, flash, url_for
import hashlib
from datetime import datetime
from src.fitness_tracker import db_mongo as db
from src.fitness_tracker.analysis import bmi, bmr_mifflin_st_jeor

app = Flask(__name__)
app.secret_key = "dev-secret"  # replace in production

def hash_password(p: str) -> str:
    return hashlib.sha256(p.encode("utf-8")).hexdigest()

# Initialize database on startup
with app.app_context():
    db.ensure_db()


@app.route("/")
def index():
    return render_template("index.html", user=session.get("user"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        goal = request.form.get("goal", "cut").lower()
        
        # Get weight, height, age, gender, and activity level
        try:
            weight = float(request.form.get("weight_kg"))
            height = float(request.form.get("height_cm"))
            age = int(request.form.get("age"))
        except (ValueError, TypeError):
            return "Invalid weight, height, or age", 400
        
        gender = request.form.get("gender", "").lower()
        activity_level = request.form.get("activity_level", "sedentary").lower()
            
        if not username or not password or goal not in ("bulk", "cut"):
            return "Invalid input", 400
        if gender not in ("male", "female"):
            return "Invalid gender", 400
        if db.get_user_by_username(username):
            return "User exists", 400
            
        # Create user with profile data
        db.create_user(username, hash_password(password), goal, age, gender, activity_level)
        
        # Get the newly created user to add initial body entry
        user = db.get_user_by_username(username)
        if user:
            user_id = user[0]
            
            # Calculate BMI
            computed_bmi = bmi(weight, height)
            
            # Calculate BMR (Basal Metabolic Rate)
            bmr = bmr_mifflin_st_jeor(weight, height, age, gender)
            
            # Calculate maintenance calories based on activity level
            activity_multipliers = {
                "sedentary": 1.2,
                "lightly_active": 1.375,
                "moderately_active": 1.55,
                "very_active": 1.725,
                "extra_active": 1.9
            }
            maintenance_calories = bmr * activity_multipliers.get(activity_level, 1.2) if bmr else None
            
            # Add initial body entry
            today = datetime.now().strftime("%Y-%m-%d")
            db.add_body_entry(user_id, today, weight, height, None, None, "Initial registration")
            
            # Flash success message with BMI and maintenance calories
            bmi_text = f"{computed_bmi:.2f}" if computed_bmi else "n/a"
            cal_text = f"{maintenance_calories:.0f}" if maintenance_calories else "n/a"
            flash(f"Account created! BMI: {bmi_text}, Maintenance Calories: {cal_text} kcal/day")
        
        return redirect("/login")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        u = db.get_user_by_username(username)
        if not u:
            return "No such user", 404
        # Supports tuple: (id, username, goal, pw_hash, role)
        if len(u) == 5:
            user_id, uname, goal, pw_hash, role = u
        else:
            user_id, uname, goal, pw_hash = u
            role = "user"
        if hash_password(password) != pw_hash:
            return "Wrong password", 403
        session["user"] = {"id": str(user_id), "username": uname, "goal": goal, "role": role}
        # Route admins to admin dashboard by default
        if role == "admin":
            return redirect("/admin")
        return redirect("/dashboard")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")

@app.route("/dashboard")
def dashboard():
    user = session.get("user")
    if not user:
        return redirect("/login")
    
    # Get user profile with age, gender, activity level
    profile = db.get_user_profile(user["id"])
    
    # Get body entries and workouts
    entries = db.list_body_entries(user["id"], limit=5)
    workouts = db.list_workouts(user["id"], limit=5)
    
    # Calculate maintenance calories
    maintenance_calories = None
    if profile and len(profile) >= 6:
        user_id, username, goal, age, gender, activity_level = profile
        
        # Get latest body entry for weight and height
        if entries and len(entries) > 0:
            latest_entry = entries[0]
            weight = latest_entry[1]  # weight_kg
            height = latest_entry[2]  # height_cm
            
            if age and gender and weight and height:
                # Calculate BMR
                bmr = bmr_mifflin_st_jeor(weight, height, age, gender)
                
                # Calculate maintenance calories based on activity level
                activity_multipliers = {
                    "sedentary": 1.2,
                    "lightly_active": 1.375,
                    "moderately_active": 1.55,
                    "very_active": 1.725,
                    "extra_active": 1.9
                }
                if bmr:
                    maintenance_calories = round(bmr * activity_multipliers.get(activity_level, 1.2))
    
    # Get today's calories
    today = datetime.now().strftime("%Y-%m-%d")
    calories_burned_today = db.get_calories_burned_today(user["id"], today)
    calories_consumed_today = db.get_calories_consumed_today(user["id"], today)
    
    return render_template(
        "dashboard.html", 
        user=user, 
        recent_body_entries=entries, 
        recent_workouts=workouts,
        maintenance_calories=maintenance_calories,
        calories_burned_today=calories_burned_today,
        calories_consumed_today=calories_consumed_today
    )

@app.route("/body", methods=["POST"]) 
def add_body():
    user = session.get("user")
    if not user:
        return redirect("/login")
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form.to_dict()
    date = (data.get("date") or datetime.now().strftime("%Y-%m-%d")).strip()
    try:
        weight = float(data.get("weight_kg"))
        height = float(data.get("height_cm"))
    except Exception:
        if request.is_json:
            return {"ok": False, "error": "Invalid numeric inputs"}, 400
        flash("Invalid numeric inputs for body entry")
        return redirect(url_for("dashboard"))
    bodyfat = None
    if data.get("bodyfat_pct") not in (None, ""):
        try:
            bodyfat = float(data.get("bodyfat_pct"))
        except Exception:
            bodyfat = None
    water = None
    if data.get("water_l") not in (None, ""):
        try:
            water = float(data.get("water_l"))
        except Exception:
            water = None
    notes = (data.get("notes") or None)
    db.add_body_entry(user["id"], date, weight, height, bodyfat, water, notes)
    computed_bmi = bmi(weight, height)
    if request.is_json:
        return {"ok": True, "bmi": computed_bmi}
    flash(f"Body entry saved. BMI: {computed_bmi if computed_bmi is not None else 'n/a'}")
    return redirect(url_for("dashboard"))

@app.route("/workout", methods=["POST"]) 
def add_workout():
    user = session.get("user")
    if not user:
        return redirect("/login")
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form.to_dict()
    date = (data.get("date") or datetime.now().strftime("%Y-%m-%d")).strip()
    wtype = (data.get("workout_type") or "other").strip()
    try:
        duration = int(data.get("duration_min", 0) or 0)
    except Exception:
        duration = 0
    try:
        calories = float(data.get("calories_burned")) if data.get("calories_burned") not in (None, "") else duration * 6.0
    except Exception:
        calories = duration * 6.0
    notes = (data.get("notes") or None)
    db.add_workout(user["id"], date, wtype, duration, calories, notes)
    if request.is_json:
        return {"ok": True}
    flash("Workout saved.")
    return redirect(url_for("dashboard"))

@app.route("/workout/log")
def log_workout_page():
    user = session.get("user")
    if not user:
        return redirect("/login")
    today = datetime.now().strftime("%Y-%m-%d")
    return render_template("log_workout.html", user=user, today=today)

@app.route("/body/log")
def log_body_page_view():
    user = session.get("user")
    if not user:
        return redirect("/login")
    today = datetime.now().strftime("%Y-%m-%d")
    return render_template("log_body.html", user=user, today=today)

@app.route("/food/log")
def log_food_page():
    user = session.get("user")
    if not user:
        return redirect("/login")
    
    # Get user profile with age, gender, activity level
    profile = db.get_user_profile(user["id"])
    
    # Get body entries for weight and height
    entries = db.list_body_entries(user["id"], limit=1)
    
    # Calculate maintenance calories
    maintenance_calories = None
    if profile and len(profile) >= 6:
        user_id, username, goal, age, gender, activity_level = profile
        
        # Get latest body entry for weight and height
        if entries and len(entries) > 0:
            latest_entry = entries[0]
            weight = latest_entry[1]  # weight_kg
            height = latest_entry[2]  # height_cm
            
            if age and gender and weight and height:
                # Calculate BMR
                bmr = bmr_mifflin_st_jeor(weight, height, age, gender)
                
                # Calculate maintenance calories based on activity level
                activity_multipliers = {
                    "sedentary": 1.2,
                    "lightly_active": 1.375,
                    "moderately_active": 1.55,
                    "very_active": 1.725,
                    "extra_active": 1.9
                }
                if bmr:
                    maintenance_calories = round(bmr * activity_multipliers.get(activity_level, 1.2))
    
    today = datetime.now().strftime("%Y-%m-%d")
    return render_template("log_food.html", user=user, maintenance_calories=maintenance_calories, today=today)

@app.route("/food/add", methods=["POST"])
def add_food_entry():
    user = session.get("user")
    if not user:
        return redirect("/login")
    
    food_id = request.form.get("food_id")
    quantity = request.form.get("quantity")
    date = request.form.get("date") or datetime.now().strftime("%Y-%m-%d")
    notes = request.form.get("notes") or None
    
    # Validate inputs
    if not food_id or not quantity:
        flash("Please select a food and enter a quantity")
        return redirect(url_for("log_food_page"))
    
    try:
        quantity = float(quantity)
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
    except (ValueError, TypeError):
        flash("Invalid quantity. Please enter a positive number.")
        return redirect(url_for("log_food_page"))
    
    # Check if this is a manual food entry (starts with "manual_")
    if food_id.startswith("manual_"):
        # Get manual food details from POST
        manual_food_name = request.form.get("manual_food_name")
        manual_calories = request.form.get("manual_calories_per_unit")
        manual_unit = request.form.get("manual_unit", "grams")
        manual_protein = request.form.get("manual_protein") or 0
        manual_carbs = request.form.get("manual_carbs") or 0
        manual_fat = request.form.get("manual_fat") or 0
        
        try:
            manual_calories = float(manual_calories)
            manual_protein = float(manual_protein) or 0
            manual_carbs = float(manual_carbs) or 0
            manual_fat = float(manual_fat) or 0
        except (ValueError, TypeError):
            flash("Invalid manual food details")
            return redirect(url_for("log_food_page"))
        
        # Check if food already exists, if not add it
        food = db.get_food_by_name(manual_food_name)
        if not food:
            db.add_food(manual_food_name, manual_calories, manual_unit, manual_protein, manual_carbs, manual_fat)
            food = db.get_food_by_name(manual_food_name)
        if not food:
            flash("Error saving manual food")
            return redirect(url_for("log_food_page"))
        calories_consumed = manual_calories * quantity
        db.add_food_entry(user["id"], date, food[0], quantity, calories_consumed, notes)
        flash(f"✓ Food logged: {manual_food_name} ({quantity} {manual_unit}) - {calories_consumed:.0f} kcal")
    else:
        # Get food by ID (handles string ObjectId)
        food = db.get_food_by_id(food_id)
        if not food:
            flash("Food not found. Please select a valid food.")
            return redirect(url_for("log_food_page"))
        
        try:
            # Calculate calories: calories_per_unit * quantity
            calories_consumed = float(food[2]) * quantity  # food[2] is calories_per_unit
            
            db.add_food_entry(user["id"], date, food_id, quantity, calories_consumed, notes)
            flash(f"✓ Food logged: {food[1]} ({quantity} {food[3]}) - {calories_consumed:.0f} kcal")
        except Exception as e:
            flash(f"Error logging food: {str(e)}")
            return redirect(url_for("log_food_page"))
    
    return redirect(url_for("log_food_page"))

@app.route("/api/food-entries/<entry_id>", methods=["DELETE"])
def delete_food_entry_api(entry_id):
    """API endpoint to delete a food entry"""
    user = session.get("user")
    if not user:
        return {"error": "Not authenticated"}, 401
    
    try:
        db.delete_food_entry(entry_id)
        return {"ok": True, "message": "Food entry deleted"}
    except Exception as e:
        return {"ok": False, "error": str(e)}, 400

@app.route("/api/foods")
def api_foods():
    """API endpoint to get all foods as JSON"""
    foods = db.get_all_foods()
    return jsonify([{
        "id": str(f[0]),
        "name": f[1],
        "calories_per_unit": f[2],
        "unit": f[3],
        "protein_g": f[4],
        "carbs_g": f[5],
        "fat_g": f[6]
    } for f in foods])

@app.route("/api/food-entries")
def api_food_entries():
    """API endpoint to get food entries for a specific date"""
    user = session.get("user")
    if not user:
        return {"error": "Not authenticated"}, 401
    
    date = request.args.get("date") or datetime.now().strftime("%Y-%m-%d")
    entries = db.get_food_entries_by_date(user["id"], date)
    
    return jsonify([{
        "entry_id": str(e[0]),
        "date": e[1],
        "food_name": e[2],
        "quantity": e[3],
        "unit": e[4],
        "calories_consumed": e[5],
        "notes": e[6]
    } for e in entries])

# ---------------------- Suggestions API ----------------------
@app.route("/suggestions")
def get_suggestions():
    user = session.get("user")
    if not user:
        return {"suggestions": []}
    items = db.list_suggestions(user["id"], limit=20)
    return jsonify({"suggestions": [f"{t}" for (t, _a, _c) in items]})


@app.route("/schedules")
def get_schedules():
    user = session.get("user")
    if not user:
        return {"schedules": []}
    items = db.list_schedules(user["id"])
    return jsonify({"schedules": [{"date": d, "title": t, "notes": n} for (d, t, n) in items]})

# ---------------------- Admin routes -------------------------


def require_admin():
    u = session.get("user")
    return bool(u and u.get("role") == "admin")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        u = db.get_user_by_username(username)
        if not u:
            return "No such user", 404
        if len(u) == 5:
            user_id, uname, goal, pw_hash, role = u
        else:
            return "Not an admin", 403
        if role != "admin":
            return "Not an admin", 403
        if hash_password(password) != pw_hash:
            return "Wrong password", 403
        session["user"] = {"id": str(user_id), "username": uname, "goal": goal, "role": role}
        return redirect("/admin")
    return render_template("admin_login.html")


@app.route("/admin")
def admin_dashboard():
    if not require_admin():
        return redirect("/admin/login")
    today = datetime.now().strftime("%Y-%m-%d")
    users = db.list_users()
    # Build summaries for each user
    summaries = []
    for u in users:
        uid, uname, goal, age, gender, activity_level, role, created_at = u
        burned = db.get_calories_burned_today(uid, today)
        consumed = db.get_calories_consumed_today(uid, today)
        entries = db.list_body_entries(uid, limit=1)
        weight = entries[0][1] if entries else None
        height = entries[0][2] if entries else None
        summaries.append({
            "id": str(uid),
            "username": uname,
            "role": role,
            "goal": goal,
            "age": age,
            "gender": gender,
            "activity_level": activity_level,
            "burned": burned,
            "consumed": consumed,
            "weight": weight,
            "height": height,
        })
    return render_template("admin_dashboard.html", user=session.get("user"), summaries=summaries, today=today)


@app.route("/admin/user/update", methods=["POST"])
def admin_update_user():
    if not require_admin():
        return {"ok": False, "error": "forbidden"}, 403
    user_id = request.form.get("user_id")
    goal = request.form.get("goal")
    activity_level = request.form.get("activity_level")
    db.update_user_goal_activity(user_id, goal=goal, activity_level=activity_level)
    flash("User profile updated")
    return redirect("/admin")


@app.route("/admin/suggest", methods=["POST"])
def admin_suggest():
    if not require_admin():
        return {"ok": False, "error": "forbidden"}, 403
    user_id = request.form.get("user_id")
    text = request.form.get("text")
    if user_id and text:
        db.add_suggestion(user_id, text, author=session["user"]["username"])
        flash("Suggestion sent")
    return redirect("/admin")


@app.route("/admin/schedule", methods=["POST"])
def admin_schedule():
    if not require_admin():
        return {"ok": False, "error": "forbidden"}, 403
    user_id = request.form.get("user_id")
    date = request.form.get("date") or datetime.now().strftime("%Y-%m-%d")
    title = request.form.get("title")
    notes = request.form.get("notes") or None
    if user_id and title:
        db.add_schedule(user_id, date=date, title=title, notes=notes)
        flash("Schedule created")
    return redirect("/admin")


@app.route("/admin/assign-workout", methods=["POST"])
def admin_assign_workout():
    if not require_admin():
        return {"ok": False, "error": "forbidden"}, 403
    
    user_id = request.form.get("user_id")
    date = request.form.get("date") or datetime.now().strftime("%Y-%m-%d")
    plan_name = request.form.get("plan_name")
    notes = request.form.get("notes") or None
    
    # Get exercises, sets, and reps arrays
    exercises = request.form.getlist("exercises[]")
    sets = request.form.getlist("sets[]")
    reps = request.form.getlist("reps[]")
    
    if not user_id or not plan_name or not exercises:
        flash("Please provide all required fields")
        return redirect("/admin")
    
    # Build workout plan details
    workout_details = []
    for i, exercise in enumerate(exercises):
        if exercise and i < len(sets) and i < len(reps):
            workout_details.append({
                "exercise": exercise,
                "sets": sets[i],
                "reps": reps[i]
            })
    
    # Format the workout plan into a readable string
    workout_text = f"Workout Plan: {plan_name}\n\n"
    for detail in workout_details:
        workout_text += f"• {detail['exercise']}: {detail['sets']} sets × {detail['reps']} reps\n"
    
    if notes:
        workout_text += f"\nNotes: {notes}"
    
    # Add as a schedule entry
    db.add_schedule(user_id, date=date, title=plan_name, notes=workout_text)
    
    flash(f"Workout plan '{plan_name}' assigned successfully")
    return redirect("/admin")


if __name__ == "__main__":
    app.run(debug=True)
