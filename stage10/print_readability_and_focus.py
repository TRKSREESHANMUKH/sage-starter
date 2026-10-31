"""
stage10/print_readability_and_focus.py — Compute and print readability metrics and focus items for Days 0 to 10.
"""

from datetime import date
from pathlib import Path
import re
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import SessionLocal
from web.one_page_data import build_one_page_context


def run():
    days = [date(2025, 12, 31)] + [date(2026, 1, d) for d in range(1, 11)]
    print("=" * 80)
    print("SAGE READABILITY & FOCUS REPORT FOR DAYS 0 TO 10")
    print("=" * 80)

    for idx, d in enumerate(days):
        day_label = f"Day {idx} ({d.isoformat()})"
        brief = build_one_page_context(selected_date_str=d.isoformat())
        summary = brief.get("plain_summary", {})
        sentences = summary.get("sentences", [])
        text = summary.get("text", "")

        sentence_lengths = [len(s.split()) for s in sentences]
        max_s_len = max(sentence_lengths) if sentence_lengths else 0
        all_words = text.split()
        total_words = len(all_words)
        char_count = sum(len(w.strip(".,;:()\"'")) for w in all_words)
        avg_word_len = char_count / total_words if total_words > 0 else 0.0

        today_focus = brief.get("today_focus_items", [])
        weekly_focus = brief.get("weekly_focus_items", [])

        print(f"\n--- {day_label} ---")
        print(f"Sentences count   : {len(sentences)}")
        print(f"Sentence lengths  : {sentence_lengths} (Max: {max_s_len} words, rule strictly < 22)")
        print(f"Total word count  : {total_words} words")
        print(f"Avg word length   : {avg_word_len:.2f} chars/word")
        print("\nSummary Text:")
        for s_idx, s in enumerate(sentences):
            print(f"  [{s_idx+1}] ({len(s.split())}w) {s}")

        print("\nToday's Focus Items:")
        for it in today_focus:
            print(f"  • [{it.get('owner_role')}] {it.get('action')} (Target: {it.get('due_time')})")

        print("\nWeekly Focus Items:")
        for it in weekly_focus:
            print(f"  • [{it.get('owner_role')}] {it.get('action')}")


if __name__ == "__main__":
    run()
