import urllib.request
import json

url = "http://localhost:8000/api/investigations/49488d13-7fa6-4778-9f02-e62600e577cc/events"
headers = {
    "Authorization": "Bearer 9d6qTtDjIP6T",
    "Content-Type": "application/json"
}
data = {
    "source_type": "crowdstrike",
    "raw": {
        "event_simpleName": "ProcessRollup2",
        "timestamp": "2026-10-01T00:00:00Z",
        "UserSid": "S-1-5-21",
        "SHA256HashData": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "FileName": "malware.exe",
        "CommandLine": "malware.exe --stealth"
    }
}

req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')

try:
    with urllib.request.urlopen(req) as response:
        print("Status:", response.status)
        print("Response:", response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("Error:", e.code)
    print(e.read().decode('utf-8'))
