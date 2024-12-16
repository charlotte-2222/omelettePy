import openai

from utilFunc.config import OPEN_AI_KEY

openai.api_key = OPEN_AI_KEY


def chat_gpt_query(prompt):
    response = openai.Completion.create(
        engine="gpt-4",
        prompt=prompt,
        max_tokens=150,
    )
    return response.choices[0].text.strip()
