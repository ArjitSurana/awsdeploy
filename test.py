"""List available Gemini models. Requires GOOGLE_API_KEY in .env."""
import os

from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise SystemExit("Set GOOGLE_API_KEY in .env before running test.py")

genai.configure(api_key=api_key)

for m in genai.list_models():
    print(m.name)
