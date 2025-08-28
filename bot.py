import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)
import re

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define states for the conversation
WELCOME, AWAITING_TX_URL, AWAITING_IMAGE = range(3)

# Bot token from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Telegram ID or username to send the data to
RECIPIENT_USERNAME = "@Kerverossui"  # Replace with chat ID if needed

# Wallet addresses
TON_ADDRESS = "UQBW2B1gjQBydPp2qMphelacZMQ26kna4W0p0NuzDYSuJlyP"
SOL_ADDRESS = "8CvnXzMuKWN2gzAp75PeGHKqks2RhPnoVChpu7aRcVjN"

# Welcome message
WELCOME_MESSAGE = (
    "Welcome! Please send 2.5 TON or 0.06 SOL to the following addresses:\n\n"
    f"**TON**: `{TON_ADDRESS}`\n"
    f"**SOL**: `{SOL_ADDRESS}`\n\n"
    "After making the payment, please provide a valid URL for the transaction payment proof."
)

# Function to validate URL
def is_valid_url(url):
    regex = r'^(https?://)?[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$'
    return re.match(regex, url) is not None

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info(f"User {update.message.from_user.id} started the bot")
    await update.message.reply_text(WELCOME_MESSAGE, parse_mode="Markdown")
    return AWAITING_TX_URL

# Handler for transaction URL
async def handle_tx_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    url = update.message.text
    if is_valid_url(url):
        context.user_data['tx_url'] = url
        context.user_data['user_id'] = update.message.from_user.id
        context.user_data['username'] = update.message.from_user.username or "No username"
        logger.info(f"User {context.user_data['user_id']} submitted URL: {url}")
        await update.message.reply_text(
            "Thank you for providing the transaction URL. "
            "Now, please upload a square image (PNG, JPG, or GIF) with a minimum size of 200x200 pixels."
        )
        return AWAITING_IMAGE
    else:
        await update.message.reply_text("Please provide a valid URL for the transaction proof.")
        return AWAITING_TX_URL

# Handler for image
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.photo or (update.message.document and update.message.document.mime_type in ["image/png", "image/jpeg", "image/gif"]):
        # Get the file (photo or document)
        if update.message.photo:
            file = await update.message.photo[-1].get_file()
        else:
            file = await update.message.document.get_file()

        # Download the file to check dimensions
        file_path = await file.download_to_drive()
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                width, height = img.size
                if width == height and width >= 200:
                    # Prepare to send data to recipient
                    user_id = context.user_data['user_id']
                    username = context.user_data['username']
                    tx_url = context.user_data['tx_url']
                    message = (
                        f"New submission from user ID: {user_id} (Username: {username})\n"
                        f"Transaction URL: {tx_url}"
                    )

                    try:
                        # Send message to recipient
                        await context.bot.send_message(
                            chat_id=RECIPIENT_USERNAME,
                            text=message
                        )
                        # Send image to recipient
                        with open(file_path, 'rb') as image_file:
                            await context.bot.send_document(
                                chat_id=RECIPIENT_USERNAME,
                                document=image_file,
                                caption=f"Image from user ID: {user_id} (Username: {username})"
                            )
                        logger.info(f"Successfully sent data to {RECIPIENT_USERNAME} for user {user_id}")
                        await update.message.reply_text(
                            "Image received successfully! All information has been sent to @Kerverossui. Thank you for completing the process."
                        )
                    except Exception as e:
                        logger.error(f"Failed to send data to {RECIPIENT_USERNAME}: {e}")
                        await update.message.reply_text(
                            "Image received, but there was an error sending the information to @Kerverossui. Please contact support."
                        )
                    finally:
                        file_path.unlink()  # Clean up the downloaded file
                    return ConversationHandler.END
                else:
                    await update.message.reply_text(
                        "The image must be square (equal width and height) and at least 200x200 pixels. Please upload a valid image."
                    )
                    file_path.unlink()
                    return AWAITING_IMAGE
        except Exception as e:
            logger.error(f"Error processing image for user {update.message.from_user.id}: {e}")
            await update.message.reply_text("Error processing the image. Please try again.")
            file_path.unlink()
            return AWAITING_IMAGE
    else:
        await update.message.reply_text(
            "Please upload a valid image (PNG, JPG, or GIF)."
        )
        return AWAITING_IMAGE

# Cancel command handler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info(f"User {update.message.from_user.id} cancelled the operation")
    await update.message.reply_text("Operation cancelled. You can start again with /start.")
    return ConversationHandler.END

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error: {context.error}")
    if update and update.message:
        await update.message.reply_text("An error occurred. Please try again or contact support.")

def main() -> None:
    # Check if BOT_TOKEN is set
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable not set")
        raise ValueError("BOT_TOKEN environment variable not set")

    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Define the conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            AWAITING_TX_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_tx_url)
            ],
            AWAITING_IMAGE: [
                MessageHandler(
                    filters.PHOTO | filters.Document.IMAGE | filters.Document.GIF,
                    handle_image
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Add handlers
    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)

    # Start the bot
    logger.info("Starting bot polling")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
