import httpx
import sys
import os

TOKEN = os.getenv("BOT_TOKEN", "")
if not TOKEN:
    print("❌ Переменная окружения BOT_TOKEN не задана. Укажи токен перед запуском скрипта.")
    sys.exit(1)

print("--- DIAGNOSTIC SCRIPT STARTED ---")
print(f"Python Version: {sys.version}")

try:
    print("\n1. Testing connection to Telegram API (getMe)...")
    res = httpx.get(f"https://api.telegram.org/bot{TOKEN}/getMe", timeout=10.0)
    if res.status_code == 200:
        bot_info = res.json().get("result", {})
        print(f"✅ Connection successful!")
        print(f"🤖 Bot Name: {bot_info.get('first_name')}")
        print(f"🆔 Bot Username: @{bot_info.get('username')}")
        print("👉 IMPORTANT: Make sure you are sending messages to this EXACT username!")
    else:
        print(f"❌ Failed. Telegram API returned status code {res.status_code}: {res.text}")
except Exception as e:
    print(f"❌ Connection error: {e}")

try:
    print("\n2. Checking for pending messages (getUpdates)...")
    res = httpx.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", timeout=10.0)
    if res.status_code == 200:
        updates = res.json().get("result", [])
        print(f"✅ Successfully retrieved updates. Count: {len(updates)}")
        if updates:
            print("\nRecent messages received by the bot:")
            for u in updates[-3:]:
                msg = u.get("message", {})
                chat = msg.get("chat", {})
                from_user = msg.get("from", {})
                print(f"- From: {from_user.get('first_name')} (@{from_user.get('username')}), Chat ID: {chat.get('id')}, Text: '{msg.get('text')}'")
        else:
            print("📭 No messages in the queue. Try sending /start to the bot and run this script again.")
    else:
         print(f"❌ Failed. status code {res.status_code}: {res.text}")
except Exception as e:
    print(f"❌ Error checking updates: {e}")
