#!/usr/bin/env python3
"""
Wait for email-api service to be ready
"""
import time
import requests
import sys

def wait_for_email_api(max_attempts=30, delay=2):
    """Wait for email-api service to be ready"""
    for attempt in range(max_attempts):
        try:
            response = requests.get("http://email-api:8001/health", timeout=5)
            if response.status_code == 200:
                print("✅ Email API is ready!")
                return True
        except Exception as e:
            print(f"⏳ Waiting for email-api... (attempt {attempt + 1}/{max_attempts})")
            time.sleep(delay)
    
    print("❌ Email API not ready after maximum attempts")
    return False

if __name__ == "__main__":
    if wait_for_email_api():
        sys.exit(0)
    else:
        sys.exit(1)
