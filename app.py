from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    send_from_directory
)
import os
from cs50 import SQL
from werkzeug.security import generate_password_hash, check_password_hash
import re
from datetime import datetime, timedelta
from functools import wraps
from ai_caller import call
import json
import os
import subprocess
import time
from urllib.parse import urlparse
import traceback

# Ensure login_required is defined before any route uses it
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login to access this page", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = "qwertyuiopasdfghjklzxcvbnm"  # In production, use a secure random key
# Configure logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
with open ("diet_coach_prompt.txt", "r") as f:
    DIET_COACH_SYSTEM_PROMPT = f.read()
# Initialize CS50 SQL database
db = SQL("sqlite:///health.db")

# Initialize Database Tables
def init_db():
    # Weekly Workout Plans table
    db.execute("""
        CREATE TABLE IF NOT EXISTS weekly_workout_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            week_start_date DATE NOT NULL,
            plan_data TEXT NOT NULL,
            completed_items TEXT DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    # Users table
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # BMI Records table
    db.execute("""
        CREATE TABLE IF NOT EXISTS bmi_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            weight REAL NOT NULL,
            height REAL NOT NULL,
            bmi REAL NOT NULL,
            category TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # Chat Messages table
    db.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            response TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # User Preferences table
    db.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            dietary_preferences TEXT DEFAULT '',
            allergies TEXT DEFAULT '',
            goals TEXT DEFAULT 'maintenance',
            target_weight REAL,
            gender TEXT DEFAULT '',
            age INTEGER,
            activity_level TEXT DEFAULT '',
            previous_history TEXT DEFAULT '',
            prefered_cuisine TEXT DEFAULT '',
            meal_frequency TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # Weekly Diet Plaminutesns table
    db.execute("""
        CREATE TABLE IF NOT EXISTS weekly_diet_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            week_start_date DATE NOT NULL,
            plan_data TEXT NOT NULL,
            completed_items TEXT DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    db.execute("""
    CREATE TABLE IF NOT EXISTS user_connections (
        user_id INTEGER NOT NULL,
        friend_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (friend_id) REFERENCES users (id),
        UNIQUE(user_id, friend_id),
        CHECK(status IN ('pending', 'accepted', 'rejected'))
    )
    """)

# --- AI Workout Plan Generation ---
with open ("workout_coach_prompt.txt", "r") as f:
    WORKOUT_COACH_SYSTEM_PROMPT = f.read()

def generate_weekly_workout_plan_ai(user_id: int):
    # Gather user profile
    prefs = db.execute("""
        SELECT gender, age, activity_level, previous_history, goals
        FROM user_preferences
        WHERE user_id = ?
        ORDER BY created_at DESC LIMIT 1
    """, user_id)
    latest_bmi = db.execute("""
        SELECT bmi, category FROM bmi_records
        WHERE user_id = ?
        ORDER BY created_at DESC LIMIT 1
    """, user_id)
    gender = prefs[0]["gender"] if prefs else ""
    age = prefs[0]["age"] if prefs else None
    activity_level = prefs[0]["activity_level"] if prefs else ""
    previous_history = prefs[0]["previous_history"] if prefs else ""
    goals = prefs[0]["goals"] if prefs else "general_fitness"
    bmi = latest_bmi[0]["bmi"] if latest_bmi else None
    bmi_category = latest_bmi[0]["category"] if latest_bmi else ""

    # Compose AI prompt for call()
    user_info = json.dumps({
        "gender": gender,
        "age": age,
        "activity_level": activity_level,
        "previous_history": previous_history,
        "goals": goals,
        "bmi": bmi,
        "bmi_category": bmi_category
    })
    ai_response = call(
        sys_prompt=WORKOUT_COACH_SYSTEM_PROMPT,
        history=previous_history,
        message=user_info
    )
    plan = extract_json_strict(ai_response)
    if not plan or "week" not in plan:
        raise ValueError("Workout AI returned invalid JSON plan")
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())
    db.execute(
        """
        INSERT INTO weekly_workout_plans (user_id, week_start_date, plan_data, completed_items)
        VALUES (?, ?, ?, ?)
        """,
        user_id, start_of_week.date(), json.dumps(plan, ensure_ascii=False), json.dumps({})
    )
    return plan
# --- Workout Plan Routes ---
@app.route("/workout_plan")
@login_required
def workout_plan():
    existing_plan = db.execute("""
        SELECT * FROM weekly_workout_plans
        WHERE user_id = ? AND week_start_date >= date('now', '-7 days')
        ORDER BY created_at DESC LIMIT 1
    """, session["user_id"])
    if existing_plan:
        plan_data = json.loads(existing_plan[0]["plan_data"])
        completed_items = json.loads(existing_plan[0]["completed_items"] or "{}")
        plan_id = existing_plan[0]["id"]
    else:
        plan_data = None
        completed_items = {}
        plan_id = None
    return render_template("workout_plan.html",
                           plan_data=plan_data,
                           completed_items=completed_items,
                           plan_id=plan_id)

@app.route("/generate_new_workout_plan", methods=["POST"])
@login_required
def generate_new_workout_plan():
    try:
        plan = generate_weekly_workout_plan_ai(session["user_id"])
        if plan is None:
            flash("No profile found. Please fill your preferences first.", "warning")
        else:
            flash("New AI workout plan generated!", "success")
    except Exception as e:
        app.logger.error(f"AI workout plan error: {e}")
        flash("Failed to generate AI workout plan. Please try again.", "danger")
    return redirect(url_for("workout_plan"))

# Helper Functions
def calculate_bmi(weight, height):
    height_m = height / 100
    return round(weight / (height_m**2), 1)
def get_bmi_category(bmi):
    if bmi < 18.5:
        return {
            "category": "underweight",
            "name": "Underweight",
            "color": "#3a86ff",
            "tip": """<strong>Underweight Advice:</strong><br>
                    • Increase calorie intake with nutrient-dense foods<br>
                    • Include protein-rich foods like eggs, chicken, beans<br>
                    • Consider strength training 3x/week<br>
                    • 🍳🥩💪""",
        }
    elif bmi < 24.9:
        return {
            "category": "normal",
            "name": "Normal",
            "color": "#06d6a0",
            "tip": """<strong>Healthy Weight Tips:</strong><br>
                    • Maintain balanced diet (fruits, veggies, whole grains)<br>
                    • 150+ mins exercise weekly<br>
                    • Stay hydrated (8 glasses/day)<br>
                    • 🥗🏃‍♂️💧""",
        }
    elif bmi < 29.9:
        return {
            "category": "overweight",
            "name": "Overweight",
            "color": "#ffd166",
            "tip": """<strong>Overweight Advice:</strong><br>
                    • Aim for 1-2 lbs weight loss/week<br>
                    • Increase physical activity (walking, cycling)<br>
                    • Reduce sugary drinks and snacks<br>
                    • 🚶‍♀️🚫🍰""",
        }
    else:
        return {
            "category": "obese",
            "name": "Obese",
            "color": "#ef476f",
            "tip": """<strong>Obesity Advice:</strong><br>
                    • Consult healthcare professional<br>
                    • Focus on sustainable lifestyle changes<br>
                    • Join support groups for motivation<br>
                    • 👨‍⚕️🤝💚""",
        }
def clean_ai_response(response):
    response = re.sub(r"[★☆*]+", "", response)
    response = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", response)
    response = response.replace("\n- ", "<br>• ")
    response = response.replace("\n", "<br>")
    return response
def check_ollama_service():
    # Ollama service is no longer used for AI responses
    return True, "AI service is now handled by OpenRouter via ai_caller.py."
def generate_chat_response(user_message, user_id):
    try:
        # Get latest BMI record
        bmi = db.execute("""
            SELECT bmi, category FROM bmi_records
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, user_id)

        bmi_context = ""
        if bmi:
            bmi_context = f"The user's BMI history is {bmi[0]['bmi']} ({bmi[0]['category'].lower()})."

        system_prompt = (
            f"You are Kinetic Edge, an AI health assistant specializing in nutrition, fitness, and weight management."
            f"The user prefers to be called as {session['username']}, unless stated otherwise in the chat. Treat it as a nickname and don't take it repeatedly."
            f"{bmi_context}Provide science-based, practical advice. Be encouraging and empathetic. Think and answer logically and not emotionally, while still showing empathy towards user, like an actual health coach."
            "Keep responses concise and in the range of 2-3 sentences/ within 25-50 words except if longer responses are absolutely necessary."
            "Keep your tone professional, like a true coach."
        )

        # Get previous messages
        previous_messages = db.execute("""
            SELECT message, response FROM chat_messages
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 10
        """, user_id)

        messages = [{"role": "system", "content": system_prompt}]
        for msg in reversed(previous_messages):
            messages.append({"role": "user", "content": clean_ai_response(msg["message"])})
            messages.append({"role": "assistant", "content": clean_ai_response(msg["response"])})
        messages.append({"role": "user", "content": user_message})

        # Use the call function from ai_caller.py
        # Prepare history string from previous messages
        history_str = "\n".join([
            f"User: {clean_ai_response(msg['message'])}\nAI: {clean_ai_response(msg['response'])}"
            for msg in reversed(previous_messages)
        ])
        ai_response = call(
            sys_prompt=system_prompt,
            history=history_str,
            message=user_message
        )
        return clean_ai_response(ai_response)
    except Exception as e:
        app.logger.error(f"Error generating chat response: {str(e)}")
        return "Sorry, I'm having trouble processing your request right now."
def _port_from_host_url(host_url: str) -> int:
    u = urlparse(host_url)
    if u.port:
        return u.port
    try:
        return int(host_url.split(":")[-1])
    except Exception:
        return 11435
def _try_connect_diet_client():
    # No longer needed for OpenRouter
    return True
def _start_diet_sidecar_if_needed():
    _try_connect_diet_client()
def _spawn_sidecar_server():
    port = _port_from_host_url(app.config["DIET_OLLAMA_HOST"])
    env = os.environ.copy()
    env["OLLAMA_HOST"] = f"127.0.0.1:{port}"
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        time.sleep(2.0)
        _try_connect_diet_client()
        return True
    except Exception as e:
        app.logger.error(f"Failed to spawn diet Ollama sidecar: {e}")
        return False
_start_diet_sidecar_if_needed()
JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)
def extract_json_strict(text: str):
    if not text:
        return None
    cleaned = text.strip()
    cleaned = cleaned.replace("``````", "")
    m = JSON_BLOCK_RE.search(cleaned)
    if not m:
        return None
    block = m.group(0)
    return json.loads(block)
