import requests
import json

# Test 1: Greeting
print("=" * 60)
print("TEST 1: Bonjour (greeting)")
print("=" * 60)

url = "http://127.0.0.1:8000/chat"
data = {
    "text": "bonjour",
    "session_id": "test_greeting",
    "model_name": "qwen2.5-coder:3b",
    "tools_config": {"executor_python": True}
}

print("Sending: bonjour")
response = requests.post(url, json=data, stream=True)

if response.status_code == 200:
    print("Response:")
    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith('data: '):
                try:
                    data_obj = json.loads(line_str[6:])
                    if 'message' in data_obj:
                        print(data_obj['message'], end='')
                except json.JSONDecodeError:
                    pass
    print("\n")

# Test 2: Disk space
print("=" * 60)
print("TEST 2: Combien me reste d'espace disque")
print("=" * 60)

data = {
    "text": "utilisez python et donnez moi combien me reste d'espace disque",
    "session_id": "test_disk_space",
    "model_name": "qwen2.5-coder:3b",
    "tools_config": {"executor_python": True}
}

print("Sending: utilisez python et donnez moi combien me reste d'espace disque")
response = requests.post(url, json=data, stream=True)

if response.status_code == 200:
    print("Response:")
    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith('data: '):
                try:
                    data_obj = json.loads(line_str[6:])
                    if 'message' in data_obj:
                        print(data_obj['message'], end='')
                except json.JSONDecodeError:
                    pass
    print("\n")

print("=" * 60)
print("Tests completed")
print("=" * 60)