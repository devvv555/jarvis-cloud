"""Standalone 24/7 Jarvis Telegram Bot with Text & Voice support powered by Groq & Ollama."""

import os
import sys
import io
import time
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# System prompt giving Jarvis his personality
SYSTEM_PROMPT = """You are Jarvis, a brilliant, helpful, friendly, and concise personal AI assistant. 
You are speaking directly to Devdarshan on his phone. Keep answers direct, friendly, and natural."""

conversation_history = {}

def ask_groq(chat_id: int, user_text: str) -> str:
    """Send text to Groq API (Qwen 3.8 27B / GPT-OSS 120B) with memory."""
    if not GROQ_API_KEY:
        return "Error: GROQ_API_KEY is not configured in environment variables."
        
    if chat_id not in conversation_history:
        conversation_history[chat_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
        
    conversation_history[chat_id].append({"role": "user", "content": user_text})
    
    # Keep last 15 messages in memory
    messages = [conversation_history[chat_id][0]] + conversation_history[chat_id][-14:]
    
    try:
        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "qwen/qwen3.8-27b",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1024
            },
            timeout=30.0
        )
        if resp.status_code == 200:
            reply = resp.json()["choices"][0]["message"]["content"]
            conversation_history[chat_id].append({"role": "assistant", "content": reply})
            return reply
        else:
            print(f"[Groq Error] {resp.status_code}: {resp.text}")
            return "I had trouble reaching my reasoning engine. Please try again in a moment."
    except Exception as e:
        print(f"[Request Error] {e}")
        return "I encountered a network issue while thinking. Please try again."

async def transcribe_voice(voice_bytes: bytes) -> str:
    """Transcribe voice message using Groq's high-speed Whisper Large v3."""
    if not GROQ_API_KEY:
        return ""
    try:
        files = {"file": ("voice.ogg", voice_bytes, "audio/ogg")}
        data = {"model": "whisper-large-v3-turbo"}
        resp = httpx.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            files=files,
            data=data,
            timeout=30.0
        )
        if resp.status_code == 200:
            return resp.json().get("text", "").strip()
        else:
            print(f"[Whisper Error] {resp.status_code}: {resp.text}")
            return ""
    except Exception as e:
        print(f"[Transcription Error] {e}")
        return ""

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    user_text = update.message.text
    chat_id = update.message.chat_id
    print(f"\n[Telegram Text] [{chat_id}]: {user_text}")
    
    reply = ask_groq(chat_id, user_text)
    print(f"[Jarvis Reply]: {reply}")
    await update.message.reply_text(reply)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.voice:
        return
    chat_id = update.message.chat_id
    print(f"\n[Telegram Voice] Received audio note from [{chat_id}]...")
    
    # Download voice note from Telegram
    voice_file = await update.message.voice.get_file()
    voice_bytes = await voice_file.download_as_bytearray()
    
    # Transcribe speech to text using Whisper
    transcript = await transcribe_voice(bytes(voice_bytes))
    if not transcript:
        await update.message.reply_text("I couldn't quite hear that clearly. Could you say it again?")
        return
        
    print(f"[Transcribed Speech]: \"{transcript}\"")
    
    # Generate intelligent answer
    reply = ask_groq(chat_id, transcript)
    print(f"[Jarvis Reply]: {reply}")
    
    # Send back answer (with speech confirmation)
    await update.message.reply_text(f"🎤 *You said:* \"{transcript}\"\n\n💬 *Jarvis:* {reply}", parse_mode="Markdown")

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN environment variable is not set!")
        sys.exit(1)
        
    print("[Jarvis] Booting Cloud & Voice enabled Telegram Bot...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Listen to both TEXT and VOICE notes
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    print("[Jarvis] Bot is ONLINE! Both Text and Voice Notes are fully active!")
    app.run_polling()

if __name__ == "__main__":
    main()
