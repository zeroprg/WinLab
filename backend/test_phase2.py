"""Phase 2 functional verification script."""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def chat(text: str, user: str = "zeroprg@yahoo.com") -> str:
    data = json.dumps({"user_id": user, "role": "user", "text": text, "locale": "ru"}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/message",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read())
        return body.get("reply", "")


def search(q: str) -> list:
    from urllib.parse import quote
    url = f"{BASE}/api/knowledge/search?q={quote(q)}"
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.loads(r.read()).get("results", [])


if __name__ == "__main__":
    cases = [
        ("Onboarding", "Покажи мой план адаптации"),
        ("KB - отпуск", "Расскажи про политику отпусков"),
        ("HR self-service", "Сколько дней отпуска у меня осталось?"),
        ("Unknown", "Как дела в компании?"),
    ]
    for label, text in cases:
        try:
            reply = chat(text)
            print(f"\n[{label}]")
            print(f"  => {reply[:200]}")
        except Exception as e:
            print(f"[{label}] ERROR: {e}")

    print("\n--- Search 'отпуск' ---")
    results = search("отпуск")
    print(f"  Found: {len(results)}")
    if results:
        print(f"  First: {str(results[0].get('text',''))[:120]}")

    print("\n--- Search 'адаптация' ---")
    results2 = search("план")
    print(f"  Found: {len(results2)}")
