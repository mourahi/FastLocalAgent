import requests
import json
import time

print('Testing disk space query...')
response = requests.post('http://127.0.0.1:8000/chat', json={'text': 'Quel est mon espace disque ?'}, timeout=60)

if response.status_code == 200:
    full_response = ''
    lines = response.text.split('\n')
    print(f'Received {len(lines)} lines')

    for i, line in enumerate(lines):
        if line.startswith('data: '):
            try:
                data = json.loads(line[6:])
                if 'message' in data:
                    full_response += data['message']
                    if i < 5:  # Print first few chunks
                        print(f'Chunk {i}: {repr(data["message"])}')
            except Exception as e:
                print(f'Error parsing line {i}: {e}')

    print(f'\nFull response ({len(full_response)} chars): {repr(full_response)}')

    # Check if it contains a result
    if 'GB' in full_response:
        print('SUCCESS: Found GB in response!')
    else:
        print('WARNING: No GB found in response')
else:
    print('HTTP Error:', response.status_code, response.text)