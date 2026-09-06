"""Seeds 4 attempts at deliberately different proficiency levels through the
real scoring pipeline (T3.7). Requires the backend running on :8000.

Usage: .venv/Scripts/python seed_attempts.py
"""

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


def seed_one(client: httpx.Client, candidate: dict) -> str:
    attempt_id = client.post("/api/attempts", json={"name": candidate["name"]}).json()["attempt_id"]

    for item_id, answer in {**candidate["grammar"], **candidate["listening"]}.items():
        client.post(f"/api/attempts/{attempt_id}/response", json={"item_id": item_id, "text": answer})

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
            print(f"{candidate['name']}: status={report['status']} cir={cir}")

        overall_bands = [r[2] for r in results if r[2] is not None]
        if overall_bands:
            print(f"\nBand spread: min={min(overall_bands)} max={max(overall_bands)}")


if __name__ == "__main__":
    main()
