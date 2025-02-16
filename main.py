import webbrowser
import json
import random
import gspread
from google.oauth2.service_account import Credentials
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("API_KEY")
# Initialize Google Sheets API
creds = Credentials.from_service_account_file("credentials.json", scopes=["https://www.googleapis.com/auth/spreadsheets"])
client = gspread.authorize(creds)

# Google Sheet ID
sheet_id = "1AXvO6VrCOyjDQ4ChQeo6LQ1yi8roJKlpYHhL5Zl8VR4"
sheet = client.open_by_key(sheet_id)

# Fetch available hotels
def fetch_hotels():
    try:
        return [worksheet.title for worksheet in sheet.worksheets()]
    except gspread.SpreadsheetNotFound:
        print("Chatbot: Could not find the spreadsheet.")
        return []

# Fetch menu from Google Sheets
def get_menu(hotel_name):
    try:
        worksheet = sheet.worksheet(hotel_name)
        return worksheet.get_all_records()
    except Exception as e:
        print(f"Chatbot: Error fetching menu: {e}")
        return None

# Get UPI ID of the hotel from Google Sheets
def get_hotel_upi(hotel_name):
    try:
        worksheet = sheet.worksheet("UPI_IDs")  # Make sure this sheet exists
        upi_data = worksheet.get_all_records()
        for row in upi_data:
            if row["Hotel"].lower() == hotel_name.lower():
                return row["UPI_ID"]
    except Exception as e:
        print(f"Chatbot: Error fetching UPI ID: {e}")
    return None

# Place order in Google Sheets
def place_order_in_sheet(order_id, hotel_name, order_details, total_price, payment_method, transaction_id):
    try:
        worksheet = sheet.worksheet("OrderSummary")  # Ensure this sheet exists
        order_data = [order_id, *[item[0] for item in order_details], total_price, hotel_name, payment_method, transaction_id]
        worksheet.append_row(order_data)
        print(f"Chatbot: Order saved in Google Sheets with Order ID: {order_id}")
    except Exception as e:
        print(f"Chatbot: Error while saving order: {e}")

# Generate PDF receipt
def generate_receipt(hotel_name, order_details, total_price, payment_method, transaction_id):
    receipt_file = f"Receipt_{hotel_name}.pdf"
    c = canvas.Canvas(receipt_file, pagesize=letter)
    c.setFont("Helvetica", 12)

    y = 750
    c.drawString(100, y, f"Receipt - {hotel_name}")
    y -= 20
    c.drawString(100, y, "------------------------------------")
    y -= 20

    for item, price, quantity in order_details:
        c.drawString(100, y, f"{item} x{quantity}  - ₹{price * quantity:.2f}")
        y -= 20

    y -= 10
    c.drawString(100, y, f"Total: ₹{total_price:.2f}")
    y -= 20
    c.drawString(100, y, f"Payment Method: {payment_method}")
    y -= 20
    if transaction_id:
        c.drawString(100, y, f"Transaction ID: {transaction_id}")
        y -= 20
    c.drawString(100, y, "------------------------------------")
    y -= 20
    c.drawString(100, y, "Thank you for ordering!")

    c.save()
    print(f"Chatbot: Your receipt has been generated as {receipt_file}.")

# Handle UPI payment
def handle_upi_payment(hotel_name, total_price):
    upi_id = get_hotel_upi(hotel_name)
    if not upi_id:
        print("Chatbot: No UPI ID found for this hotel.")
        return None

    # Generate UPI deep link
    transaction_id = f"TXN{random.randint(100000, 999999)}"
    upi_url = f"upi://pay?pa={upi_id}&pn={hotel_name}&mc=&tid={transaction_id}&tr={transaction_id}&tn=Order Payment&am={total_price}&cu=INR"
    
    print(f"Chatbot: Redirecting to UPI payment for ₹{total_price}...")
    webbrowser.open(upi_url)  # Opens UPI app

    # Confirm payment manually
    input("Chatbot: Press Enter after completing the payment...")

    return transaction_id  # Returning generated transaction ID

# Chatbot interaction
def chatbot():
    print("Canteen Chatbot is Running! (Type 'exit' to stop)")
    
    order_id = random.randint(1000, 9999)  # Generate random order ID

    while True:
        import sys

        if len(sys.argv) > 1:
            user_input = " ".join(sys.argv[1:])  # Takes input from command-line arguments
        else:
            user_input = "start"  # Default action if no input is provided

        if user_input.lower() == "exit":
            print("Chatbot: Goodbye!")
            break

        if user_input.lower() == "start":
            print("Chatbot: Please choose an option:")
            print("1. Order")
            print("2. Track the parcel")
            print("3. Explore the hotel")
            option = input("You: ").strip().lower()
            
            if option == "order":
                hotels = fetch_hotels()
                if hotels:
                    print("Chatbot: Available hotels:")
                    for index, hotel in enumerate(hotels, 1):
                        print(f"{index}. {hotel}")
                    
                    hotel_index = input("You: Enter the hotel number: ").strip()
                    try:
                        hotel_name = hotels[int(hotel_index) - 1]
                        print(f"Chatbot: You selected {hotel_name}. Here's the menu:")

                        # Fetch menu
                        menu = get_menu(hotel_name)
                        if menu:
                            menu_dict = {item['Item'].lower(): float(item['Price']) for item in menu}
                            for item in menu:
                                print(f"{item['Item']}: ₹{item['Price']}")

                            # Take the order
                            order_details = []
                            total_price = 0
                            while True:
                                item_order = input("You: Enter the item and quantity (e.g., Dosa 2) or 'done': ").strip()
                                if item_order.lower() == "done":
                                    break
                                try:
                                    item_name, quantity = item_order.rsplit(" ", 1)
                                    quantity = int(quantity)
                                    if item_name.lower() in menu_dict:
                                        price = menu_dict[item_name.lower()]
                                        order_details.append([item_name, price, quantity])
                                        total_price += price * quantity
                                    else:
                                        print("Chatbot: Item not found.")
                                except ValueError:
                                    print("Chatbot: Invalid input. Try again.")
                                    continue

                            # Payment method
                            print("\nChatbot: Select Payment Method:")
                            print("1. UPI Payment")
                            print("2. Cash on Delivery (COD)")
                            payment_option = input("You: ").strip()

                            transaction_id = None
                            if payment_option == "1":
                                transaction_id = handle_upi_payment(hotel_name, total_price)
                                payment_method = "UPI Payment"
                            else:
                                payment_method = "Cash on Delivery (COD)"

                            # Save order
                            place_order_in_sheet(order_id, hotel_name, order_details, total_price, payment_method, transaction_id)
                            generate_receipt(hotel_name, order_details, total_price, payment_method, transaction_id)
                            print("Chatbot: Your order has been placed successfully!")
                    
                    except (ValueError, IndexError):
                        print("Chatbot: Invalid hotel selection.")
            else:
                print("Chatbot: I can only process orders right now.")
        else:
            print("Chatbot: Please type 'start' to begin.")

# Run the chatbot
chatbot()
