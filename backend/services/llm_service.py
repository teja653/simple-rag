import requests
from backend.config import OPENROUTER_API_KEY

URL = "https://openrouter.ai/api/v1/chat/completions"

def get_response(prompt):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "nvidia/nemotron-nano-9b-v2:free",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    response = requests.post(URL, headers=headers, json=data)
    result = response.json()

    if "choices" not in result:
        print("OpenRouter API error response:", result)
        error_msg = result.get("error", {}).get("message", str(result))
        raise Exception(f"OpenRouter API error: {error_msg}")

    return result["choices"][0]["message"]["content"]