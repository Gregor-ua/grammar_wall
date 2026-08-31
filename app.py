from copy import deepcopy
import json
import os
from datetime import datetime, timedelta
import random
from flask import Flask, render_template, request, jsonify, redirect, url_for

# Імпортуємо нашу бібліотеку даних
from grammar_data import GRAMMAR_DATA

app = Flask(__name__)

PROGRESS_FILE = "progress.json"


def save_user_progress(username, card_id, score):
    data = {}
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}

    if username not in data:
        data[username] = {}

    if score >= 7:
        pass_date = datetime.now().isoformat()
        next_review_date = (datetime.now() + timedelta(minutes=5)).isoformat()

        current_card_data = data[username].get(card_id, {})
        repetitions = current_card_data.get("repetitions", 0) + 1
        if repetitions > 6:
            repetitions = 6

        data[username][card_id] = {
            "last_passed": pass_date,
            "next_review": next_review_date,
            "score": score,
            "repetitions": repetitions
        }

        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/board")
def board():
    reminders = []
    user_progress = {}
    username = "ігор"

    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                user_progress = data.get(username, {})
                now = datetime.now()
                for card_id, info in user_progress.items():
                    repetitions = info.get("repetitions", 0)
                    if repetitions < 6:
                        next_review = datetime.fromisoformat(info["next_review"])
                        if now >= next_review:
                            card_title = GRAMMAR_DATA.get(card_id, {}).get("title", card_id)
                            reminders.append(f"Сьогодні потрібно повторити тему: {card_title} (система Anki)")
            except Exception:
                pass

    return render_template("board.html", cards=GRAMMAR_DATA, reminders=reminders, user_progress=user_progress)


def find_card(card_id):
    if not card_id:
        return None
    if card_id in GRAMMAR_DATA:
        return GRAMMAR_DATA[card_id]

    clean_target = card_id.lower().replace("-", "").replace("_", "").replace(" ", "")
    for key, card_data in GRAMMAR_DATA.items():
        clean_key = key.lower().replace("-", "").replace("_", "").replace(" ", "")
        if clean_key == clean_target:
            return card_data
    return None


@app.route("/card/<card_id>")
def card_detail(card_id):
    card = find_card(card_id)
    if not card:
        return f"Картку '{card_id}' не знайдено", 404
    return render_template("card.html", card=card, card_id=card_id)


# МАРШРУТ ДЛЯ ПОВНОГО СКИНУ ПРОГРЕСУ КОНКРЕТНОЇ КАРТКИ
@app.route("/reset/<card_id>")
def reset_card(card_id):
    username = "ігор"
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}

        if username in data:
            for variant in [card_id, card_id.replace("-", "_"), card_id.replace("_", "-")]:
                if variant in data[username]:
                    del data[username][variant]

            with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

    return redirect(url_for("board"))


@app.route("/quiz/<card_id>")
def quiz(card_id):
    card = find_card(card_id)
    if not card:
        return "Картку не знайдено", 404

    raw_questions = card.get("questions", [])
    sample_size = min(len(raw_questions), 10)
    selected_items = deepcopy(random.sample(raw_questions, sample_size))

    questions = []
    answers_map = {}

    for idx, item in enumerate(selected_items):
        opts = item["options"]
        random.shuffle(opts)

        questions.append({"id": idx, "question": item["question"], "options": opts})
        answers_map[str(idx)] = item["answer"]

    return render_template(
        "quiz.html",
        card=card,
        card_id=card_id,
        questions=questions,
        answers_map=answers_map,
    )


@app.route("/api/save_score", methods=["POST"])
def save_score():
    data = request.get_json()
    card_id = data.get("card_id")
    score = data.get("score")
    username = "ігор"

    if card_id and score is not None:
        save_user_progress(username, card_id, int(score))
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400


if __name__ == "__main__":
    app.run(debug=True)