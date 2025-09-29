import os
from dotenv import load_dotenv
from openai import OpenAI


def main():
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Missing OPENAI_API_KEY in environment/.env")

    client = OpenAI(api_key=api_key)

    print("-- Embedding sanity --")
    emb = client.embeddings.create(
        model="text-embedding-3-small",
        input="Hello Workout AI"
    )
    vec = emb.data[0].embedding
    print(f"Embedding dim: {len(vec)} (expect ~1536)")

    print("-- Response sanity --")
    msg = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Reply with 'ready'."}
        ],
        temperature=0
    )
    print("Model reply:", msg.choices[0].message.content)


if __name__ == "__main__":
    main()

