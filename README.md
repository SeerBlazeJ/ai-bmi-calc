# AI-Powered Health & Fitness Companion

A Flask web application that helps users track their BMI, generate personalized meal and workout plans, and interact with an AI health coach. The application stores user data in a local SQLite database and uses OpenRouter (via `ai_caller.py`) to produce AI-generated plans and chat responses.

## Key features

- User authentication (signup/login/logout) with hashed passwords
- BMI calculator with history and categorized tips
- Persistent user preferences (diet, allergies, goals, activity level, target weight, etc.)
- AI-generated weekly meal plans (stored per-week)
- AI-generated weekly workout plans (stored per-week)
- Chat interface with AI assistant that uses recent chat history and BMI context
- Progress view that shows BMI trends for the user and accepted friends
- Friend request system (send/accept/reject) to share progress
- Toggle-tracking for completed meal/workout items

## Project structure

```
ai-bmi-calc/
├── app.py                # Flask application and routes
├── ai_caller.py          # Lightweight OpenRouter client wrapper used for AI calls
├── health.db             # SQLite database (created at runtime)
├── requirements.txt      # Python dependencies
├── static/               # CSS, favicon, client assets
└── templates/            # Jinja2 HTML templates (login, signup, dashboard, etc.)
```

## Dependencies

Dependencies are listed in `requirements.txt`. Key packages:

- Flask
- requests
- cs50 (lightweight SQLite wrapper used here)
- matplotlib (used for chart rendering)

Install them with:

```bash
pip install -r requirements.txt
```

## AI backend

This project uses OpenRouter (https://openrouter.ai/) via `ai_caller.py` to call hosted models (the default code sets the model to a Llama 3 variant). You must provide an OpenRouter API key via an environment variable named `OPENROUTER_API_KEY` (see notes below). The app prepares system prompts from `diet_coach_prompt.txt` and `workout_coach_prompt.txt` and sends user context for plan generation.

Note: older README referenced Ollama — the current code uses OpenRouter. Some legacy Ollama-sidecar code remains but the AI calls are performed by `ai_caller.py`.

## Database

The app uses a local SQLite database file named `health.db`. On first run the app will create required tables automatically. You can remove `health.db` to reset data (or use a migration script if you add one).

## Run locally

1. Create and activate a virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Set up required variables:

In app.py:
```py
app.config["SECRET_KEY"] = "qwertyuiopasdfghjklzxcvbnm"  # Use your own secret key here to encrypt the data
```

In ai_caller.py:
```py
API_KEY = "openrouter_api_key"  # Enter your openrouter API key here
```

3. Start the app (development):

```bash
python app.py
```

By default the app runs on 127.0.0.1:5501 (see `app.run(...)` in `app.py`).

## Usage overview

- Signup for a new account and login.
- Set your preferences on the Preferences page (dietary preferences, goals, age, activity level, etc.).
- Use the BMI Calculator to record weight/height entries; BMI entries are saved and used by the AI to tailor meal/workout plans.
- Generate weekly meal and workout plans from the Meal Plan and Workout Plan pages.
- Chat with the AI assistant from the Chat page; messages are saved to history.
- Track progress and optionally connect with friends to compare charts.

## Security & production notes

- Do not commit secret keys or API keys. Use environment variables or a secrets manager.
- The default `SECRET_KEY` in `app.py` is for development only. Replace it before deploying.
- Consider enabling HTTPS, session protection, rate limiting and proper model usage quotas when exposing the app.

## Development notes & troubleshooting

- If AI calls return errors, verify `OPENROUTER_API_KEY` is set correctly and the chosen model is available on OpenRouter.
- The app expects `diet_coach_prompt.txt` and `workout_coach_prompt.txt` to exist in the project root — they provide system-level prompts for plan generation.
- If templates or tables are missing, check runtime errors in the console — the app tries to create missing tables on startup.

## Tests

There are no automated tests included. For quick smoke testing: create an account, set preferences, add a BMI entry, and try generating plans and chatting.

## License

This project is licensed under the MIT License.
