from flask import Flask, request, jsonify
import requests
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# Temporary user session storage
user_data = {}

# WhatsApp API Credentials
ACCESS_TOKEN = "EAAOAi7h03l8BO6jhNOmpzaV8tW5Hq4mZAAryB7IXv6LlnXeXi4GjWKZAvkjDZAvkzkPnUOxRk7pOCtVqztZAZA73RNPVvkMnQZBZAT2ZB0JDhb3p0UmkcAdlKTAluj2tDeAILcOf49Yjf4kZBytjo7hY7O6eUeYGaG5PB7VpxUPo8cbGvEPrzuIkrbDjpMVlMj6k0xoPUx2sbCEqidbeTxvbX6ys5AWoZD"
PHONE_NUMBER_ID = "550908254774273"
VERIFY_TOKEN = "svsfoods"

# Google Sheets API Configuration
SERVICE_ACCOUNT_FILE = "credsvs.json"  # Replace with your JSON key file
SHEET_ID = "185XRA23EbkqWg2E_QBXFwzFjsnsS6Rh9ksiFlU8LCdo"  # Replace with your Google Sheet ID
SHEET_NAME = "SVS_Foods"  # Sheet Name

# Authenticate Google Sheets API
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
client = gspread.authorize(creds)

def fetch_product_data():
    """Fetch product data from Google Sheet and convert it into a dictionary."""
    sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    data = sheet.get_all_values()  # Fetch all data
    
    headers = data[0]  # Extract column headers
    product_dict = {}  # Dictionary to store product details
    
    for row in data[1:]:
        product_name = row[0].strip().lower()  # Product Name
        product_dict[product_name] = {
            "price": row[1],  # Price
            "ingredients": row[2],  # Ingredients
            "recipe": row[3]  # Recipe
        }
    
    return product_dict

@app.route("/webhook", methods=["GET"])
def verify():
    """Verify Webhook"""
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Invalid verification token", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle Incoming Messages"""
    data = request.get_json()
    if "object" in data and "entry" in data:
        for entry in data["entry"]:
            for change in entry.get("changes", []):
                if "value" in change and "messages" in change["value"]:
                    for msg in change["value"]["messages"]:
                        sender_id = msg["from"]

                        # Ensure user_data is initialized
                        if sender_id not in user_data:
                            user_data[sender_id] = {"step": "language", "cart": [], "total": 0, "product_index": 0}

                        # Handle text messages
                        if "text" in msg:
                            user_input = msg["text"]["body"].strip().lower()
                            if user_input == "hi":
                                user_data[sender_id] = {"step": "language", "cart": [], "total": 0, "product_index": 0}
                                send_language_buttons(sender_id)
                                return "EVENT_RECEIVED", 200
                             # Handle text messages (name, address, etc.)
                            step = user_data[sender_id]["step"]

                            if step == "get_name":
                                user_data[sender_id]["name"] = user_input
                                user_data[sender_id]["step"] = "get_address"
                                send_message(sender_id, "📍 Please enter your address:")

                            elif step == "get_address":
                                user_data[sender_id]["address"] = user_input
                                user_data[sender_id]["step"] = "get_phone"
                                send_message(sender_id, "📞 Please enter your phone number:")

                            elif step == "get_phone":
                                user_data[sender_id]["phone"] = user_input
                                user_data[sender_id]["step"] = "get_payment_method"
                                send_payment_buttons(sender_id)
                        # Handle Interactive Button Responses
                        if "interactive" in msg and "button_reply" in msg["interactive"]:
                            handle_button_reply(sender_id, msg["interactive"]["button_reply"])

    return "EVENT_RECEIVED", 200
def send_language_buttons(sender_id):
    """Send Language Selection Buttons"""
    buttons = [
        {"type": "reply", "reply": {"id": "1", "title": "English"}},
        {"type": "reply", "reply": {"id": "2", "title": "தமிழ்"}}
    ]
    send_message(sender_id, "Choose your language:", buttons)
def send_payment_buttons(sender_id):
    """Send Payment Method Selection Buttons"""
    buttons = [
        {"type": "reply", "reply": {"id": "upi", "title": "UPI"}},
        {"type": "reply", "reply": {"id": "cod", "title": "Cash on Delivery"}}
    ]
    send_message(sender_id, "Which payment method would you like to use?", buttons)

