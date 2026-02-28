import os
import requests
import json

API_KEY = "AIzaSyCl6JliYPMsz-sKU9i5yYxliURHtQNtLmc"

if not API_KEY:
    raise Exception("GEMINI_API_KEY not set")

URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

headers = {
    "Content-Type": "application/json"
}

params = {
    "key": API_KEY
}

payload = {
    "contents": [
        {
            "role": "user",
            "parts": [
                {"text": "Explain in one sentence what machine learning is."}
            ]
        }
    ],
    "generationConfig": {
        "temperature": 0,
        "maxOutputTokens": 200
    }
}

response = requests.post(URL, headers=headers, params=params, json=payload, timeout=60)

if not response.ok:
    print("Error:", response.status_code)
    print(response.text)
    exit()

data = response.json()

candidates = data.get("candidates", [])
if not candidates:
    print("No response returned")
    exit()

text = candidates[0]["content"]["parts"][0]["text"]

print("Response:\n")
print(text)