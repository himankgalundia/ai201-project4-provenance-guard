"""Calibration harness (Milestone 4).

Runs both signals + the combined classifier on four deliberately chosen inputs
spanning the confidence range, and prints each signal separately so a
misbehaving signal is easy to spot. Run with the venv active:

    python test_scoring.py
"""

from signals import combine_and_classify, generate_label

CASES = {
    "Clearly AI-generated": (
        "Artificial intelligence represents a transformative paradigm shift in "
        "modern society. It is important to note that while the benefits of AI "
        "are numerous, it is equally essential to consider the ethical "
        "implications. Furthermore, stakeholders across various sectors must "
        "collaborate to ensure responsible deployment."
    ),
    "Clearly human-written": (
        "ok so i finally tried that new ramen place downtown and honestly? "
        "underwhelming. the broth was fine but they put WAY too much sodium in "
        "it and i was thirsty for like three hours after. my friend got the "
        "spicy version and said it was better. probably won't go back unless "
        "someone drags me there"
    ),
    "Borderline: formal human": (
        "The relationship between monetary policy and asset price inflation has "
        "been extensively studied in the literature. Central banks face a "
        "fundamental tension between their mandate for price stability and the "
        "unintended consequences of prolonged low interest rates on equity and "
        "real estate valuations."
    ),
    "Borderline: lightly edited AI": (
        "I've been thinking a lot about remote work lately. There are genuine "
        "tradeoffs — flexibility and no commute on one side, isolation and "
        "blurred work-life boundaries on the other. Studies show productivity "
        "varies widely by individual and role type."
    ),
}


def main():
    for name, text in CASES.items():
        r = combine_and_classify(text)
        label = generate_label(r["attribution"], r["confidence"])
        print("=" * 72)
        print(name)
        print("-" * 72)
        print(f"  llm_score         : {r['llm_score']:.3f}  ({r['llm_reasoning']})")
        print(f"  stylometric_score : {r['stylometric_score']:.3f}")
        print(f"  combined ai_score : {r['ai_score']:.3f}")
        print(f"  attribution       : {r['attribution']}")
        print(f"  confidence        : {r['confidence']:.3f}")
        print(f"  label variant     : {label['variant']}")
    print("=" * 72)


if __name__ == "__main__":
    main()