def calorie_hint(bmi_category: str, goals: str) -> str:
    cat = (bmi_category or "").lower()
    goal = (goals or "maintenance").lower()

    if goal == "weight_gain":
        return "2400-3000 kcal/day" if cat in ["underweight", "normal"] else "2200-2600 kcal/day"
    if goal == "muscle_gain":
        return "2200-2800 kcal/day" if cat in ["normal", "overweight"] else "2000-2400 kcal/day"
    if goal == "weight_loss":
        return "1200-1800 kcal/day" if cat in ["overweight", "obese"] else "1500-1900 kcal/day"
    return "1800-2300 kcal/day" if cat in ["normal", "overweight"] else "2000-2400 kcal/day"
def generate_weekly_diet_plan_ai(user_id: int):
    latest_bmi = db.execute("""
        SELECT weight, height, bmi, category, created_at
        FROM bmi_records
        WHERE user_id = ?
        ORDER BY created_at DESC LIMIT 1
    """, user_id)
    if not latest_bmi:
        return None
    bmi_val = latest_bmi[0]["bmi"]
    bmi_cat = latest_bmi[0]["category"]

    prefs = db.execute("""
        SELECT dietary_preferences, allergies, goals, target_weight, gender, age, activity_level, previous_history, meal_frequency, prefered_cuisine
        FROM user_preferences
        WHERE user_id = ?
        ORDER BY created_at DESC LIMIT 1
    """, user_id)
    dietary_preferences = prefs[0]["dietary_preferences"] if prefs else ""
    allergies = prefs[0]["allergies"] if prefs else ""
    goals = prefs[0]["goals"] if prefs else "maintenance"
    target_weight = prefs[0]["target_weight"] if prefs else None
    gender = prefs[0]["gender"] if prefs else ""
    age = prefs[0]["age"] if prefs else None
    activity_level = prefs[0]["activity_level"] if prefs else ""
    previous_history = prefs[0]["previous_history"] if prefs else ""
    meal_freq = prefs[0]["meal_frequency"] if prefs else ""
    cuisine = prefs[0]["prefered_cuisine"] if prefs else ""

    calorie_range = calorie_hint(bmi_cat, goals)

    # Compose AI prompt for call()
    user_info = json.dumps({
        "bmi": bmi_val,
        "bmi_category": bmi_cat,
        "goals": goals,
        "target_weight": target_weight,
        "dietary_preferences": dietary_preferences,
        "allergies": allergies,
        "gender": gender,
        "age": age,
        "activity_level": activity_level,
        "previous_history": previous_history,
        "calorie_range_hint": calorie_range,
        "meal_frequency": meal_freq,
        "cuisine": cuisine
    })
    ai_response = call(
        sys_prompt=DIET_COACH_SYSTEM_PROMPT,
        history=previous_history,
        message=user_info
    )
    plan = extract_json_strict(ai_response)
    if not plan or "week" not in plan:
        raise ValueError("Diet AI returned invalid JSON plan")
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())
    db.execute(
        """
        INSERT INTO weekly_diet_plans (user_id, week_start_date, plan_data, completed_items)
        VALUES (?, ?, ?, ?)
        """,
        user_id, start_of_week.date(), json.dumps(plan, ensure_ascii=False), json.dumps({})
    )
    return plan