def handle_button_reply(sender_id, button_reply):
    """Process Button Clicks"""
    reply_id = button_reply["id"]
    reply_title = button_reply["title"].lower()
    step = user_data[sender_id]["step"]
    product_data = fetch_product_data()  # Fetch latest product data from Google Sheets

    if step == "language":
        user_data[sender_id]["language"] = "english" if reply_id == "1" else "tamil"
        language_msg = "You selected English. Here are our products:" if reply_id == "1" else "நீங்கள் தமிழ் மொழியை தேர்ந்தெடுத்துள்ளீர்கள். எங்கள் பொருட்கள்:"
        send_message(sender_id, language_msg)
        user_data[sender_id]["step"] = "product_selection"
        user_data[sender_id]["product_index"] = 0  # Reset product index
        send_product_buttons(sender_id, product_data)

    elif step == "product_selection":
        if reply_id == "next":
            user_data[sender_id]["product_index"] += 2
            send_product_buttons(sender_id, product_data)
        else:
            user_data[sender_id]["selected_product"] = reply_title
            send_product_info(sender_id, reply_title, product_data)
            user_data[sender_id]["step"] = "recipe_prompt"

    elif step == "recipe_prompt":
        if reply_id == "1":
            send_recipe(sender_id, user_data[sender_id]["selected_product"], product_data)
            user_data[sender_id]["step"] = "order_prompt"
        else:
            send_message(sender_id, "Alright! Let me know if you need anything else.")

    elif step == "order_prompt":
        if reply_id == "1":
            send_message(sender_id, "Great! Let's proceed with your order. Please enter your *Name*:")            
            user_data[sender_id]["step"] = "get_name"
        else:
            send_message(sender_id, "No problem! Let me know if you need anything else.")

    elif step == "get_payment_method":  # 🚀 Fix: Handle Payment Selection Here
        user_data[sender_id]["payment_method"] = reply_title.capitalize()
        confirm_order(sender_id)  # Send order summary

def process_user_input(sender_id, user_input):
    """Handle text input based on the current step."""
    step = user_data[sender_id]["step"]

    if step == "get_name":
        user_data[sender_id]["name"] = user_input
        send_message(sender_id, "Please enter your *Address*:")
        user_data[sender_id]["step"] = "get_address"

    elif step == "get_address":
        user_data[sender_id]["address"] = user_input
        send_message(sender_id, "Please enter your *Phone Number*:")
        user_data[sender_id]["step"] = "get_phone"

    elif step == "get_phone":
        user_data[sender_id]["phone"] = user_input
        send_payment_buttons(sender_id)
        user_data[sender_id]["step"] = "get_payment_method"

    elif step == "get_payment_method":
        user_data[sender_id]["payment_method"] = user_input
        confirm_order(sender_id)


def confirm_order(sender_id):
    """Confirm Order and Send Summary"""
    order_summary = (
        f"📝 *Order Summary*\n"
        f"🍽 Product: {user_data[sender_id]['selected_product'].capitalize()}\n"
        f"👤 Name: {user_data[sender_id]['name'].capitalize()}\n"
        f"📍 Address: {user_data[sender_id]['address'].capitalize()}\n"
        f"📞 Phone: {user_data[sender_id]['phone']}\n"
        f"💳 Payment: {user_data[sender_id]['payment_method']}\n"
        f"✅ Your order has been placed successfully!"
    )
    send_message(sender_id, order_summary)


def send_message(recipient_id, message, buttons=None):
    """Send WhatsApp Message via API"""
    url = f"https://graph.facebook.com/v13.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_id,
        "type": "text",
        "text": {"body": message}
    }

    if buttons:
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_id,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": message},
                "action": {"buttons": buttons}
            }
        }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print("Message sent successfully!")
    else:
        print("Error sending message:", response.text)

def send_product_buttons(sender_id, product_data):
    """Send Product List from Google Sheet"""
    start_index = user_data[sender_id]["product_index"]
    product_list = list(product_data.keys())

    buttons = [
        {"type": "reply", "reply": {"id": p, "title": p.capitalize()}} 
        for p in product_list[start_index:start_index + 2]
    ]

    if start_index + 2 < len(product_list):
        buttons.append({"type": "reply", "reply": {"id": "next", "title": "➡️ Next"}})

    send_message(sender_id, "Choose a product:", buttons)

def send_product_info(sender_id, product_name, product_data):
    """Send Product Details"""
    product = product_data.get(product_name.lower())
    if not product:
        send_message(sender_id, "Sorry, product not found.")
        return

    product_info = (
        f"🍽 *{product_name.capitalize()}*\n"
        f"💰 Price: ₹{product['price']}\n"
        f"📜 Ingredients: {product['ingredients']}"
    )
    send_message(sender_id, product_info)

    buttons = [
        {"type": "reply", "reply": {"id": "1", "title": "Yes"}},
        {"type": "reply", "reply": {"id": "2", "title": "No"}}
    ]
    send_message(sender_id, "Would you like to see the recipe?", buttons)

def send_recipe(sender_id, product_name, product_data):
    """Send Recipe Details"""
    recipe = product_data.get(product_name.lower(), {}).get("recipe", "No recipe available.")
    send_message(sender_id, f"📖 Recipe for {product_name.capitalize()}:\n{recipe}")
    
    buttons = [
        {"type": "reply", "reply": {"id": "1", "title": "Yes"}},
        {"type": "reply", "reply": {"id": "2", "title": "No"}}
    ]
    send_message(sender_id, "Would you like to Order?", buttons)
    
import os

port = int(os.getenv("PORT", 5000))  # Use Render's PORT or default to 5000
app.run(host="0.0.0.0", port=port, debug=True)

