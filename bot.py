import telebot
from telegram.ext import Updater, CommandHandler
import requests
import json

# Initialize bot with your token
TOKEN = '8621587751:AAGrC6DrIl5d8s0psxy3y-C7GtcOkF0ln_Q'
updater = Updater(token=TOKEN)
dp = updater.dispatcher

# Claude API configuration
CLAUDE_API_URL = 'https://api.anthropic.com/v1/messages'
CLAUDE_API_KEY = 'sk-ant-api03-your_api_key_here'  # You'll need to replace this

def start(update, context):
    update.message.reply_text(
        "Hi! This bot connects to Claude. Try sending: /ask 'Hello Claude'\n"
        "Or: /ask 'Summarize this document content'"
    )

def ask_claude(update, context):
    # Extract the question - handle both /ask Hello and /ask "Hello"
    message_parts = ' '.join(context.args)
    if not message_parts:
        update.message.reply_text(
            "Please provide a question after /ask. Example: /ask 'Hello Claude'"
        )
        return
    
    # Show "thinking..." status
    status_msg = update.message.reply_text("Thinking...")
    
    try:
        # Forward to Claude via Anthropic API
        headers = {
            'x-api-key': CLAUDE_API_KEY,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }
        
        payload = {
            'model': 'claude-opus-4-8',
            'max_tokens': 200,
            'temperature': 0.7,
            'system': 'You are Claude, an AI assistant that provides helpful and accurate responses. Be concise and direct.',
            'messages': [
                {
                    'role': 'user',
                    'content': message_parts
                }
            ]
        }
        
        response = requests.post(CLAUDE_API_URL, headers=headers, json=payload)
        
        if response.status_code == 200:
            claude_result = response.json()
            result_text = claude_result['content'][0]['text']
            
            # Edit the "thinking..." message with the response
            status_msg.edit_text(f"Claude: {result_text}")
        else:
            status_msg.edit_text(
                f"❌ Error calling Claude (Status: {response.status_code})"
            )
            
    except Exception as e:
        status_msg.edit_text(f"❌ Error: {str(e)}")

# Add command handlers
dp.add_handler(CommandHandler('start', start))
dp.add_handler(CommandHandler('ask', ask_claude))

print(f"Bot starting with token: {TOKEN[:20]}...")
updater.start_polling()

print("Bot is running!")
updater.idle()
