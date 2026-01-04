from openai import OpenAI
import json

def get_llm_client(api_key, base_url=None):
    return OpenAI(api_key=api_key, base_url=base_url)

def generate_ideas_deepseek(api_key, title, search_title, tongue_use):
    client = get_llm_client(api_key, base_url="https://api.deepseek.com")
    prompt = f"Title: {title}\nSearch Context: {search_title}\nTongue/Style: {tongue_use}\nTask: Generate 5 to 6 distinct ideas. IMPORTANT: For each idea, you MUST write exactly three sentences."
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def select_and_score_openai(api_key, ideas_text, title, search_title):
    client = get_llm_client(api_key)
    prompt = f"Ideas: {ideas_text}\nContext: {title} | {search_title}\nReturn JSON: {{\"best_idea\": \"...\", \"clout_score\": 85}}"
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={ "type": "json_object" }
    )
    data = json.loads(response.choices[0].message.content)
    return data['best_idea'], data['clout_score']