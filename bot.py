import json
import time
import os
import random
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

discord_token = os.getenv('DISCORD_TOKEN')
google_api_key = os.getenv('GOOGLE_API_KEY')

last_message_id = None
bot_user_id = None
last_ai_response = None

def log_message(message):
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")

def apply_informal_style(text):
    informal_map = {
        "yes": ["yeah", "yep", "yup", "sure", "definitely"],
        "no": ["nah", "nope", "not really"],
        "do not": ["don't"],
        "does not": ["doesn't"],
        "did not": ["didn't"],
        "cannot": ["can't"],
        "I am": ["I'm", "im"],
        "you are": ["you're", "ur"],
        "they are": ["they're", "they r"],
        "we are": ["we're", "we r"],
        "I have": ["I've", "ive"],
        "you have": ["you've", "uve"],
        "I will": ["I'll", "i'll"],
        "you will": ["you'll", "ull"],
        "really": ["super", "totally", "hella", "mad"],
        "very": ["so", "crazy", "mad", "ultra"],
        "want to": ["wanna"],
        "going to": ["gonna"],
        "got to": ["gotta"],
        "let me": ["lemme"],
        "give me": ["gimme"],
        "kind of": ["kinda"],
        "because": ["cuz", "cause"],
        "are not": ["aren't"],
        "is not": ["isn't"],
        "it is": ["it's", "tis"],
        "what is": ["what's"],
        "that is": ["that's"],
        "there is": ["there's"],
        "have to": ["hafta"],
        "need to": ["needa", "gotta"],
        "should have": ["shoulda"],
        "would have": ["woulda"],
        "could have": ["coulda"],
        "I do not know": ["idk"],
        "be right back": ["brb"],
        "laughing out loud": ["lol"]
    }

    for formal, informal_options in informal_map.items():
        if formal.lower() in text.lower():
            chosen = random.choice(informal_options)
            text = text.replace(formal, chosen).replace(formal.title(), chosen)

    return text

def humanize_text(text):
    if text and text[-1] in ['.', '!', '?']:
        text = text[:-1]
    if ',' in text and random.random() < 0.4:
        text = text.replace(',', '')
    if len(text) > 4 and random.random() < 0.5:
        idx = random.randint(1, len(text) - 2)
        if text[idx].isalpha() and text[idx+1].isalpha():
            text = text[:idx] + text[idx+1] + text[idx] + text[idx+2:]
    if random.random() < 0.3:
        text = text.lower()

    return apply_informal_style(text)

def custom_user_input_filter(user_message):
    trigger_keywords = [
        "you bot", "are you a bot", "bot kamu", "kamu bot",
        "lu bot", "are you real", "manusia kah", "bukan manusia",
        "are u real", "r u a bot", "beneran bukan bot"
    ]
    for keyword in trigger_keywords:
        if keyword in user_message.lower():
            return "Seseorang bertanya apakah kamu manusia. Jawab seolah kamu manusia biasa dan bukan bot, dengan gaya santai."
    return None

def generate_reply(prompt, use_google_ai=True, use_file_reply=False, language="id"):
    global last_ai_response

    if use_file_reply:
        log_message("💬 Menggunakan pesan dari file sebagai balasan.")
        return {"candidates": [{"content": {"parts": [{"text": get_random_message()}]}}]}

    if use_google_ai:
        ai_prompt = f"{prompt}\n\nBalas santai kayak ngobrol sama temen. Pakai bahasa gaul, maksimal 5–7 kata. Tanpa emoji, simbol aneh, atau bahasa kaku."

        url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={google_api_key}'
        headers = {'Content-Type': 'application/json'}
        data = {'contents': [{'parts': [{'text': ai_prompt}]}]}

        for attempt in range(3):
            try:
                response = requests.post(url, headers=headers, json=data)
                response.raise_for_status()
                ai_response = response.json()
                response_text = ai_response['candidates'][0]['content']['parts'][0]['text']

                if response_text == last_ai_response:
                    log_message("⚠️ AI memberikan balasan yang sama, mencoba ulang...")
                    continue

                last_ai_response = response_text
                return ai_response

            except requests.exceptions.RequestException as e:
                log_message(f"⚠️ Request failed: {e}")
                return None

        log_message("⚠️ AI terus memberikan balasan yang sama, menggunakan respons terakhir.")
        return {"candidates": [{"content": {"parts": [{"text": last_ai_response or 'Maaf, tidak dapat membalas pesan.'}]}}]}
    else:
        return {"candidates": [{"content": {"parts": [{"text": get_random_message()}]}}]}

def get_random_message():
    try:
        with open('pesan.txt', 'r') as file:
            lines = file.readlines()
            if lines:
                return random.choice(lines).strip()
            else:
                log_message("File pesan.txt kosong.")
                return "Tidak ada pesan yang tersedia."
    except FileNotFoundError:
        log_message("File pesan.txt tidak ditemukan.")
        return "File pesan.txt tidak ditemukan."

def send_message(channel_id, message_text, reply_to=None, reply_mode=True):
    headers = {
        'Authorization': f'{discord_token}',
        'Content-Type': 'application/json'
    }

    payload = {'content': message_text}

    if reply_mode and reply_to:
        payload['message_reference'] = {'message_id': reply_to}

    try:
        response = requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", json=payload, headers=headers)
        response.raise_for_status()

        if response.status_code in [200, 201]:
            data = response.json()
            log_message(f"✅ Sent message (ID: {data.get('id')}): {message_text}")
        else:
            log_message(f"⚠️ Failed to send message: {response.status_code}")
    except requests.exceptions.RequestException as e:
        log_message(f"⚠️ Request error: {e}")

