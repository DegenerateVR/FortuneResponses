import requests
import json
import base64
from flask import Flask, request, jsonify
from typing import List
from datetime import datetime, timezone
import traceback

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

# Groq API Configuration
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = "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"  # Replace with a valid Groq API key

# GitHub Configuration
GITHUB_USERNAME = "DegenerateDecals"
GITHUB_TOKEN = "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"  # Replace with a valid GitHub token
GITHUB_REPO = "FortuneResponses"
FILE_PATH = "responses.json"

# Flask Application Setup
app = Flask(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  UTILITY FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def get_current_timestamp():
    """
    Returns the current UTC timestamp in ISO format.
    """
    return datetime.now(timezone.utc).isoformat()


def log_error(message: str):
    """
    Logs an error message with additional details for debugging.
    """
    print(f"[ERROR] {message}")
    print(f"[TRACEBACK] {traceback.format_exc()}")


def log_debug(message: str):
    """
    Logs a debug message for better traceability of operations.
    """
    print(f"[DEBUG] {message}")


# ─────────────────────────────────────────────────────────────────────────────
#  TOKEN VALIDATION FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def validate_groq_api_key():
    """
    Validates the Groq API key by making a basic test request.
    """
    headers = {"Authorization": f"Bearer {GROQ_API_KEY.strip()}"}
    test_url = GROQ_API_URL.replace("/chat/completions", "/models")

    try:
        response = requests.get(test_url, headers=headers, timeout=10)
        if response.status_code == 401:
            log_error("Invalid Groq API Key. Ensure the key is correct and has proper permissions.")
            return False
        elif response.status_code == 200:
            log_debug("Groq API key is valid.")
            return True
        else:
            log_error(f"Unexpected response while validating Groq API key: {response.status_code}")
            return False
    except Exception as e:
        log_error(f"Error while validating Groq API key: {e}")
        return False


def validate_github_token():
    """
    Validates the GitHub token by testing access to the authenticated user endpoint.
    """
    url = "https://api.github.com/user"
    headers = {"Authorization": f"token {GITHUB_TOKEN.strip()}"}

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 401:
            log_error("Invalid GitHub token: Unauthorized access.")
            log_debug("Ensure the token has 'repo' or 'public_repo' scope depending on your repository type.")
            return False
        elif response.status_code == 200:
            log_debug("GitHub token is valid.")
            return True
        else:
            log_error(f"Unexpected response while validating GitHub token: {response.status_code}")
            return False
    except Exception as e:
        log_error(f"Failed to validate GitHub token: {e}")
        return False

# ─────────────────────────────────────────────────────────────────────────────
#  QUERY GROQ API FOR A FORTUNE
# ─────────────────────────────────────────────────────────────────────────────

def query_groq(name: str, keywords: List[str]) -> str:
    """
    Generate a fortune from the Groq API using the provided 'name' and 'keywords'.
    """
    unique_timestamp = get_current_timestamp()
    prompt = (
        f"Generate a fortune for {name} based on these keywords: {', '.join(keywords)}.\n"
        f"Add a unique timestamp: {unique_timestamp}."
    )
    payload = {
        "model": "llama-3.2-1b-preview",
        "messages": [
            {"role": "system", "content": "You are a fortune teller."},
            {"role": "user", "content": prompt}
        ]
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY.strip()}",
        "Content-Type": "application/json",
    }

    try:
        log_debug(f"Sending request to Groq API with unique timestamp: {unique_timestamp}")
        response = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        log_debug(f"Received response from Groq API: {data}")

        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        else:
            return "Error: Groq API returned an unexpected format."
    except requests.exceptions.RequestException as e:
        log_error(f"Error connecting to Groq API: {e}")
        return f"Error connecting to Groq API: {e}"

# ─────────────────────────────────────────────────────────────────────────────
#  UPDATE OR CREATE responses.json ON GITHUB
# ─────────────────────────────────────────────────────────────────────────────

def update_github_file(new_content: str) -> None:
    """
    Create or update responses.json in your GitHub repo with 'new_content' (string).
    """
    if not validate_github_token():
        log_error("GitHub token validation failed. Aborting operation.")
        return

    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN.strip()}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        log_debug("Checking if file exists on GitHub...")
        get_resp = requests.get(url, headers=headers)
        log_debug(f"GET Response: {get_resp.status_code} - {get_resp.text}")

        if get_resp.status_code == 401:
            log_error("Unauthorized: Invalid GitHub token or insufficient permissions.")
            return

        get_resp.raise_for_status()

        if get_resp.status_code == 200:
            current_sha = get_resp.json().get("sha")
            log_debug(f"File exists. Updating content with SHA: {current_sha}")
            payload = {
                "message": "Update fortune response",
                "content": base64.b64encode(new_content.encode("utf-8")).decode("utf-8"),
                "sha": current_sha
            }
        elif get_resp.status_code == 404:
            log_debug("File does not exist. Creating new file...")
            payload = {
                "message": "Create fortune response",
                "content": base64.b64encode(new_content.encode("utf-8")).decode("utf-8")
            }
        else:
            log_error(f"Unexpected response while checking file existence: {get_resp.status_code}")
            return

        log_debug("Sending request to update/create file on GitHub...")
        put_resp = requests.put(url, headers=headers, json=payload)
        log_debug(f"PUT Response: {put_resp.status_code} - {put_resp.text}")

        if put_resp.status_code in (200, 201):
            log_debug("File successfully created/updated on GitHub!")
        else:
            log_error(f"Unexpected response from GitHub: {put_resp.status_code} - {put_resp.text}")
    except requests.exceptions.RequestException as e:
        log_error(f"Error communicating with GitHub: {e}")

# ─────────────────────────────────────────────────────────────────────────────
#  FLASK ROUTE TO HANDLE FORTUNE REQUESTS
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/generate_fortune', methods=['GET'])
def generate_fortune():
    """
    Flask route to handle fortune generation. Accepts 'name' and 'keywords' as query params.
    """
    name = request.args.get('name')
    keywords = request.args.getlist('keywords')

    if not name or not keywords:
        log_error("Missing 'name' or 'keywords' parameters.")
        return jsonify({"error": "Missing required parameters 'name' or 'keywords'."}), 400

    log_debug(f"Received request: name={name}, keywords={keywords}")

    fortune_text = query_groq(name, keywords)
    log_debug(f"Generated fortune: {fortune_text}")

    new_json_data = {
        "fortune": fortune_text,
        "name": name,
        "keywords": keywords
    }

    try:
        log_debug("Updating GitHub with new content...")
        update_github_file(json.dumps(new_json_data, indent=2))
    except Exception as e:
        log_error(f"Failed to update GitHub: {e}")
        return jsonify({"error": "Failed to update GitHub."}), 500

    return jsonify({"status": "success", "fortune": fortune_text}), 200

# ─────────────────────────────────────────────────────────────────────────────
#  RUN FLASK APPLICATION
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log_debug("Starting Flask server...")
    app.run(debug=True, host="0.0.0.0", port=5000)
