const TelegramBot = require('node-telegram-bot-api');
const config = require('./config');

// Initialize bot
const bot = new TelegramBot(config.TELEGRAM_BOT_TOKEN, { polling: true });

console.log('Bot is running...');

// Security Middleware: Only allow the owner to interact with the bot
// (We will set OWNER_ID in the .env file later once you get your ID)
const verifyOwner = (msg) => {
    if (config.OWNER_ID && msg.from.id.toString() !== config.OWNER_ID) {
        bot.sendMessage(msg.chat.id, 'Unauthorized user. This is a private bot.');
        return false;
    }
    return true;
};

// Handle /start command
bot.onText(/\/start/, (msg) => {
    // Optional: if (!verifyOwner(msg)) return; // Commented out until we get your OWNER_ID
    
    const chatId = msg.chat.id;
    const welcomeMessage = `Welcome to the Antigravity Productivity Hub! 🚀\n\n` +
                           `I am currently configured to run the **Job Application Module**.\n` +
                           `Use the command /findjobs to trigger a search for marketing jobs in Barbados.`;
                           
    bot.sendMessage(chatId, welcomeMessage);
});

// Register Modules
const registerJobsModule = require('./modules/jobs');
const registerSystemModule = require('./modules/system');

registerJobsModule(bot);
registerSystemModule(bot);

// Error handling
bot.on('polling_error', (error) => {
    console.error(`Polling error: ${error.code}`); 
});
