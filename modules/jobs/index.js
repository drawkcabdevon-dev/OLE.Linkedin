const { scrapeJobs } = require('./scraper');

// We will keep track of jobs globally in memory for now so the user can "Apply" to them
const jobCache = new Map();

module.exports = (bot) => {
    
    // Command to trigger the job search
    bot.onText(/\/findjobs/, async (msg) => {
        const chatId = msg.chat.id;
        
        bot.sendMessage(chatId, '🔍 Initializing scraper... Looking for Marketing jobs in Barbados...');
        
        try {
            // Call the scraper (we will build this next)
            const jobs = await scrapeJobs();
            
            if (jobs.length === 0) {
                bot.sendMessage(chatId, 'No new jobs found today.');
                return;
            }

            // Send each job to the user with an inline keyboard
            for (const job of jobs) {
                // Save to cache using a unique ID so we can reference it if they click "Apply"
                const jobId = `job_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
                jobCache.set(jobId, job);

                const messageText = `🏢 *${job.company}*\n` +
                                    `💼 *${job.title}*\n\n` +
                                    `${job.summary}\n\n` +
                                    `📍 ${job.location}\n` +
                                    `🔗 [View Original](${job.url})`;

                const options = {
                    parse_mode: 'Markdown',
                    reply_markup: {
                        inline_keyboard: [
                            [
                                { text: '✅ Apply with AI', callback_data: `apply_${jobId}` },
                                { text: '❌ Skip', callback_data: `skip_${jobId}` }
                            ]
                        ]
                    }
                };

                await bot.sendMessage(chatId, messageText, options);
            }
            
        } catch (error) {
            console.error(error);
            bot.sendMessage(chatId, '❌ An error occurred while scraping for jobs.');
        }
    });

    // Handle button clicks (Apply or Skip)
    bot.on('callback_query', async (query) => {
        const chatId = query.message.chat.id;
        const data = query.data;

        if (data.startsWith('skip_')) {
            // Delete the message to clean up the chat
            bot.deleteMessage(chatId, query.message.message_id);
            bot.answerCallbackQuery(query.id, { text: 'Job skipped.' });
        } 
        else if (data.startsWith('apply_')) {
            const jobId = data.replace('apply_', '');
            const jobData = jobCache.get(jobId);

            if (!jobData) {
                bot.answerCallbackQuery(query.id, { text: 'Job data expired or not found.' });
                return;
            }

            bot.answerCallbackQuery(query.id, { text: 'Starting application process...' });
            
            // Send an initial status message
            const statusMsg = await bot.sendMessage(chatId, `📝 Generating custom cover letter for *${jobData.title}* at *${jobData.company}*...`, { parse_mode: 'Markdown' });

            try {
                // TODO: 1. Generate Cover Letter via Gemini
                // TODO: 2. Save Cover Letter to file
                // TODO: 3. Execute Google Workspace CLI to draft email with Cover Letter & CV attached
                
                // Simulate delay for now
                setTimeout(() => {
                    bot.editMessageText(`✅ Success! I have drafted an email for the *${jobData.title}* position. Please check your Gmail drafts.`, {
                        chat_id: chatId,
                        message_id: statusMsg.message_id,
                        parse_mode: 'Markdown'
                    });
                }, 3000);

            } catch (error) {
                console.error(error);
                bot.editMessageText(`❌ Failed to draft the application.`, {
                    chat_id: chatId,
                    message_id: statusMsg.message_id
                });
            }
        }
    });
};
