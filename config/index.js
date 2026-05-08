require('dotenv').config();

module.exports = {
  TELEGRAM_BOT_TOKEN: process.env.TELEGRAM_BOT_TOKEN,
  GEMINI_API_KEY: process.env.GEMINI_API_KEY,
  OWNER_ID: process.env.OWNER_ID, // Your specific Telegram User ID to lock down the bot
};
