import os
import logging
import random
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler, InlineQueryHandler
from database import Database
from sqlalchemy.exc import SQLAlchemyError
from scraper import get_product_details, is_valid_amazon_url
from aiohttp import web

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize database
db = Database()

# Store admin user IDs
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

# Dictionary to store products (will be loaded from MongoDB)
PRODUCTS = {}

# Get environment variables
PORT = int(os.getenv('PORT', 8080))
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development').lower()
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')

def load_products_from_db():
    """Load products from MongoDB into memory."""
    global PRODUCTS
    try:
        # Get all categories first
        categories = db.get_all_categories()
        
        # Initialize PRODUCTS with empty lists for all categories
        PRODUCTS = {category: [] for category in categories}
        
        # Get all products from database
        all_products = db.get_all_products()
        
        # Organize products by category
        for product in all_products:
            category = product['category']
            # Convert MongoDB _id to string for JSON serialization
            product['_id'] = str(product['_id'])
            if category in PRODUCTS:
                PRODUCTS[category].append(product)
            else:
                # If category doesn't exist (shouldn't happen), create it
                PRODUCTS[category] = [product]
        
        logger.info(f"Loaded {len(all_products)} products across {len(categories)} categories")
    except Exception as e:
        logger.error(f"Error loading products from database: {e}")
        # Don't clear PRODUCTS on error
        return

def is_admin(user_id):
    """Check if user is an admin."""
    return user_id in ADMIN_IDS

# Predefined products with affiliate links
PRODUCTS = {
    'Electronics': [
        {
            'title': 'boAt Airdopes 141 Bluetooth TWS Earbuds',
            'price': '₹1,299',
            'original_price': '₹4,499',
            'discount': '71%',
            'rating': '4.1',
            'reviews': '12,543',
            'description': '42H playtime, ENx™ Technology, ASAP™ Charge, IWP™ Technology, 8mm drivers',
            'features': [
                'Up to 42 Hours Total Playback',
                'ENx™ Technology for Clear Calls',
                'ASAP™ Charge - 10 mins = 75 mins',
                'IPX4 Water Resistance'
            ],
            'image_url': 'https://m.media-amazon.com/images/I/61KNJav3S9L._SX522_.jpg',
            'link': 'https://amzn.to/yourlink1'  # Replace with your actual affiliate link
        },
        {
            'title': 'OnePlus Nord Buds 2',
            'price': '₹2,999',
            'original_price': '₹3,999',
            'discount': '25%',
            'rating': '4.2',
            'reviews': '8,876',
            'description': 'Active Noise Cancellation, Spatial Audio, 12.4mm drivers, Up to 36hrs battery',
            'features': [
                'Up to 36 Hours Battery Life',
                'Active Noise Cancellation up to 25db',
                'IP55 Dust and Water Resistance',
                'Super Fast Charging'
            ],
            'image_url': 'https://m.media-amazon.com/images/I/51oxrEYhYQL._SL1500_.jpg',
            'link': 'https://amzn.to/yourlink2'  # Replace with your actual affiliate link
        }
    ],
    'Fashion': [
        {
            'title': 'Allen Solly Men Regular Fit Shirt',
            'price': '₹799',
            'original_price': '₹1,599',
            'discount': '50%',
            'rating': '4.0',
            'reviews': '2,345',
            'description': 'Regular Fit Cotton Shirt, Perfect for Office Wear',
            'features': [
                '100% Premium Cotton',
                'Regular Collar',
                'Machine Wash',
                'Perfect for Formal & Casual Wear'
            ],
            'image_url': 'https://m.media-amazon.com/images/I/61N6Ls3K8iL._UY679_.jpg',
            'link': 'https://amzn.to/yourlink3'  # Replace with your actual affiliate link
        }
    ],
    'Home': [
        {
            'title': 'Wipro Smart LED Bulb',
            'price': '₹499',
            'rating': '4.3',
            'link': f'https://www.amazon.in/dp/B07PYJJ898?tag=krunalweb20-21'
        }
    ]
}

WELCOME_MESSAGE = """🎉 Welcome to Amazon Deals Bot! 🛍️

I'm here to help you discover amazing deals on Amazon products! 

Commands you can use:
/deals - Get random product deals
/category - Browse products by category
/help - Show this help message

Every purchase you make through our links helps support us! 🙏
"""

