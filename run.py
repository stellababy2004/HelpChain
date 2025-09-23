from backend.appy import app  # <-- важно е да сочи към backend/appy.py

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
