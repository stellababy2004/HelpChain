from flask import Flask, render_template
import os

app = Flask(__name__, template_folder=os.path.join(os.getcwd(), "templates"))


@app.route("/")
def home():
    return '<h1>HelpChain</h1><a href="/chatbot">AI Chatbot</a>'


@app.route("/chatbot")
def chatbot():
    return render_template("chatbot.html")


if __name__ == "__main__":
    print("Starting test server on http://localhost:5002")
    print("Test the chatbot at: http://localhost:5002/chatbot")
    app.run(debug=True, host="127.0.0.1", port=5002, use_reloader=False)
