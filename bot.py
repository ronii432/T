import os
import telebot
import json
import requests
import logging
import time
import subprocess
from pymongo import MongoClient
from datetime import datetime, timedelta
import certifi
import asyncio
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from threading import Thread

loop = asyncio.get_event_loop()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MONGO_URI = os.getenv("MONGODB_URI")

FORWARD_CHANNEL_ID = -1002156421934
CHANNEL_ID = -1002156421934
ERROR_CHANNEL_ID = -1002156421934

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['rishi']
users_collection = db.users

bot = telebot.TeleBot(TOKEN)
REQUEST_INTERVAL = 1

def is_user_admin(user_id, chat_id):
    try:
        return bot.get_chat_member(chat_id, user_id).status in ['administrator', 'creator']
    except:
        return False

def check_user_approval(user_id):
    user_data = users_collection.find_one({"user_id": user_id})
    return bool(user_data and user_data.get('plan', 0) > 0)

def send_not_approved_message(chat_id):
    bot.send_message(chat_id, "*YOU ARE NOT APPROVED! CONTACT ADMIN FOR ACCESS.*", parse_mode='Markdown')

@bot.message_handler(commands=['approve', 'disapprove'])
def approve_or_disapprove_user(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    is_admin = is_user_admin(user_id, CHANNEL_ID)
    cmd_parts = message.text.split()

    if not is_admin:
        bot.send_message(chat_id, "*You are not authorized to use this command*", parse_mode='Markdown')
        return

    if len(cmd_parts) < 2:
        bot.send_message(chat_id, "*Invalid command format. Use /approve <user_id> <plan> <days> or /disapprove <user_id>.*", parse_mode='Markdown')
        return

    action = cmd_parts[0]
    target_user_id = int(cmd_parts[1])
    plan = int(cmd_parts[2]) if len(cmd_parts) >= 3 else 0
    days = int(cmd_parts[3]) if len(cmd_parts) >= 4 else 0

    if action == '/approve':
        valid_until = (datetime.now() + timedelta(days=days)).date().isoformat() if days > 0 else datetime.now().date().isoformat()
        users_collection.update_one(
            {"user_id": target_user_id},
            {"$set": {"plan": plan, "valid_until": valid_until, "access_count": 0}},
            upsert=True
        )
        msg_text = f"*User {target_user_id} approved with plan {plan} for {days} days.*"
    else:
        users_collection.update_one(
            {"user_id": target_user_id},
            {"$set": {"plan": 0, "valid_until": "", "access_count": 0}},
            upsert=True
        )
        msg_text = f"*User {target_user_id} disapproved and reverted to free.*"

    bot.send_message(chat_id, msg_text, parse_mode='Markdown')
    bot.send_message(CHANNEL_ID, msg_text, parse_mode='Markdown')

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)

    btn1 = KeyboardButton("ℹ️ My Info")
    btn2 = KeyboardButton("💼 ResellerShip")
    btn3 = KeyboardButton("Contact Admin ✔️")

    markup.add(btn1, btn2, btn3)

    bot.send_message(message.chat.id, "*🚀 Welcome to the Secure Bot 🚀*", reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(commands=['run'])
def run_command(message):
    user_id = message.from_user.id
    if not check_user_approval(user_id):
        send_not_approved_message(message.chat.id)
        return

    command = message.text.replace('/run ', '', 1).strip()

    if not command:
        bot.send_message(message.chat.id, "*Usage: /run <command>*", parse_mode='Markdown')
        return

    if '.py' in command or 'python' in command:
        bot.send_message(message.chat.id, "*Python scripts execution is not allowed.*", parse_mode='Markdown')
        return

    try:

        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        output = result.stdout.strip() if result.stdout else result.stderr.strip()

        if not output:
            output = "*Command executed but returned no output.*"

    except Exception as e:
        output = f"*Error executing command:* {str(e)}"

    bot.send_message(message.chat.id, f"```\n{output}\n```", parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.text == "ℹ️ My Info":
        user_id = message.from_user.id
        user_data = users_collection.find_one({"user_id": user_id})

        if user_data:
            username = message.from_user.username or "No Username"
            plan = user_data.get('plan', 'Not Approved')
            valid_until = user_data.get('valid_until', 'Not Approved')
            role = 'User' if plan > 0 else 'Not Approved'

            response = (
                f"*👤 User Info*\n"
                f"🔖 Role: {role}\n"
                f"🆔 User ID: {user_id}\n"
                f"👤 Username: @{username}\n"
                f"⏳ Approval Expiry: {valid_until if valid_until != 'Not Approved' else 'Not Approved'}"
            )
        else:
            response = "*No account information found. Please contact the administrator.*"

        bot.reply_to(message, response, parse_mode='Markdown')

    elif message.text == "💼 ResellerShip":
        bot.send_message(message.chat.id, "*For Reseller Ship, Contact Admin!*", parse_mode='Markdown')

    elif message.text == "Contact Admin ✔️":
        bot.reply_to(message, "*Contact Admin Selected*", parse_mode='Markdown')

    else:
        bot.reply_to(message, "*Invalid option*", parse_mode='Markdown')

def start_asyncio_thread():
    asyncio.set_event_loop(loop)
    loop.run_until_complete(asyncio.sleep(REQUEST_INTERVAL))

if __name__ == "__main__":
    asyncio_thread = Thread(target=start_asyncio_thread, daemon=True)
    asyncio_thread.start()
    logging.info("Secure Bot is Running...")
    
    while True:
        try:
            bot.polling(none_stop=True, interval=3, timeout=20)
        except Exception as e:
            logging.error(f"An error occurred while polling: {e}")
        time.sleep(REQUEST_INTERVAL)
