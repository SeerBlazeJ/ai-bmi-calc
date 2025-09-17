# AI-Powered Health and Fitness Companion

This is a Flask-based web application that serves as a personal health and fitness companion. It provides users with a BMI calculator, personalized meal and workout plans, and an AI-powered chat assistant.

## Features

*   **User Authentication:** Secure user sign-up and login functionality.
*   **BMI Calculator:** Calculate your Body Mass Index (BMI) to assess your weight status.
*   **Personalized Meal Plans:** Generate weekly meal plans based on user preferences using Ollama.
*   **Personalized Workout Plans:** Generate weekly workout schedules to help users stay active using Ollama.
*   **AI Chat Assistant:** A chat interface powered by Ollama to answer health and fitness-related questions.
*   **Progress Tracking:** A dashboard to track your progress over time.

## Project Structure

```
├── app.py              # Main Flask application file
├── health.db           # SQLite database
├── requirements.txt    # Python dependencies
├── rebuild_db.py       # Script to rebuild the database
├── static/
│   └── styles.css      # CSS stylesheets
└── templates/
    ├── base.html       # Base template
    ├── login.html      # Login page
    ├── signup.html     # Signup page
    ├── dashboard.html  # User dashboard
    ├── calculator.html # BMI calculator
    ├── meal_plan.html  # Meal plan generator
    ├── workout_plan.html # Workout plan generator
    └── chat.html       # AI chat interface
```

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/AI-powered-BMI-calculator.git
    cd AI-powered-BMI-calculator
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up Ollama:**
    This project uses Ollama to power its AI features. Make sure you have Ollama installed and running. You can find installation instructions here: [https://ollama.ai/](https://ollama.ai/)

    Once Ollama is running, pull the `gemma3` model:
    ```bash
    ollama pull gemma3
    ```

5.  **Run the application:**
    Create a file named `health.db` in the main code directory, and the enter the following command:
    ```bash
    flask run
    ```

    The application will be available at `http://127.0.0.1:5000`.

## Usage

1.  **Sign up** for a new account or **login** if you already have one.
2.  Use the **BMI Calculator** to check your BMI.
3.  Generate personalized **Meal Plans** and **Workout Plans**.
4.  Chat with the **AI Assistant** for any health and fitness queries.

## Note:
To change the secret key, the user needs to edit the key in the .env folder as well as moify this line of code:
```python
app.config["SECRET_KEY"] = "your_secret_key_here"  # In production, use a secure random key
```

## License

This project is licensed under the MIT License.
