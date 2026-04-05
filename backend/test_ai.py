from ai_engine import analyze_ticket

scenarios = [
    ("How do I reset my password?", "I forgot my login password and need to reset it"),
    ("Production DB is down", "Our main database is not responding. All users are affected."),
    ("How do I apply for leave?", "I want to apply for 3 days casual leave next week. Not sure of the process.")
]

for title, desc in scenarios:
    print(f"\nTesting: {title}")
    result = analyze_ticket(title, desc)
    print(f"  Category: {result['category']}")
    print(f"  Severity: {result['severity']}")
    print(f"  Department: {result['department']}")
    print(f"  Resolution: {result['resolution_path']}")
    print(f"  Confidence: {result['confidence']}")