HELP_MESSAGE = """🤖 Available Commands:

/start - Start the bot
/deals - Get random product deals
/category - Browse products by category
/help - Show this help message

Admin Commands:
/link [amazon_url] - Add product from Amazon URL
/remove [product_id] - Remove a product
/list - List all products

Happy shopping! 🛍️"""

ADMIN_HELP = """🔐 Admin Commands:

/link [amazon_url] - Add new product using Amazon URL
/remove [product_id] - Remove a product
/list - List all products with their IDs
/category_add [category] - Add new category
/category_remove [category] - Remove category

Example:
/link https://www.amazon.in/dp/XXXXX"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message when /start command is issued."""
    user = update.effective_user
    try:
        db.add_user(user.id, user.username or "Unknown", datetime.now())
        await update.message.reply_text(WELCOME_MESSAGE)
        if is_admin(user.id):
            await update.message.reply_text(ADMIN_HELP)
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        await update.message.reply_text("An error occurred. Please try again later.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message when /help command is issued."""
    if is_admin(update.effective_user.id):
        await update.message.reply_text(HELP_MESSAGE + "\n\n" + ADMIN_HELP)
    else:
        await update.message.reply_text(HELP_MESSAGE)

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add product from Amazon URL."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is only for admins.")
        return

    if not context.args:
        await update.message.reply_text("❌ Please provide an Amazon product URL.\nExample: /link https://www.amazon.in/dp/XXXXX")
        return

    url = context.args[0]
    if not is_valid_amazon_url(url):
        await update.message.reply_text("❌ Invalid Amazon URL. Please provide a valid Amazon product URL.")
        return

    status_message = await update.message.reply_text("🔄 Fetching product details...")
    
    try:
        product_data = get_product_details(url)
        if not product_data:
            await status_message.edit_text("❌ Failed to fetch product details. This could be because:\n"
                                        "1. The product page is not accessible\n"
                                        "2. The product is out of stock\n"
                                        "3. Amazon's anti-bot protection is active\n\n"
                                        "Please try again in a few minutes.")
            return
        
        # Determine category
        if len(context.args) > 1:
            category = context.args[1].capitalize()
        else:
            # Ask for category
            categories = db.get_all_categories() or ['Electronics', 'Fashion', 'Home']
            category_list = "\n".join([f"🔹 {cat}" for cat in categories])
            await status_message.edit_text(
                f"Please specify a category for this product:\n\n{category_list}\n\n"
                "Use: /link [url] [category]"
            )
            return

        # Add product to database
        product_id = db.add_product(product_data, category)
        if not product_id:
            await status_message.edit_text("❌ Failed to add product to database. Please try again.")
            return

        # Reload products from database
        load_products_from_db()

        # Send preview
        try:
            message, keyboard = format_product_message(product_data)
            if 'image_url' in product_data:
                await update.message.reply_photo(
                    photo=product_data['image_url'],
                    caption=message,
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
            else:
                await update.message.reply_text(
                    text=message,
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
            await status_message.edit_text(f"✅ Product added to {category} category!")
        except Exception as e:
            logger.error(f"Error sending product message: {e}")
            await status_message.edit_text("✅ Product added, but there was an error displaying it. "
                                         "The product has been saved and will appear in deals.")
            
    except Exception as e:
        logger.error(f"Error in add_product: {e}")
        await status_message.edit_text("❌ An error occurred while processing the product. Please try again.")

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all products with their IDs."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is only for admins.")
        return

    if not PRODUCTS:
        await update.message.reply_text("No products available.")
        return

    message = "📦 Product List:\n\n"
    for category, products in PRODUCTS.items():
        message += f"📂 {category}:\n"
        for i, product in enumerate(products):
            message += f"{i+1}. {product['title'][:50]}...\n"
        message += "\n"

    await update.message.reply_text(message)

async def remove_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a product."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is only for admins.")
        return

    if not context.args or len(context.args) != 2:
        await update.message.reply_text("❌ Please provide category and product number.\nExample: /remove Electronics 1")
        return

    category = context.args[0].capitalize()
    try:
        index = int(context.args[1]) - 1
        if category in PRODUCTS and 0 <= index < len(PRODUCTS[category]):
            product = PRODUCTS[category][index]
            if db.remove_product(product['_id']):
                # Reload products from database
                load_products_from_db()
                await update.message.reply_text(f"✅ Removed: {product['title']}")
            else:
                await update.message.reply_text("❌ Failed to remove product from database.")
        else:
            await update.message.reply_text("❌ Invalid category or product number.")
    except ValueError:
        await update.message.reply_text("❌ Invalid product number.")

