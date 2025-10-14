from flask import Flask

app = Flask(__name__)


@app.route("/")
def hello():
    return "Hello World from HelpChain!"


@app.route("/health")
def health():
    return {"status": "ok", "message": "HelpChain is running"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
