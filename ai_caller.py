import requests

API_KEY = "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"

url = "https://openrouter.ai/api/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}
def call (sys_prompt, history, message):
    global data
    data = {
     "model": "meta-llama/llama-3.3-8b-instruct:free",  # You can choose any model available on OpenRouter
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
