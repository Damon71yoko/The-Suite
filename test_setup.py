import os
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials
import requests

# Load environment variables
load_dotenv()

print("Testing The Suite Setup...")
print("-" * 40)

# Test environment variables
env_vars = {
    "VAPI_API_KEY": os.getenv('VAPI_API_KEY'),
    "EDEN_AI_API_KEY": os.getenv('EDEN_AI_API_KEY'),
    "STRIPE_SECRET_KEY": os.getenv('STRIPE_SECRET_KEY'),
    "FIREBASE_CREDENTIALS_PATH": os.getenv('FIREBASE_CREDENTIALS_PATH')
}

for key, value in env_vars.items():
    status = "✓" if value else "✗"
    print(f"{status} {key}: {'Set' if value else 'Missing'}")

print("-" * 40)

# Test Firebase connection
try:
    cred = credentials.Certificate(env_vars['FIREBASE_CREDENTIALS_PATH'])
    firebase_admin.initialize_app(cred)
    print("✓ Firebase: Connected")
except Exception as e:
    print(f"✗ Firebase: {e}")

# Test Vapi connection
try:
    headers = {"Authorization": f"Bearer {env_vars['VAPI_API_KEY']}"}
    response = requests.get("https://api.vapi.ai/assistant", headers=headers)
    if response.status_code in [200, 201]:
        print("✓ Vapi: Connected")
    else:
        print(f"✗ Vapi: Status {response.status_code}")
except Exception as e:
    print(f"✗ Vapi: {e}")

print("-" * 40)
print("Setup test complete!")