def get_bmi_chart_data(user_id):
    records = db.execute("""
        SELECT bmi, weight, height, created_at FROM bmi_records
        WHERE user_id = ?
        ORDER BY created_at ASC
    """, user_id)

    chart_data = {
        "dates": [],
        "bmi_values": [],
        "weights": [],
        "heights": []
    }

    for record in records:
        if isinstance(record["created_at"], str):
            date_obj = datetime.strptime(record["created_at"], '%Y-%m-%d %H:%M:%S')
        else:
            date_obj = record["created_at"]

        chart_data["dates"].append(date_obj.strftime('%m/%d'))
        chart_data["bmi_values"].append(record["bmi"])
        chart_data["weights"].append(record["weight"])
        chart_data["heights"].append(record["height"])

    return chart_data
## login_required decorator is already defined above all usages, so remove this duplicate
# Routes
@app.route("/")
def home():
    return redirect(url_for("login"))
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if not username or not password:
            flash("Please enter both username and password", "danger")
            return redirect(url_for("login"))
        user = db.execute("SELECT * FROM users WHERE username = ?", username)
        if user and check_password_hash(user[0]["password"], password):
            session["user_id"] = user[0]["id"]
            session["username"] = user[0]["username"]
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password", "danger")
    return render_template("login.html")
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        if not username or not password or not confirm_password:
            flash("Please fill all fields", "danger")
            return redirect(url_for("signup"))
        if password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect(url_for("signup"))
        if len(password) < 8:
            flash("Password must be at least 8 characters", "danger")
            return redirect(url_for("signup"))
        if len(username) < 3:
            flash("Username must be at least 3 characters", "danger")
            return redirect(url_for("signup"))
        if not re.match(r"^[a-zA-Z0-9_]+$", username):
            flash("Username can only contain letters, numbers, and underscores", "danger")
            return redirect(url_for("signup"))
        existing_user = db.execute("SELECT id FROM users WHERE username = ?", username)
        if existing_user:
            flash("Username already taken", "danger")
            return redirect(url_for("signup"))
        hashed_password = generate_password_hash(password)
        db.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            username, hashed_password
        )
        flash("Account created successfully! Please login.", "success")
        return redirect(url_for("login"))
    return render_template("signup.html")
