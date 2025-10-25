import os

os.environ["USE_SOCKETIO"] = "false"

print("Importing appy module...")
import appy

print(f"App from appy: {appy.app}")
print(f"App name: {appy.app.name}")
print(f"App import name: {appy.app.import_name}")

# Use the fully configured app from appy.py
app = appy.app

if __name__ == "__main__":
    print("Starting Flask server for testing...")
    print(f"Routes registered: {len(list(app.url_map.iter_rules()))}")
    for rule in app.url_map.iter_rules():
        if "test" in rule.rule:
            print(f"  Test route: {rule.rule}")
    app.run(debug=True, host="127.0.0.1", port=5000, use_reloader=False)
