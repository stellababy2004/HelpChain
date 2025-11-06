import requests

try:
    response = requests.get("http://localhost:8000/", timeout=5)
    print("Home page status:", response.status_code)
    print("Content length:", len(response.text))

    # Check for Font Awesome in home page
    if "cdnjs.cloudflare.com/ajax/libs/font-awesome" in response.text:
        print("SUCCESS: Font Awesome CSS found in home page")
    else:
        print("WARNING: Font Awesome CSS not found in home page")

except Exception as e:
    print("Error:", e)