@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for("login"))
@app.route("/dashboard")
@login_required
def dashboard():
    latest_bmi = db.execute("""
        SELECT * FROM bmi_records
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, session["user_id"])
    if latest_bmi:
        latest_record = latest_bmi[0]
        if 'created_at' in latest_record and isinstance(latest_record['created_at'], str):
            try:
                latest_record['created_at'] = datetime.strptime(latest_record['created_at'], '%Y-%m-%d %H:%M:%S')
            except ValueError:
                app.logger.error("Failed to parse created_at in dashboard")
    else:
        latest_record = None
    return render_template("dashboard.html", latest_bmi=latest_record)
@app.route("/calculator", methods=["GET", "POST"])
@login_required
def calculator():
    records = db.execute("""
        SELECT * FROM bmi_records
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, session["user_id"])

    for record in records:
        if 'created_at' in record and isinstance(record['created_at'], str):
            try:
                record['created_at'] = datetime.strptime(record['created_at'], '%Y-%m-%d %H:%M:%S')
            except ValueError:
                app.logger.error("Failed to parse created_at in calculator")

    if request.method == "POST":
        try:
            weight = float(request.form.get("weight", 0))
            height = float(request.form.get("height", 0))
            if weight <= 0 or height <= 0:
                flash("Weight and height must be positive values", "danger")
                return redirect(url_for("calculator"))
            bmi = calculate_bmi(weight, height)
            category_data = get_bmi_category(bmi)
            db.execute("""
                INSERT INTO bmi_records (user_id, weight, height, bmi, category)
                VALUES (?, ?, ?, ?, ?)
            """, session["user_id"], weight, height, bmi, category_data["name"])
            flash("BMI calculation saved!", "success")
            return redirect(url_for("calculator"))
        except ValueError:
            flash("Please enter valid numbers for weight and height", "danger")
        except Exception as e:
            app.logger.error(f"Error saving BMI record: {str(e)}")
            flash("An error occurred while saving your BMI data", "danger")
    return render_template("calculator.html", records=records)
@app.route("/chat")
@login_required
def chat():
    messages = db.execute("""
        SELECT * FROM chat_messages
        WHERE user_id = ?
        ORDER BY created_at ASC
    """, session["user_id"])

    for message in messages:
        if 'created_at' in message and isinstance(message['created_at'], str):
            try:
                message['created_at'] = datetime.strptime(message['created_at'], '%Y-%m-%d %H:%M:%S')
                message['message'] = clean_ai_response(message['message'])
            except ValueError:
                app.logger.error("Failed to parse created_at in chat")
    return render_template("chat.html", messages=messages)
