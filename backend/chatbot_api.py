from flask import Flask, request, jsonify
from huggingface_hub import InferenceClient

app = Flask(__name__)
HF_TOKEN = "your_huggingface_token_here"


@app.route("/chatbot_api", methods=["POST"])
def chatbot_api():
    user_message = request.json.get("message", "")
    client = InferenceClient("google/flan-t5-base", token=HF_TOKEN)
    response = client.text_generation(user_message)
    return jsonify({"answer": response})


if __name__ == "__main__":
    app.run(debug=True)
