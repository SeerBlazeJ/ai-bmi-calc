import requests

API_KEY = "openrouter_api_key"

url = "https://openrouter.ai/api/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}
def call (sys_prompt, history, message):
    global data
    data = {
     "model": "meta-llama/llama-4-maverick:free",  # You can choose any model available on OpenRouter
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "system", "content": f"This is the previous history for the user that you should keep context of while generating: {history}"},
            {"role": "user", "content": message },
        ]
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        result = response.json()
        return result["choices"][0]["message"]["content"]
    else:
        return f"Error: {response.status_code} {response.text}"
"""
# example useage of call function
with open ("diet_coach_prompt.txt", "r") as f:
    DIET_COACH_SYSTEM_PROMPT = f.read()
print(call(sys_prompt=DIET_COACH_SYSTEM_PROMPT, history="", message="generate a balanced workout plan"))
"""
