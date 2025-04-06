import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def set_webhook():
    # Get bot token and webhook URL from environment variables
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    webhook_url = f"{os.getenv('WEBHOOK_URL')}/webhook"
    
    # API endpoint
    url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    
    # Request data
    data = {
        "url": webhook_url,
        "allowed_updates": [
            "message",
            "edited_message",
            "channel_post",
            "edited_channel_post",
            "inline_query",
            "chosen_inline_result",
            "callback_query",
            "shipping_query",
            "pre_checkout_query",
            "poll",
            "poll_answer",
            "my_chat_member",
            "chat_member",
            "chat_join_request"
        ]
    }
    
    # Send request
    response = requests.post(url, json=data)
    print(f"Response: {response.json()}")
    
    # Check current webhook info
    info_response = requests.get(f"https://api.telegram.org/bot{bot_token}/getWebhookInfo")
    print(f"\nWebhook Info: {info_response.json()}")

if __name__ == "__main__":
    set_webhook() 