def format_product_message(product_data):
    """Format product data into a nice message with modern formatting."""
    if not product_data:
        return "Sorry, I couldn't fetch the product details. Please try again with a different link."

    # Start with the product image if available
    message = ""
    if product_data.get('image_url'):
        message += f"<a href='{product_data['image_url']}'>&#8205;</a>"

    # Add title with link
    title = product_data.get('title', 'Product Title Not Available')
    message += f"<b>🛍️ {title}</b>\n\n"

    # Price section with original price and discount if available
    price_section = []
    if product_data.get('price'):
        current_price = f"<b>Price: {product_data['price']}</b>"
        price_section.append(current_price)
        
        if product_data.get('original_price'):
            original_price = f"M.R.P: {product_data['original_price']}"
            price_section.append(original_price)
            
        if product_data.get('discount'):
            discount = f"🏷️ <b>Save {product_data['discount']}</b>"
            price_section.append(discount)
    
    message += "\n".join(price_section) + "\n\n"

    # Rating and reviews section
    if product_data.get('rating') or product_data.get('reviews'):
        rating_section = []
        if product_data.get('rating'):
            stars = "⭐" * round(float(product_data['rating']))
            rating_section.append(f"{stars} ({product_data['rating']})")
        if product_data.get('reviews'):
            rating_section.append(f"📊 {product_data['reviews']} reviews")
        message += " | ".join(rating_section) + "\n\n"

    # Description or features
    if product_data.get('description'):
        message += f"📝 <i>{product_data['description'][:200]}...</i>\n\n"
    elif product_data.get('features'):
        message += "✨ <b>Highlights:</b>\n"
        for feature in product_data['features'][:3]:
            message += f"• {feature}\n"
        message += "\n"

    # Add Buy Now button using inline keyboard markup
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Buy Now", url=product_data.get('link'))]
    ])

    return message, keyboard

async def send_deals(message_obj, context: ContextTypes.DEFAULT_TYPE):
    """Send deals to chat. Works with both regular messages and callback queries."""
    # Check if there are any products
    total_products = sum(len(products) for products in PRODUCTS.values())
    if total_products == 0:
        await message_obj.reply_text("😔 No deals available at the moment. Please check back later!")
        return

    # Send a nice header message with inline keyboard for categories
    category_buttons = []
    row = []
    for category in PRODUCTS.keys():
        if len(row) == 2:  # Create rows of 2 buttons
            category_buttons.append(row)
            row = []
        row.append(InlineKeyboardButton(f"📂 {category}", callback_data=f"cat_{category.lower()}"))
    if row:  # Add any remaining buttons
        category_buttons.append(row)

    header_keyboard = InlineKeyboardMarkup(category_buttons)
    await message_obj.reply_text(
        "🔥 *HOT DEALS OF THE DAY* 🔥\n\n"
        "Check out these amazing offers! 🎉\n"
        "Click on categories below to see more deals 👇",
        parse_mode='Markdown',
        reply_markup=header_keyboard
    )
    
    # Get all available products
    all_products = []
    for category, products in PRODUCTS.items():
        for product in products:
            product['category'] = category  # Add category to product info
            all_products.append(product)
    
    if not all_products:
        return
    
    # Shuffle and select up to 5 random products
    random.shuffle(all_products)
    selected_products = all_products[:5]
    
    # Send products with delay to avoid rate limiting
    for product in selected_products:
        try:
            message, keyboard = format_product_message(product)
            
            # Add category tag and time to message
            current_time = datetime.now().strftime("%I:%M %p")
            message = f"{message}\n📂 Category: #{product['category']}\n⏰ Updated: {current_time}"
            
            # Add additional buttons
            share_button = InlineKeyboardButton("📤 Share Deal", switch_inline_query=f"deal_{product.get('title', 'Amazing Deal')}")
            more_button = InlineKeyboardButton("🔍 More Deals", callback_data=f"more_{product['category'].lower()}")
            
            # Get existing keyboard buttons and add new ones
            existing_buttons = keyboard.inline_keyboard[0] if keyboard.inline_keyboard else []
            new_row = [share_button, more_button]
            new_keyboard = InlineKeyboardMarkup([existing_buttons, new_row])
            
            if 'image_url' in product:
                await message_obj.reply_photo(
                    photo=product['image_url'],
                    caption=message,
                    parse_mode='HTML',
                    reply_markup=new_keyboard
                )
            else:
                await message_obj.reply_text(
                    text=message,
                    parse_mode='HTML',
                    reply_markup=new_keyboard
                )
            
            # Add small delay between messages
            await asyncio.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error formatting product: {e}")
            continue
    
    # Send footer message
    footer_buttons = [
        [
            InlineKeyboardButton("🔄 Refresh Deals", callback_data="refresh_deals"),
            InlineKeyboardButton("📱 Share Bot", url=f"https://t.me/share/url?url=Check%20out%20this%20amazing%20deals%20bot!&text=Join%20@{context.bot.username}")
        ]
    ]
    footer_keyboard = InlineKeyboardMarkup(footer_buttons)
    
    await message_obj.reply_text(
        "🎯 *Want More Deals?*\n\n"
        "• Use /category to browse by category\n"
        "• Click Refresh Deals for new offers\n"
        "• Share with friends to support us!\n\n"
        "_Prices and offers may change. Please check final price before ordering._",
        parse_mode='Markdown',
        reply_markup=footer_keyboard
    )