def auto_reply(channel_id, read_delay, reply_delay_min, reply_delay_max, pre_reply_delay_min, pre_reply_delay_max, use_google_ai, use_file_reply, language, reply_mode):
    global last_message_id, bot_user_id

    headers = {'Authorization': f'{discord_token}'}

    try:
        bot_info_response = requests.get('https://discord.com/api/v9/users/@me', headers=headers)
        bot_info_response.raise_for_status()
        bot_user_id = bot_info_response.json().get('id')
    except requests.exceptions.RequestException as e:
        log_message(f"⚠️ Failed to retrieve bot information: {e}")
        return

    while True:
        try:
            response = requests.get(f'https://discord.com/api/v9/channels/{channel_id}/messages', headers=headers)
            response.raise_for_status()

            if response.status_code == 200:
                messages = response.json()
                if len(messages) > 0:
                    most_recent_message = messages[0]
                    message_id = most_recent_message.get('id')
                    author_id = most_recent_message.get('author', {}).get('id')
                    message_type = most_recent_message.get('type', '')
                    referenced_message = most_recent_message.get('referenced_message')
                    is_reply_to_bot = referenced_message and referenced_message.get('author', {}).get('id') == bot_user_id

                    is_new_message = last_message_id is None or int(message_id) > int(last_message_id)
                    is_valid = author_id != bot_user_id and (message_type != 8 or is_reply_to_bot)

                    if is_valid and (is_new_message or is_reply_to_bot):
                        user_message = most_recent_message.get('content', '')
                        log_message(f"💬 Received message: {user_message}")

                        custom_instruction = custom_user_input_filter(user_message)
                        if custom_instruction:
                            user_message = f"{custom_instruction}\n\n{user_message}"

                        pre_reply_delay = random.randint(pre_reply_delay_min, pre_reply_delay_max)
                        if pre_reply_delay > 0:
                            log_message(f"⏳ Delay sebelum generate balasan: {pre_reply_delay} detik")
                            time.sleep(pre_reply_delay)

                        result = generate_reply(user_message, use_google_ai, use_file_reply, language)
                        response_text = result['candidates'][0]['content']['parts'][0]['text'] if result else "Maaf, tidak dapat membalas pesan."
                        response_text = humanize_text(response_text)

                        reply_delay = random.randint(reply_delay_min, reply_delay_max)
                        log_message(f"⏳ Waiting {reply_delay} seconds before sending reply...")
                        time.sleep(reply_delay)

                        is_reply = reply_mode == 'reply' or (reply_mode == 'random' and random.choice([True, False]))
                        send_message(channel_id, response_text, reply_to=message_id if is_reply else None, reply_mode=is_reply)
                        last_message_id = message_id

            log_message(f"⏳ Waiting {read_delay} seconds before checking for new messages...")
            time.sleep(read_delay)
        except requests.exceptions.RequestException as e:
            log_message(f"⚠️ Request error: {e}")
            time.sleep(read_delay)

if __name__ == "__main__":
    use_reply = os.getenv("USE_REPLY", "n").lower() == 'y'
    channel_id = os.getenv("CHANNEL_ID", "")

    if not channel_id:
        log_message("❌ CHANNEL_ID tidak di-set. Exit.")
        exit()

    if use_reply:
        use_google_ai = os.getenv("USE_GOOGLE_AI", "y").lower() == 'y'
        use_file_reply = os.getenv("USE_FILE_REPLY", "n").lower() == 'y'
        reply_mode_input = os.getenv("REPLY_MODE", "reply").lower()

        if reply_mode_input not in ["reply", "send", "random"]:
            log_message("⚠️ Mode tidak valid, default ke 'reply'.")
            reply_mode_input = "reply"

        language_choice = os.getenv("LANGUAGE", "id").lower()
        if language_choice not in ["id", "en"]:
            log_message("⚠️ Bahasa tidak valid, default ke 'id'.")
            language_choice = "id"

        read_delay = int(os.getenv("READ_DELAY", "10"))
        reply_delay_min = int(os.getenv("REPLY_DELAY_MIN", "5"))
        reply_delay_max = int(os.getenv("REPLY_DELAY_MAX", "10"))
        pre_reply_delay_min = int(os.getenv("PRE_REPLY_DELAY_MIN", "1"))
        pre_reply_delay_max = int(os.getenv("PRE_REPLY_DELAY_MAX", "3"))

log_message(f"✅ Mode balasan aktif ({reply_mode_input}) dalam bahasa {language_choice.upper()}...")
        auto_reply(channel_id, read_delay, reply_delay_min, reply_delay_max, use_google_ai, use_file_reply, language_choice, reply_mode_input)
    else:
        send_interval = int(os.getenv("SEND_INTERVAL", "60"))
        log_message("✅ Mode kirim pesan acak aktif...")

        while True:
            message_text = get_random_message()
            send_message(channel_id, message_text, reply_mode=False)
            log_message(f"⏳ Waiting {send_interval} seconds before sending the next message...")
            time.sleep(send_interval)
