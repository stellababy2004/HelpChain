import os

from flask import Flask, jsonify, request
from langdetect import detect
from transformers import MarianMTModel, MarianTokenizer, pipeline

app = Flask(__name__)

# Q&A pipeline
qa_pipeline = pipeline(
    "question-answering", model="distilbert-base-cased-distilled-squad"
)

# Translation models
translation_models = {
    "bg-en": ("Helsinki-NLP/opus-mt-bg-en",),
    "en-bg": ("Helsinki-NLP/opus-mt-en-bg",),
    "fr-en": ("Helsinki-NLP/opus-mt-fr-en",),
    "en-fr": ("Helsinki-NLP/opus-mt-en-fr",),
    "bg-fr": ("Helsinki-NLP/opus-mt-bg-fr",),
    "fr-bg": ("Helsinki-NLP/opus-mt-fr-bg",),
}


def translate_text(text, src, tgt):
    key = f"{src}-{tgt}"
    if key not in translation_models:
        return text
    model_name = translation_models[key][0]
    tokenizer = MarianTokenizer.from_pretrained(model_name)
    model = MarianMTModel.from_pretrained(model_name)
    translated = model.generate(**tokenizer(text, return_tensors="pt", padding=True))
    tgt_text = [tokenizer.decode(t, skip_special_tokens=True) for t in translated]
    return tgt_text[0]


@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.json
    question = data.get("question", "")
    context = data.get("context", "")
    if not question or not context:
        return jsonify({"error": "Missing question or context"}), 400
    result = qa_pipeline({"question": question, "context": context})
    answer = result["answer"]
    return jsonify({"answer": answer})


@app.route("/api/translate", methods=["POST"])
def translate():
    data = request.json
    text = data.get("text", "")
    src = data.get("src_lang", "bg")
    tgt = data.get("tgt_lang", "en")
    if not text:
        return jsonify({"error": "Missing text"}), 400
    translated = translate_text(text, src, tgt)
    return jsonify({"translated": translated})


@app.route("/api/detect_language", methods=["POST"])
def detect_language():
    data = request.json
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "Missing text"}), 400
    detected = detect(text)
    return jsonify({"language": detected})


@app.route("/api/health", methods=["GET"])
def health():
    health_status = {
        "qa_model_loaded": qa_pipeline is not None,
        "translation_models": list(translation_models.keys()),
        "status": "ok",
    }
    return jsonify(health_status)


# Feedback loop endpoint
@app.route("/api/feedback", methods=["POST"])
def feedback():
    data = request.json
    feedback_text = data.get("feedback", "")
    user_id = data.get("user_id", None)
    ai_response = data.get("ai_response", None)
    if not feedback_text:
        return jsonify({"error": "Missing feedback"}), 400
    feedback_entry = {
        "feedback": feedback_text,
        "user_id": user_id,
        "ai_response": ai_response,
    }
    feedback_file = "feedback.json"
    if os.path.exists(feedback_file):
        import json

        with open(feedback_file, encoding="utf-8") as f:
            feedback_list = json.load(f)
    else:
        feedback_list = []
    feedback_list.append(feedback_entry)
    with open(feedback_file, "w", encoding="utf-8") as f:
        import json

        json.dump(feedback_list, f, ensure_ascii=False, indent=2)
    return jsonify({"status": "success", "saved": feedback_entry})


if __name__ == "__main__":
    app.run(debug=True)

import os

from flask import Flask, jsonify, request
from langdetect import detect
from transformers import pipeline

app = Flask(__name__)

# Q&A pipeline (може да се смени с по-специализиран модел)
qa_pipeline = pipeline(
    "question-answering", model="distilbert-base-cased-distilled-squad"
)
# Превод (BG/FR/EN) MarianMT
from transformers import MarianMTModel, MarianTokenizer

translation_models = {
    "bg-en": ("Helsinki-NLP/opus-mt-bg-en",),
    "en-bg": ("Helsinki-NLP/opus-mt-en-bg",),
    "fr-en": ("Helsinki-NLP/opus-mt-fr-en",),
    "en-fr": ("Helsinki-NLP/opus-mt-en-fr",),
    "bg-fr": ("Helsinki-NLP/opus-mt-bg-fr",),
    "fr-bg": ("Helsinki-NLP/opus-mt-fr-bg",),
}


def translate_text(text, src, tgt):
    key = f"{src}-{tgt}"
    if key not in translation_models:
        return text
    model_name = translation_models[key][0]
    tokenizer = MarianTokenizer.from_pretrained(model_name)
    model = MarianMTModel.from_pretrained(model_name)
    translated = model.generate(**tokenizer(text, return_tensors="pt", padding=True))
    tgt_text = [tokenizer.decode(t, skip_special_tokens=True) for t in translated]
    return tgt_text[0]


@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.json
    question = data.get("question", "")
    context = data.get("context", "")
    if not question or not context:
        return jsonify({"error": "Missing question or context"}), 400
    result = qa_pipeline({"question": question, "context": context})
    answer = result["answer"]
    return jsonify({"answer": answer})


@app.route("/api/translate", methods=["POST"])
def translate():
    data = request.json
    text = data.get("text", "")
    src = data.get("src_lang", "bg")
    tgt = data.get("tgt_lang", "en")
    if not text:
        return jsonify({"error": "Missing text"}), 400
    translated = translate_text(text, src, tgt)
    return jsonify({"translated": translated})


@app.route("/api/detect_language", methods=["POST"])
def detect_language():
    data = request.json
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "Missing text"}), 400
    detected = detect(text)
    return jsonify({"language": detected})


# Health-check endpoint (винаги регистриран)
@app.route("/api/health", methods=["GET"])
def health():
    health_status = {
        "qa_model_loaded": qa_pipeline is not None,
        "translation_models": list(translation_models.keys()),
        "status": "ok",
    }
    return jsonify(health_status)


if __name__ == "__main__":
    app.run(debug=True)