async def deals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send random product deals when /deals command is issued."""
    await send_deals(update.message, context)

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show products by category."""
    categories = list(PRODUCTS.keys())
    category_list = "\n".join([f"🔹 {cat}" for cat in categories])
    
    message = f"""📂 Available Categories:

{category_list}

To view products, use:
/category_name (e.g., /electronics)"""
    
    await update.message.reply_text(message)

async def category_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show products from a specific category."""
    category_name = update.message.text[1:].capitalize()  # Remove / and capitalize
    
    if category_name in PRODUCTS:
        await update.message.reply_text(f"🔍 Showing products in {category_name}...")
        
        for product in PRODUCTS[category_name]:
            try:
                message, keyboard = format_product_message(product)
                if 'image_url' in product:
                    await update.message.reply_photo(
                        photo=product['image_url'],
                        caption=message,
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
                else:
                    await update.message.reply_text(
                        text=message,
                        parse_mode='HTML',
                        reply_markup=keyboard
                    )
            except Exception as e:
                logger.error(f"Error formatting product: {e}")
                continue
    else:
        await update.message.reply_text("❌ Category not found. Use /category to see available categories.")

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses."""
    query = update.callback_query
    await query.answer()  # Answer the callback query to remove the loading state

    if query.data.startswith("cat_"):
        # Handle category selection
        category = query.data[4:].capitalize()
        if category in PRODUCTS:
            await query.message.reply_text(f"🔍 Showing deals from {category}...")
            for product in PRODUCTS[category]:
                try:
                    message, keyboard = format_product_message(product)
                    current_time = datetime.now().strftime("%I:%M %p")
                    message = f"{message}\n📂 Category: #{category}\n⏰ Updated: {current_time}"
                    
                    # Add share button
                    share_button = InlineKeyboardButton("📤 Share Deal", switch_inline_query=f"deal_{product.get('title', 'Amazing Deal')}")
                    existing_buttons = keyboard.inline_keyboard[0] if keyboard.inline_keyboard else []
                    new_keyboard = InlineKeyboardMarkup([existing_buttons, [share_button]])
                    
                    if 'image_url' in product:
                        await query.message.reply_photo(
                            photo=product['image_url'],
                            caption=message,
                            parse_mode='HTML',
                            reply_markup=new_keyboard
                        )
                    else:
                        await query.message.reply_text(
                            text=message,
                            parse_mode='HTML',
                            reply_markup=new_keyboard
                        )
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error sending product: {e}")
                    continue

    elif query.data == "refresh_deals":
        # Delete the original message and send new deals
        try:
            await query.message.delete()
        except Exception as e:
            logger.error(f"Error deleting message: {e}")
        
        # Send new deals using the query.message
        await send_deals(query.message, context)

    elif query.data.startswith("more_"):
        # Show more deals from the same category
        category = query.data[5:].capitalize()
        if category in PRODUCTS:
            products = PRODUCTS[category]
            random.shuffle(products)
            await query.message.reply_text(f"📦 More deals from {category}:")
            
            for product in products[:3]:  # Show 3 more products
                try:
                    message, keyboard = format_product_message(product)
                    current_time = datetime.now().strftime("%I:%M %p")
                    message = f"{message}\n📂 Category: #{category}\n⏰ Updated: {current_time}"
                    
                    share_button = InlineKeyboardButton("📤 Share Deal", switch_inline_query=f"deal_{product.get('title', 'Amazing Deal')}")
                    existing_buttons = keyboard.inline_keyboard[0] if keyboard.inline_keyboard else []
                    new_keyboard = InlineKeyboardMarkup([existing_buttons, [share_button]])
                    
                    if 'image_url' in product:
                        await query.message.reply_photo(
                            photo=product['image_url'],
                            caption=message,
                            parse_mode='HTML',
                            reply_markup=new_keyboard
                        )
                    else:
                        await query.message.reply_text(
                            text=message,
                            parse_mode='HTML',
                            reply_markup=new_keyboard
                        )
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error sending product: {e}")
                    continue

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline queries for sharing deals."""
    query = update.inline_query.query
    
    if not query:  # If no specific query, show random deals
        results = []
        all_products = []
        
        # Collect all products
        for category, products in PRODUCTS.items():
            for product in products:
                product['category'] = category
                all_products.append(product)
        
        # Shuffle and select up to 5 products
        random.shuffle(all_products)
        selected_products = all_products[:5]
        
        for idx, product in enumerate(selected_products):
            # Create message text
            message_text = f"🔥 *{product.get('title', 'Amazing Deal')}*\n\n"
            
            if product.get('price'):
                message_text += f"💰 *Price:* {product['price']}\n"
            if product.get('original_price'):
                message_text += f"📌 *M.R.P:* ~{product['original_price']}~\n"
            if product.get('discount'):
                message_text += f"🏷️ *Save:* {product['discount']}\n"
            if product.get('rating'):
                stars = "⭐" * round(float(product['rating']))
                message_text += f"\n{stars} ({product['rating']})"
            if product.get('reviews'):
                message_text += f" | 📊 {product['reviews']} reviews\n"
            
            message_text += f"\n🛒 *Buy Now:* {product.get('link')}\n\n"
            message_text += f"📂 Category: #{product['category']}"
            
            results.append(
                InlineQueryResultArticle(
                    id=str(idx),
                    title=product.get('title', 'Amazing Deal'),
                    description=f"💰 {product.get('price', 'Check price')} | 📂 {product['category']}",
                    thumb_url=product.get('image_url') if product.get('image_url') else None,
                    input_message_content=InputTextMessageContent(
                        message_text=message_text,
                        parse_mode='Markdown'
                    ),
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🛒 Buy Now", url=product.get('link')),
                        InlineKeyboardButton("🤖 More Deals", url=f"https://t.me/{context.bot.username}")
                    ]])
                )
            )
    else:  # Search for specific product
        # Extract deal identifier if it starts with "deal_"
        if query.startswith("deal_"):
            product_title = query[5:]  # Remove "deal_" prefix
            results = []
            
            # Search for the product
            for category, products in PRODUCTS.items():
                for product in products:
                    if product.get('title', '').lower() == product_title.lower():
                        message_text = f"🔥 *{product.get('title', 'Amazing Deal')}*\n\n"
                        
                        if product.get('price'):
                            message_text += f"💰 *Price:* {product['price']}\n"
                        if product.get('original_price'):
                            message_text += f"📌 *M.R.P:* ~{product['original_price']}~\n"
                        if product.get('discount'):
                            message_text += f"🏷️ *Save:* {product['discount']}\n"
                        if product.get('rating'):
                            stars = "⭐" * round(float(product['rating']))
                            message_text += f"\n{stars} ({product['rating']})"
                        if product.get('reviews'):
                            message_text += f" | 📊 {product['reviews']} reviews\n"
                        
                        message_text += f"\n🛒 *Buy Now:* {product.get('link')}\n\n"
                        message_text += f"📂 Category: #{category}"
                        
                        results.append(
                            InlineQueryResultArticle(
                                id='1',
                                title=product.get('title', 'Amazing Deal'),
                                description=f"💰 {product.get('price', 'Check price')} | 📂 {category}",
                                thumb_url=product.get('image_url') if product.get('image_url') else None,
                                input_message_content=InputTextMessageContent(
                                    message_text=message_text,
                                    parse_mode='Markdown'
                                ),
                                reply_markup=InlineKeyboardMarkup([[
                                    InlineKeyboardButton("🛒 Buy Now", url=product.get('link')),
                                    InlineKeyboardButton("🤖 More Deals", url=f"https://t.me/{context.bot.username}")
                                ]])
                            )
                        )
                        break
                if results:
                    break
    
    await update.inline_query.answer(results, cache_time=1)

async def ping_service(context: ContextTypes.DEFAULT_TYPE):
    """Periodic task to keep the bot alive and check database connection."""
    try:
        # Get the chat ID from environment variable or use a default admin ID
        ping_chat_id = int(os.getenv('PING_CHAT_ID', ADMIN_IDS[0] if ADMIN_IDS else None))
        
        if not ping_chat_id:
            logger.warning("No ping chat ID configured. Ping service will run silently.")
            return

        # Check MongoDB connection
        try:
            # Try to ping MongoDB
            db.ping()
            db_status = "✅ Connected"
        except Exception as e:
            db_status = f"❌ Error: {str(e)}"
            # Try to reconnect to database
            try:
                db.reconnect()
                db_status += "\n♻️ Reconnected successfully"
            except Exception as e:
                db_status += f"\n❌ Reconnection failed: {str(e)}"

        # Get bot statistics
        stats = {
            "uptime": datetime.now() - context.bot_data.get("start_time", datetime.now()),
            "products": sum(len(products) for products in PRODUCTS.values()),
            "categories": len(PRODUCTS),
            **db.get_user_stats()
        }

        # Format status message
        status_message = (
            "🤖 *Bot Status Report*\n\n"
            f"🕒 Uptime: {str(stats['uptime']).split('.')[0]}\n"
            f"📊 Database: {db_status}\n\n"
            f"📦 Products: {stats['products']}\n"
            f"📂 Categories: {stats['categories']}\n"
            f"👥 Total Users: {stats['total_users']}\n"
            f"📱 Active Today: {stats['active_today']}\n\n"
            f"🔄 Last Check: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        # Send status message silently (without notification)
        await context.bot.send_message(
            chat_id=ping_chat_id,
            text=status_message,
            parse_mode='Markdown',
            disable_notification=True
        )

        # Reload products from database periodically
        load_products_from_db()
        
        logger.info("Ping service completed successfully")
    except Exception as e:
        logger.error(f"Error in ping service: {e}")

# Create web app for health check
async def health_check(request):
    """Health check endpoint for Render."""
    return web.Response(text='Bot is running!')

async def web_app():
    """Create web app for health check."""
    app = web.Application()
    app.router.add_get('/', health_check)
    return app

async def start_web_app():
    """Start the web application."""
    app = await web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"Web app started on port {PORT}")

async def category_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a new category."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is only for admins.")
        return

    if not context.args:
        await update.message.reply_text("❌ Please provide a category name.\nExample: /category_add Electronics")
        return

    category = context.args[0].capitalize()
    try:
        # Check if category already exists
        if category in PRODUCTS:
            await update.message.reply_text(f"❌ Category '{category}' already exists!")
            return

        # Add category to database
        if db.add_category(category):
            # Initialize empty product list for new category
            PRODUCTS[category] = []
            await update.message.reply_text(f"✅ Category '{category}' added successfully!")
        else:
            await update.message.reply_text("❌ Failed to add category. Please try again.")

    except Exception as e:
        logger.error(f"Error adding category: {e}")
        await update.message.reply_text("❌ An error occurred while adding the category.")

async def category_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a category and all its products."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ This command is only for admins.")
        return

    if not context.args:
        await update.message.reply_text("❌ Please provide a category name.\nExample: /category_remove Electronics")
        return

    category = context.args[0].capitalize()
    try:
        # Check if category exists
        if category not in PRODUCTS:
            await update.message.reply_text(f"❌ Category '{category}' does not exist!")
            return

        # Get number of products in category
        num_products = len(PRODUCTS[category])

        # Check if this is a confirmation command
        is_confirmation = len(context.args) > 1 and context.args[1].lower() == 'confirm'
        
        # If category has products and this is not a confirmation, ask for confirmation
        if num_products > 0 and not is_confirmation:
            await update.message.reply_text(
                f"⚠️ Category '{category}' has {num_products} products.\n"
                "All products in this category will be deleted.\n"
                f"To confirm, use: /category_remove {category} confirm"
            )
            return
        
        # Proceed with removal (either empty category or confirmed)
        if db.remove_category(category):
            # Remove category from memory
            del PRODUCTS[category]
            if num_products > 0:
                await update.message.reply_text(
                    f"✅ Category '{category}' and its {num_products} products have been removed successfully!"
                )
            else:
                await update.message.reply_text(f"✅ Category '{category}' removed successfully!")
            
            # Reload products from database to ensure sync
            load_products_from_db()
        else:
            await update.message.reply_text("❌ Failed to remove category. Please try again.")

    except Exception as e:
        logger.error(f"Error removing category: {e}")
        await update.message.reply_text("❌ An error occurred while removing the category.")

async def main():
    """Start the bot."""
    try:
        # Load products from database at startup
        load_products_from_db()
        
        # Create the Application
        application = (
            Application.builder()
            .token(os.getenv('TELEGRAM_BOT_TOKEN'))
            .concurrent_updates(True)
            .build()
        )

        # Store start time
        application.bot_data["start_time"] = datetime.now()

        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("deals", deals))
        application.add_handler(CommandHandler("category", show_categories))
        
        # Admin commands
        application.add_handler(CommandHandler("link", add_product))
        application.add_handler(CommandHandler("list", list_products))
        application.add_handler(CommandHandler("remove", remove_product))
        application.add_handler(CommandHandler("category_add", category_add))
        application.add_handler(CommandHandler("category_remove", category_remove))
        
        # Add category handlers
        for category in PRODUCTS.keys():
            application.add_handler(CommandHandler(category.lower(), category_products))

        # Add callback query handler
        application.add_handler(CallbackQueryHandler(handle_button))
        
        # Add inline query handler
        application.add_handler(InlineQueryHandler(inline_query))

        # Add ping service job (runs every 50 seconds)
        job_queue = application.job_queue
        if job_queue:
            job_queue.run_repeating(ping_service, interval=50, first=10)
            logger.info("Ping service scheduled successfully (running every 50 seconds)")
        else:
            logger.warning("Job queue is not available. Ping service will not run.")

        if ENVIRONMENT == 'production':
            # Production mode (Render)
            logger.info("Starting bot in production mode...")
            
            # Create web app
            app = web.Application()
            app.router.add_get('/', health_check)
            
            # Set up webhook handler
            async def handle_webhook(request):
                try:
                    update = await Update.de_json(await request.json(), application.bot)
                    await application.process_update(update)
                    return web.Response(status=200)
                except Exception as e:
                    logger.error(f"Error processing webhook: {e}")
                    return web.Response(status=500)

            app.router.add_post(f'/{application.bot.token}', handle_webhook)
            
            # Set webhook URL
            webhook_url = f"{WEBHOOK_URL}/{application.bot.token}"
            await application.bot.set_webhook(webhook_url)
            logger.info(f"Webhook set to {webhook_url}")
            
            return app, application
        else:
            # Development mode (local)
            logger.info("Starting bot in development mode...")
            return None, application

    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

def run_development():
    """Run the bot in development mode."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Start the bot
        _, application = loop.run_until_complete(main())
        
        # Initialize and start the application
        loop.run_until_complete(application.initialize())
        loop.run_until_complete(application.start())
        
        # Run polling in the background
        loop.create_task(application.updater.start_polling())
        
        # Keep the bot running
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        try:
            # Cleanup
            loop.run_until_complete(application.stop())
            loop.run_until_complete(application.shutdown())
            loop.close()
            db.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def run_production():
    """Run the bot in production mode."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Start the bot and get the web app
        web_app, application = loop.run_until_complete(main())
        
        # Initialize and start the application
        loop.run_until_complete(application.initialize())
        loop.run_until_complete(application.start())
        
        # Run the web app
        web.run_app(web_app, host='0.0.0.0', port=PORT, access_log=None)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        try:
            # Cleanup
            loop.run_until_complete(application.bot.delete_webhook())
            loop.run_until_complete(application.stop())
            loop.run_until_complete(application.shutdown())
            loop.close()
            db.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

if __name__ == '__main__':
    if ENVIRONMENT == 'production':
        run_production()
    else:
        run_development() 
