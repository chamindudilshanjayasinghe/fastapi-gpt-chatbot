import os

import httpx
from openai import OpenAI


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    http_client = httpx.Client()  # 👈 No proxy, explicitly clean
    return OpenAI(api_key=api_key, http_client=http_client)
