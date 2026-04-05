from groq import Groq
import json
import os
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv('GROQ_API_KEY'))

ANALYSIS_PROMPT = """
You are a smart ticketing AI. Analyze the support ticket below.
Return ONLY valid JSON. No extra text, no markdown, no explanation.

Ticket title: {title}
Ticket description: {description}

Return this exact JSON structure:
{{
    "category": "Billing|Bug|Access|HR|Server|DB|Feature|Other",
    "summary": "2-3 sentence summary of the issue",
    "severity": "Critical|High|Medium|Low",
    "sentiment": "Frustrated|Neutral|Polite",
    "resolution_path": "auto-resolve|assign",
    "auto_response": "Professional response if auto-resolve, else null",
    "department": "Engineering|Finance|HR|IT|Product|Marketing|Legal|DevOps",
    "confidence": 92,
    "estimated_hours": 4
}}
"""

def analyze_ticket(title: str, description: str) -> dict:
    prompt = ANALYSIS_PROMPT.format(title=title, description=description)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        print("Raw AI response:", raw)
        raise