@app.route("/send_message", methods=["POST"])
@login_required
def send_message():
    user_id = session["user_id"]
    message = request.form.get("message", "").strip()
    if not message:
        return jsonify({"error": "Message cannot be empty"}), 400
    try:
        response = generate_chat_response(message, user_id)
        db.execute("""
            INSERT INTO chat_messages (user_id, message, response)
            VALUES (?, ?, ?)
        """, user_id, message, response)
        return jsonify(
            {
                "message": message,
                "response": response,
                "timestamp": datetime.now().strftime("%H:%M"),
            }
        )
    except Exception as e:
        app.logger.error(f"Error processing message: {str(e)}")
        return jsonify({"error": "Failed to process message"}), 500

@app.route("/generate_new_plan", methods=["POST"])
@login_required
def generate_new_plan():
    try:
        plan = generate_weekly_diet_plan_ai(session["user_id"])
        if plan is None:
            flash("No BMI found. Calculate BMI first.", "warning")
        else:
            flash("New AI meal plan generated!", "success")
    except Exception as e:
        app.logger.error(f"AI meal plan error: {e}")
        flash("Failed to generate AI meal plan. Please try again.", "danger")
    return redirect(url_for("meal_plan"))
@app.route("/meal_plan")
@login_required
def meal_plan():
    existing_plan = db.execute("""
        SELECT * FROM weekly_diet_plans
        WHERE user_id = ? AND week_start_date >= date('now', '-7 days')
        ORDER BY created_at DESC LIMIT 1
    """, session["user_id"])

    if existing_plan:
        plan_data = json.loads(existing_plan[0]["plan_data"])
        completed_items = json.loads(existing_plan[0]["completed_items"] or "{}")
        plan_id = existing_plan[0]["id"]
    else:
        plan_data = None
        completed_items = {}
        plan_id = None

    return render_template("meal_plan.html",
                           plan_data=plan_data,
                           completed_items=completed_items,
                           plan_id=plan_id)
