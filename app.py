from copy import deepcopy
import json
import os
from datetime import datetime, timedelta
import random
from flask import Flask, render_template, request, jsonify, redirect, url_for, session

# Імпортуємо нашу бібліотеку даних
from grammar_data import GRAMMAR_DATA

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

PROGRESS_FILE = "progress.json"


def get_current_user():
    return session.get("username", "ігор").lower().strip()


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
        now = datetime.now()
        current_card_data = data[username].get(card_id, {})

        next_review_str = current_card_data.get("next_review")
        if next_review_str:
            next_review_time = datetime.fromisoformat(next_review_str)
            if now < next_review_time:
                return

        # Визначаємо поточний номер повторення
        repetitions = current_card_data.get("repetitions", 0) + 1
        if repetitions > 6:
            repetitions = 6

        # Шкала інтервалів Anki у днях: 1 день -> 3 дні -> 7 днів -> 14 днів -> 30 днів -> 60 днів
        intervals_in_days = [1, 3, 7, 14, 30, 60]
        days_to_add = intervals_in_days[repetitions - 1]

        pass_date = now.isoformat()
        next_review_date = (now + timedelta(days=days_to_add)).isoformat()

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
    username = get_current_user()
    reminders = []
    user_progress = {}
    can_exam = False

    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                user_progress = data.get(username, {})
                now = datetime.now()
                for card_id, info in user_progress.items():
                    repetitions = info.get("repetitions", 0)
                    if repetitions < 6:
                        next_review_str = info.get("next_review")
                        if next_review_str:
                            next_review = datetime.fromisoformat(next_review_str)
                            if now >= next_review:
                                card_title = GRAMMAR_DATA.get(card_id, {}).get("title", card_id)
                                reminders.append(f"Сьогодні потрібно повторити тему: {card_title} (система Anki)")
            except Exception:
                pass

    # Жорстка перевірка: шукаємо всі картки у яких ключ містить 'simple'
    if GRAMMAR_DATA:
        simple_cards = [k for k in GRAMMAR_DATA.keys() if "simple" in k.lower()]
        if simple_cards:
            all_simple_passed = True
            for card_id in simple_cards:
                reps = user_progress.get(card_id, {}).get("repetitions", 0)
                if reps < 3:
                    all_simple_passed = False
                    break
            can_exam = all_simple_passed

    return render_template("board.html", cards=GRAMMAR_DATA, reminders=reminders, user_progress=user_progress,
                           can_exam=can_exam)


@app.route("/neural")
def neural():
    username = get_current_user()
    user_progress = {}
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                user_progress = data.get(username, {})
            except Exception:
                pass
    return render_template("neural.html", user_progress=user_progress)


@app.route("/exam")
def exam():
    all_questions = []
    for card_id, card_data in GRAMMAR_DATA.items():
        if "simple" in card_id.lower():
            for q in card_data.get("questions", []):
                all_questions.append(q)

    if not all_questions:
        return redirect(url_for("board"))

    sample_size = min(len(all_questions), 20)
    selected_items = deepcopy(random.sample(all_questions, sample_size))

    questions = []
    answers_map = {}

    for idx, item in enumerate(selected_items):
        opts = item["options"]
        random.shuffle(opts)
        questions.append({"id": idx, "question": item["question"], "options": opts})
        answers_map[str(idx)] = item["answer"]

    fake_card = {
        "title": "🔥 Іспит по групах Simple",
        "formula": "Збірний марафон з усіх часів Simple"
    }

    return render_template(
        "quiz.html",
        card=fake_card,
        card_id="exam_matrix",
        questions=questions,
        answers_map=answers_map,
    )


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

    real_card_id = card_id
    for key, val in GRAMMAR_DATA.items():
        if val == card:
            real_card_id = key
            break

    username = get_current_user()
    user_progress = {}
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                user_progress = data.get(username, {})
            except Exception:
                pass

    return render_template("card.html", card=card, card_id=real_card_id, user_progress=user_progress)


@app.route("/reset/<card_id>")
def reset_card(card_id):
    username = get_current_user()
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}

        if username not in data:
            data[username] = {}

        target_key = card_id
        for key in GRAMMAR_DATA.keys():
            if key.lower().replace("-", "_") == card_id.lower().replace("-", "_"):
                target_key = key
                break

        if target_key not in data[username]:
            data[username][target_key] = {}

        data[username][target_key]["repetitions"] = 0
        data[username][target_key]["score"] = 0

        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    return redirect(url_for("board"))


@app.route("/set_user/<username>")
def set_user(username):
    session["username"] = username.lower().strip()
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
    username = get_current_user()

    if card_id == "exam_matrix":
        return jsonify({"status": "success"})

    if card_id and score is not None:
        save_user_progress(username, card_id, int(score))
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}, 400)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)