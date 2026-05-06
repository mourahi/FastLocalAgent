import requests
import json

# Test the chat endpoint
url = "http://127.0.0.1:8000/chat"
data = {
    "text": "quelle heure est t elle ?",
    "session_id": "test_session",
    "model_name": "qwen2.5-coder:3b",
    "tools_config": {
        "executor_python": True
    }
}

print("Sending request to chat endpoint...")
print(f"Message: {data['text']}")

try:
    response = requests.post(url, json=data, stream=True)
    print(f"Response status: {response.status_code}")

    if response.status_code == 200:
        print("Streaming response:")
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    try:
                        data = json.loads(line_str[6:])
                        if 'message' in data:
                            print(data['message'], end='')
                    except json.JSONDecodeError:
                        pass
        print("\n--- End of response ---")
    else:
        print(f"Error: {response.text}")

except Exception as e:
    print(f"Error: {e}")