@app.route("/preferences", methods=["GET", "POST"])
@login_required
def preferences():
    if request.method == "POST":
        try:
            # Verify user is logged in
            if "user_id" not in session:
                flash("Please log in to update preferences", "danger")
                return redirect(url_for("login"))
            # Get form data with validation
            dietary_preferences = request.form.get("dietary_preferences", "").strip()
            allergies = request.form.get("allergies", "").strip()
            goals = request.form.get("goals", "maintenance").strip()
            target_weight = request.form.get("target_weight", "").strip()
            gender = request.form.get("gender", "").strip()
            age = request.form.get("age", "").strip()
            activity_level = request.form.get("activity_level", "").strip()
            previous_history = request.form.get("previous_history", "").strip()
            meal_freq = request.form.get("meal_frequency", "").strip()
            prefered_cuisine = request.form.get("prefered_cuisine", "").strip()

            app.logger.info(f"Processing preferences update for user {session['user_id']}")
            app.logger.info(f"Form data: diet={dietary_preferences}, allergies={allergies}, goals={goals}, weight={target_weight}, gender={gender}, age={age}, activity={activity_level}, history={previous_history}, meal_frequency = {meal_freq}, cuisine={prefered_cuisine}")

            # Process target_weight
            target_weight_float = None
            if target_weight:
                try:
                    target_weight_clean = target_weight.replace(',', '').strip()
                    if target_weight_clean:
                        target_weight_float = float(target_weight_clean)
                        if target_weight_float <= 0 or target_weight_float > 500:
                            flash("Target weight must be a positive number less than 500kg", "danger")
                            return redirect(url_for("preferences"))
                except ValueError as e:
                    app.logger.error(f"Target weight validation error: {str(e)}")
                    flash("Please enter a valid target weight (numbers only)", "danger")
                    return redirect(url_for("preferences"))

            # Validate age
            age_int = None
            if age:
                try:
                    age_int = int(age)
                    if age_int < 0 or age_int > 120:
                        flash("Please enter a valid age (0-120)", "danger")
                        return redirect(url_for("preferences"))
                except ValueError:
                    flash("Please enter a valid age (numbers only)", "danger")
                    return redirect(url_for("preferences"))

            # Validate goals
            valid_goals = ["maintenance", "weight_loss", "weight_gain", "muscle_gain"]
            if goals not in valid_goals:
                goals = "maintenance"

            # Check if user already has preferences
            try:
                existing_prefs = db.execute("""
                    SELECT id FROM user_preferences
                    WHERE user_id = ?
                    ORDER BY created_at DESC LIMIT 1
                """, session["user_id"])
                logger.info(f"Found existing preferences: {existing_prefs}")
            except Exception as e:
                if "no such table" in str(e).lower():
                    # Recreate the table if it doesn't exist
                    logger.info("Preferences table not found, creating it...")
                    db.execute("""
                        CREATE TABLE IF NOT EXISTS user_preferences (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            dietary_preferences TEXT DEFAULT '',
                            allergies TEXT DEFAULT '',
                            goals TEXT DEFAULT 'maintenance',
                            target_weight REAL,
                            prefered_cuisine TEXT DEFAULT '',
                            meal_frequency TEXT DEFAULT '',
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES users (id)
                        )
                    """)
                    existing_prefs = []
                else:
                    raise

            if existing_prefs:
                # Update existing preferences
                try:
                    app.logger.info(f"Updating existing preferences with ID {existing_prefs[0]['id']}")
                    verify = db.execute("SELECT id FROM user_preferences WHERE id = ? AND user_id = ?",
                                      existing_prefs[0]["id"], session["user_id"])
                    if not verify:
                        app.logger.error("Preference record not found during update")
                        flash("Unable to find your preferences. Please try again.", "danger")
                        return redirect(url_for("preferences"))
                    update_params = {
                        "diet": dietary_preferences,
                        "allergies": allergies,
                        "goals": goals,
                        "weight": target_weight_float if target_weight_float is not None else None,
                        "gender": gender,
                        "age": age_int,
                        "activity_level": activity_level,
                        "previous_history": previous_history,
                        "prefered_cuisines": prefered_cuisine,  # Add this line
                        "meal_frequency": meal_freq,
                        "pref_id": existing_prefs[0]["id"],
                        "user_id": session["user_id"]
                    }
                    app.logger.info(f"Executing update with params: {update_params}")
                    update_query = """
                                    UPDATE user_preferences
                                    SET dietary_preferences = :diet,
                                        allergies = :allergies,
                                        goals = :goals,
                                        target_weight = :weight,
                                        gender = :gender,
                                        age = :age,
                                        prefered_cuisine = :prefered_cuisines,
                                        meal_frequency = :meal_frequency,
                                        activity_level = :activity_level,
                                        previous_history = :previous_history,
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE id = :pref_id AND user_id = :user_id
                                """
                    result = db.execute(update_query, **update_params)
                    app.logger.info(f"Update completed successfully")
                    flash("Preferences updated successfully!", "success")
                    return redirect(url_for("preferences"))
                except Exception as e:
                    error_msg = str(e)
                    app.logger.error(f"Database update error: {error_msg}")
                    app.logger.error(traceback.format_exc())
                    if "UNIQUE constraint" in error_msg:
                        flash("These preferences already exist.", "danger")
                    elif "FOREIGN KEY constraint" in error_msg:
                        flash("User session expired. Please log in again.", "danger")
                        return redirect(url_for("login"))
                    else:
                        flash(f"An error occurred while updating your preferences: {error_msg}", "danger")
                    return redirect(url_for("preferences"))
            else:
                # Insert new preferences
                try:
                    app.logger.info("Creating new preferences record")
                    insert_params = {
                        "user_id": session["user_id"],
                        "diet": dietary_preferences,
                        "allergies": allergies,
                        "goals": goals,
                        "weight": target_weight_float if target_weight_float is not None else None,
                        "gender": gender,
                        "age": age_int,
                        "activity_level": activity_level,
                        "previous_history": previous_history,
                        "meal_frequency": meal_freq,
                        "prefered_cuisine": prefered_cuisine
                    }
                    app.logger.info(f"Executing insert with params: {insert_params}")
                    insert_query = """
                        INSERT INTO user_preferences
                        (user_id, dietary_preferences, allergies, goals, target_weight, gender, age, activity_level, previous_history, meal_frequency, prefered_cuisine)
                        VALUES (:user_id, :diet, :allergies, :goals, :weight, :gender, :age, :activity_level, :previous_history, :meal_frequency, :prefered_cuisine)
                    """
                    result = db.execute(insert_query, **insert_params)
                    app.logger.info("Insert completed successfully")
                    flash("Preferences saved successfully!", "success")
                    return redirect(url_for("preferences"))
                except Exception as e:
                    app.logger.error(f"Database insert error: {str(e)}")
                    app.logger.error(traceback.format_exc())
                    flash("An error occurred while saving your preferences. Please try again.", "danger")
                    return redirect(url_for("preferences"))
        except Exception as e:
            app.logger.error(f"Unexpected error in preferences route: {str(e)}")
            app.logger.error(traceback.format_exc())
            flash("An unexpected error occurred. Please try again.", "danger")
            return redirect(url_for("preferences"))

    # Get existing preferences
    try:
        preferences_data = db.execute("""
            SELECT * FROM user_preferences
            WHERE user_id = ?
            ORDER BY updated_at DESC LIMIT 1
        """, session["user_id"])
    except Exception as e:
        app.logger.error(f"Error fetching preferences: {str(e)}")
        app.logger.error(traceback.format_exc())
        flash("An error occurred while loading your preferences.", "danger")
        preferences_data = []

    return render_template("preferences.html",
                         preferences=preferences_data[0] if preferences_data else None)
