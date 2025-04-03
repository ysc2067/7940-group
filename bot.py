import os
import openai
import firebase_admin
from firebase_admin import credentials, firestore
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
import json
import os
from firebase_admin import credentials, firestore

firebase_json = os.getenv("FIREBASE_JSON")
cred = credentials.Certificate(json.loads(firebase_json))
firebase_admin.initialize_app(cred)
db = firestore.client()


openai.api_key = os.getenv("OPENAI_API_KEY")

def get_user_interests(user_id):
    doc = db.collection("users").document(user_id).get()
    if doc.exists:
        return doc.to_dict().get("interests", [])
    return []

async def set_interests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    interests = context.args
    db.collection("users").document(user_id).set({"interests": interests})
    await update.message.reply_text(f"Your interests have been saved: {', '.join(interests)}")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": user_input}]
    )
    await update.message.reply_text(response.choices[0].message.content)

async def recommend_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    interests = get_user_interests(user_id)
    if interests:
        prompt = f"Suggest 3 fun online events for someone interested in: {', '.join(interests)}"
    else:
        prompt = "Suggest 3 fun online events for general audience."

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    await update.message.reply_text(response.choices[0].message.content)

async def create_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args)
    user_id = str(update.message.from_user.id)
    ref = db.collection("groups").document(topic)
    ref.set({"members": [user_id]}, merge=True)
    await update.message.reply_text(f"Group '{topic}' created and you joined.")

async def join_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args)
    user_id = str(update.message.from_user.id)
    ref = db.collection("groups").document(topic)
    doc = ref.get()
    if doc.exists:
        members = doc.to_dict().get("members", [])
        if user_id not in members:
            members.append(user_id)
            ref.update({"members": members})
        await update.message.reply_text(f"You joined '{topic}'. Total members: {len(members)}")
    else:
        await update.message.reply_text("Group does not exist. Use /create_group to create it.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I'm your COMP7940 chatbot. Try typing something or use /set_interests")

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("set_interests", set_interests))
    app.add_handler(CommandHandler("event", recommend_event))
    app.add_handler(CommandHandler("create_group", create_group))
    app.add_handler(CommandHandler("join_group", join_group))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    app.run_polling()

import threading
from flask import Flask

app = Flask(__name__)

def run_bot():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("set_interests", set_interests))
    app.add_handler(CommandHandler("event", recommend_event))
    app.add_handler(CommandHandler("create_group", create_group))
    app.add_handler(CommandHandler("join_group", join_group))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app.run_polling()

@app.route('/')
def home():
    return "Bot is running!"

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

