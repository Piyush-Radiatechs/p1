import os
import requests

api_key = ""
print("Key exists:", bool(api_key))
print("Key prefix:", api_key[:8] + "..." if api_key else "MISSING")

response = requests.get(
    "https://api.groq.com/openai/v1/models",
    headers={
        "Authorization": f"Bearer {api_key}"
    }
)

print("Status:", response.status_code)
print("Response:", response.text[:300])