@app.route("/toggle_meal_item", methods=["POST"])
@login_required
def toggle_meal_item():
    try:
        data = request.json
        plan_id = data.get("plan_id")
        item_key = data.get("item_key")

        if not plan_id or not item_key:
            return jsonify({"success": False, "error": "Missing plan_id or item_key"})

        plan = db.execute("""
            SELECT * FROM weekly_diet_plans WHERE id = ? AND user_id = ?
        """, plan_id, session["user_id"])

        if plan:
            completed_items = json.loads(plan[0]["completed_items"] or "{}")
            completed_items[item_key] = not completed_items.get(item_key, False)

            db.execute("""
                UPDATE weekly_diet_plans
                SET completed_items = ?
                WHERE id = ? AND user_id = ?
            """, json.dumps(completed_items), plan_id, session["user_id"])

            return jsonify({"success": True, "completed": completed_items[item_key]})

        return jsonify({"success": False, "error": "Plan not found"})
    except Exception as e:
        app.logger.error(f"Error toggling meal item: {str(e)}")
        return jsonify({"success": False, "error": "Internal server error"})


# Send a friend request
@app.route("/send_friend_request", methods=["POST"])
@login_required
def send_friend_request():
    data = request.get_json() or request.form
    friend_username = data.get("friend_username")
    user_id = session["user_id"]

    if not friend_username:
        return jsonify({"success": False, "error": "Missing friend's username"}), 400

    # Get friend's user ID
    friend = db.execute("SELECT id FROM users WHERE username = ?", friend_username)
    if not friend:
        return jsonify({"success": False, "error": "User not found"}), 404

    friend_id = friend[0]["id"]
    if friend_id == user_id:
        return jsonify({"success": False, "error": "Cannot send friend request to yourself"}), 400

    # Check if request already exists
    existing = db.execute(
        "SELECT status FROM user_connections WHERE user_id = ? AND friend_id = ?",
        user_id, friend_id
    )

    if existing:
        status = existing[0]["status"]
        if status == "pending":
            return jsonify({"success": False, "error": "Friend request already sent"}), 400
        elif status == "accepted":
            return jsonify({"success": False, "error": "Already friends"}), 400
        elif status == "rejected":
            # Allow sending new request if previously rejected
            db.execute(
                "UPDATE user_connections SET status = 'pending', updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND friend_id = ?",
                user_id, friend_id
            )
    else:
        # Create new friend request
        db.execute(
            "INSERT INTO user_connections (user_id, friend_id, status) VALUES (?, ?, 'pending')",
            user_id, friend_id
        )
    return jsonify({"success": True, "message": "Friend request sent successfully"})

@app.route("/friend_requests", methods=["GET"])
@login_required
def get_friend_requests():
    user_id = session["user_id"]
    pending_requests = db.execute("""
        SELECT u.username, uc.user_id, uc.created_at
        FROM user_connections uc
        JOIN users u ON uc.user_id = u.id
        WHERE uc.friend_id = ? AND uc.status = 'pending'
        ORDER BY uc.created_at DESC
    """, user_id)
    return jsonify({"requests": pending_requests})

@app.route("/handle_friend_request", methods=["POST"])
@login_required
def handle_friend_request():
    data = request.get_json() or request.form
    sender_id = data.get("sender_id")
    action = data.get("action")  # 'accept' or 'reject'
    user_id = session["user_id"]

    if not sender_id or not action or action not in ['accept', 'reject']:
        return jsonify({"success": False, "error": "Invalid request parameters"}), 400

    # Verify request exists and is pending
    request_exists = db.execute("""
        SELECT 1 FROM user_connections
        WHERE user_id = ? AND friend_id = ? AND status = 'pending'
    """, sender_id, user_id)

    if not request_exists:
        return jsonify({"success": False, "error": "Friend request not found"}), 404

    new_status = 'accepted' if action == 'accept' else 'rejected'

    db.execute("""
        UPDATE user_connections
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ? AND friend_id = ?
    """, new_status, sender_id, user_id)

    return jsonify({
        "success": True,
        "message": f"Friend request {action}ed successfully"
    })

#TODO: test this function

