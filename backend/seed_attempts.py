"""Seeds 4 attempts at deliberately different proficiency levels through the
real scoring pipeline (T3.7). This is how the recruiter dashboard and
analytics get data on a fresh demo.db. Requires Ollama running, and the
backend on :8000 started with ASSESSMENT_ALLOW_FIXED_SELECTION=1 so the seed
can pin a known 9-item set (g1..s2) against which the proficiency answer maps
are defined.

Usage:
  ASSESSMENT_ALLOW_FIXED_SELECTION=1 .venv/Scripts/python -m uvicorn main:app   # terminal 1
  .venv/Scripts/python seed_attempts.py                                          # terminal 2
"""

import json
import time
from pathlib import Path

import httpx

BASE_URL = "http://127.0.0.1:8000"
AUDIO_DIR = Path(__file__).parent / "seed_audio"

CANDIDATES = [
    {
        "name": "Alice Chen (strong)",
        "grammar": {"g1": "a", "g2": "c", "g3": "a", "g4": "b"},
        "listening": {"l1": "b", "l2": "b"},
        "writing": (
            "Dear valued customer, I am very sorry for the delay in your order. "
            "I completely understand how frustrating this must be, and I want to "
            "make it right immediately. I have arranged expedited shipping at no "
            "cost and refunded your original shipping fee as an apology. You "
            "should receive your package within two business days. Thank you for "
            "your patience and for giving us the chance to fix this."
        ),
        "s1_audio": "strong_s1.wav",
        "s2_audio": "strong_s2.wav",
    },
    {
        "name": "Ben Okafor (above average)",
        "grammar": {"g1": "a", "g2": "c", "g3": "a", "g4": "d"},
        "listening": {"l1": "b", "l2": "b"},
        "writing": (
            "Hi, sorry your order is late. We had a shipping delay but it should "
            "arrive soon. I can offer a discount on your next order if that helps. "
            "Let me know if you have questions."
        ),
        "s1_audio": "above_s1.wav",
        "s2_audio": "above_s2.wav",
    },
    {
        "name": "Carla Reyes (below average)",
        "grammar": {"g1": "b", "g2": "c", "g3": "c", "g4": "d"},
        "listening": {"l1": "a", "l2": "b"},
        "writing": (
            "Your order late. We are busy. It will come soon. Sorry."
        ),
        "s1_audio": "below_s1.wav",
        "s2_audio": "below_s2.wav",
    },
    {
        "name": "David Kim (weak)",
        "grammar": {"g1": "b", "g2": "a", "g3": "c", "g4": "d"},
        "listening": {"l1": "a", "l2": "a"},
        "writing": "sorry late. bye.",
        "s1_audio": "weak_s1.wav",
        "s2_audio": "weak_s2.wav",
    },
]


SEED_ITEM_IDS = ["g1", "g2", "g3", "g4", "l1", "l2", "w1", "s1", "s2"]


def seed_one(client: httpx.Client, candidate: dict) -> str:
    email = candidate["name"].split("(")[0].strip().lower().replace(" ", "") + "@example.com"
    password = "Password123!"
    res = client.post("/api/auth/signup", json={"email": email, "password": password, "display_name": candidate["name"]})
    if res.status_code == 409:
        client.post("/api/auth/login", json={"email": email, "password": password})

    client.put("/api/candidate/profile", json={"full_name": candidate["name"], "phone": "1234567890"})

    resp = client.post("/api/attempts", json={"item_ids": SEED_ITEM_IDS})
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to create attempt: {resp.status_code} {resp.text}")
    attempt_id = resp.json()["attempt_id"]

    served = {i["id"]: i for i in client.get(f"/api/attempts/{attempt_id}/items").json()["items"]}
    bank = {i["id"]: i for i in json.load(open(Path(__file__).parent / "bank.json"))["items"]}

    def display_letter(item_id: str, canonical: str) -> str:
        original = bank[item_id]["options"]
        target_text = original[["a", "b", "c", "d"].index(canonical)]
        shown = served[item_id]["options"]
        return ["a", "b", "c", "d"][shown.index(target_text)]

    for item_id, canonical in {**candidate["grammar"], **candidate["listening"]}.items():
        client.post(
            f"/api/attempts/{attempt_id}/response",
            json={"item_id": item_id, "text": display_letter(item_id, canonical)},
        )

    client.post(f"/api/attempts/{attempt_id}/response", json={"item_id": "w1", "text": candidate["writing"]})

    for item_id, filename in (("s1", candidate["s1_audio"]), ("s2", candidate["s2_audio"])):
        path = AUDIO_DIR / filename
        with open(path, "rb") as f:
            client.post(
                f"/api/attempts/{attempt_id}/audio",
                data={"item_id": item_id},
                files={"file": (f"{item_id}.webm", f, "audio/webm")},
            )

    client.post(f"/api/attempts/{attempt_id}/submit")
    return attempt_id


def wait_for_done(client: httpx.Client, attempt_id: str, timeout_s: int = 90) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        report = client.get(f"/api/attempts/{attempt_id}/report").json()
        if report["status"] != "scoring":
            return report
        time.sleep(2)
    raise TimeoutError(f"Attempt {attempt_id} did not finish scoring in {timeout_s}s")


def main() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        results = []
        for candidate in CANDIDATES:
            attempt_id = seed_one(client, candidate)
            report = wait_for_done(client, attempt_id)
            cir = next((s["band"] for s in report["scores"] if s["dimension"] == "cir"), None)
            results.append((candidate["name"], report["status"], cir))
            line = f"{candidate['name']}: status={report['status']} cir={cir}"
            if report["status"] == "error":
                line += f" ({report.get('error_message') or report.get('error')})"
            print(line)

        overall_bands = [r[2] for r in results if r[2] is not None]
        if overall_bands:
            print(f"\nBand spread: min={min(overall_bands)} max={max(overall_bands)}")


if __name__ == "__main__":
    main()
