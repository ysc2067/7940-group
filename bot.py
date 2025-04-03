import os
import json
import openai
import firebase_admin
from firebase_admin import credentials, firestore
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
import asyncio
from flask import Flask
from hypercorn.asyncio import serve
from hypercorn.config import Config

# 初始化 Firebase
firebase_json = os.getenv("FIREBASE_JSON")
cred = credentials.Certificate(json.loads(firebase_json))
firebase_admin.initialize_app(cred)
db = firestore.client()

# 初始化 OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Flask 保活服务
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

# 处理用户兴趣
async def set_interests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    interests = context.args
    db.collection("users").document(user_id).set({"interests": interests})
    await update.message.reply_text(f"✅ Your interests have been saved: {', '.join(interests)}")

# 推荐活动
async def recommend_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    doc = db.collection("users").document(user_id).get()
    interests = doc.to_dict().get("interests", []) if doc.exists else []
    try:
        prompt = f"Suggest 3 online events for: {', '.join(interests) if interests else 'general users'}"
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        await update.message.reply_text(response.choices[0].message.content)
    except Exception as e:
        await update.message.reply_text(f"❗ OpenAI error: {e}")

# 群组创建
async def create_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args)
    user_id = str(update.message.from_user.id)
    db.collection("groups").document(topic).set({"members": [user_id]}, merge=True)
    await update.message.reply_text(f"✅ Group '{topic}' created and you joined.")

# 群组加入
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
        await update.message.reply_text(f"✅ You joined '{topic}'. Members: {len(members)}")
    else:
        await update.message.reply_text("⚠️ Group does not exist. Use /create_group to create one.")

# 普通聊天功能
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": user_input}]
        )
        await update.message.reply_text(response.choices[0].message.content)
    except Exception as e:
        await update.message.reply_text(f"❗ OpenAI error: {e}")

# /start 指令
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! I'm your COMP7940 chatbot. You can use /set_interests, /event, /create_group, /join_group or just talk to me!")

# 运行 Telegram Bot
async def run_bot():
    print("🚀 Telegram bot is starting...")
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app_ = ApplicationBuilder().token(token).build()
    app_.add_handler(CommandHandler("start", start))
    app_.add_handler(CommandHandler("set_interests", set_interests))
    app_.add_handler(CommandHandler("event", recommend_event))
    app_.add_handler(CommandHandler("create_group", create_group))
    app_.add_handler(CommandHandler("join_group", join_group))
    app_.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    print("✅ Bot polling started.")
    await app_.run_polling()

# Flask 保活
async def run_flask():
    config = Config()
    config.bind = [f"0.0.0.0:{os.environ.get('PORT', 10000)}"]
    await serve(app, config)

# 同时运行 Flask + Bot
async def main():
    await asyncio.gather(
        run_bot(),
        run_flask()
    )

if __name__ == "__main__":
    asyncio.run(main())