# Progress page: show user's and all accepted friends' progress charts
@app.route("/progress", methods=["GET"])
@login_required
def progress():
    user_id = session["user_id"]

    # Get main user data and username
    user_chart_data = get_bmi_chart_data(user_id)
    user_username = db.execute("SELECT username FROM users WHERE id = ?", user_id)[0]["username"]

    # Initialize combined chart data with user's data
    all_chart_data = {
        user_username: user_chart_data
    }

    # Get accepted friends list
    friend_ids = db.execute("""
        SELECT u.id, u.username
        FROM user_connections uc
        JOIN users u ON uc.friend_id = u.id
        WHERE uc.user_id = ? AND uc.status = 'accepted'
        UNION
        SELECT u.id, u.username
        FROM user_connections uc
        JOIN users u ON uc.user_id = u.id
        WHERE uc.friend_id = ? AND uc.status = 'accepted'
    """, user_id, user_id)

    # Get all friends' chart data
    friends = []
    for friend in friend_ids:
        friend_id = friend["id"]
        friend_username = friend["username"]
        friends.append({"id": friend_id, "username": friend_username})
        friend_data = get_bmi_chart_data(friend_id)
        all_chart_data[friend_username] = friend_data

    # Normalize data to the same length
    max_len = 0
    for data in all_chart_data.values():
        if len(data["dates"]) > max_len:
            max_len = len(data["dates"])

    for username, data in all_chart_data.items():
        current_len = len(data["dates"])
        if current_len < max_len:
            if current_len > 0:
                last_date = datetime.strptime(data["dates"][-1], '%m/%d')
                last_bmi = data["bmi_values"][-1]
                last_weight = data["weights"][-1]
                last_height = data["heights"][-1]
            else:
                # If user has no data, use default values
                last_date = datetime.now()
                last_bmi = 0
                last_weight = 0
                last_height = 0

            for i in range(max_len - current_len):
                new_date = last_date + timedelta(days=i+1)
                data["dates"].append(new_date.strftime('%m/%d'))
                data["bmi_values"].append(last_bmi)
                data["weights"].append(last_weight)
                data["heights"].append(last_height)

    return render_template("progress.html",
                           all_chart_data=all_chart_data,
                           user_username=user_username,
                           friends=friends)
@app.route("/check_ollama")
@login_required
def check_ollama():
    is_running, message = check_ollama_service()
    return jsonify({
        "status": "ok" if is_running else "error",
        "message": message
    })

@app.route("/toggle_workout_item", methods=["POST"])
@login_required
def toggle_workout_item():
    try:
        data = request.json
        plan_id = data.get("plan_id")
        item_key = data.get("item_key")

        if not plan_id or not item_key:
            return jsonify({"success": False, "error": "Missing plan_id or item_key"})

        plan = db.execute("""
            SELECT * FROM weekly_workout_plans WHERE id = ? AND user_id = ?
        """, plan_id, session["user_id"])

        if plan:
            completed_items = json.loads(plan[0]["completed_items"] or "{}")
            completed_items[item_key] = not completed_items.get(item_key, False)

            db.execute("""
                UPDATE weekly_workout_plans
                SET completed_items = ?
                WHERE id = ? AND user_id = ?
            """, json.dumps(completed_items), plan_id, session["user_id"])

            return jsonify({"success": True, "completed": completed_items[item_key]})

        return jsonify({"success": False, "error": "Plan not found"})
    except Exception as e:
        app.logger.error(f"Error toggling workout item: {str(e)}")
        return jsonify({"success": False, "error": "Internal server error"})


@app.route('/favicon.ico')
def favicon():
   return send_from_directory(
       os.path.join(app.root_path, 'static'),
       'favicon.ico',
       mimetype='image/vnd.microsoft.icon'
   )

# Error Handlers
@app.errorhandler(404)
def page_not_found(e):
    return "<h1>404 - Page Not Found</h1><p>The requested page does not exist.</p>", 404
@app.errorhandler(403)
def forbidden(e):
    return "<h1>403 - Forbidden</h1><p>You don't have permission to access this page.</p>", 403
@app.errorhandler(500)
def internal_server_error(e):
    return "<h1>500 - Internal Server Error</h1><p>Something went wrong on our end. Please try again later.</p>", 500
# Initialize database and ensure schema is up to date
with app.app_context():
    init_db()
    # Ensure the updated_at column exists for existing databases
    #
if __name__ == "__main__":
    init_db()

    # Check Ollama service before starting the app
    is_running, message = check_ollama_service()
    if not is_running:
        app.logger.error(f"Ollama service issue: {message}")
        print(f"WARNING: {message}")

    app.run(host="127.0.0.1",debug=True, port=5501)
