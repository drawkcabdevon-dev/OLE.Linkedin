# 🤖 Modular Telegram Job Bot (Barbados Edition)

An autonomous job-application assistant designed to run on a tablet (PicoClaw/Termux) and automate the entire job hunt process in Barbados.

## 🚀 Features

- **Multi-Source Scraping:** Automatically monitors:
  - **LinkedIn:** Real-time search for "Marketing" roles in Barbados using authenticated session state.
  - **CaribbeanJobs:** Regional professional vacancies.
  - **BajanJobs:** Specifically targeting local Barbadian job boards.
- **Agentic AI Cover Letters:** Uses **Google Gemini API** and your uploaded `cv_text.txt` to write personalized, professional cover letters for every job lead.
- **Gmail Automation:** Integrates with **Google Workspace CLI (`gws`)** to create draft emails headlessly, allowing for quick manual review and sending.
- **Telegram Interface:** Interactive bot interface with buttons to browse jobs, generate letters, and draft emails from anywhere.

## 🛠️ Setup

### 1. Prerequisites
- Node.js (v18+)
- [Google Workspace CLI](https://github.com/googleworkspace/cli) installed and authenticated.
- A Telegram Bot Token from [@BotFather](https://t.me/BotFather).
- A Google Gemini API Key.

### 2. Configuration
Create a `.env` file in the root directory:
```env
TELEGRAM_BOT_TOKEN=your_token_here
GEMINI_API_KEY=your_gemini_key_here
OWNER_ID=your_telegram_id_here
```

### 3. Personal Data
- **`cv_text.txt`:** Place your full CV/Resume text here. The bot uses this to ground the AI-generated cover letters in your actual experience.
- **`linkedin_state.json`:** Export your LinkedIn session cookies to this file to allow the scraper to bypass login screens.

### 4. Installation
```bash
npm install
npx playwright install chromium
```

## 📱 Deployment (Tablet / PicoClaw)

This bot is optimized for low-resource environments like Amazon Fire Tablets running Termux.

1. **Clone the repo:**
   ```bash
   git clone https://github.com/drawkcabdevon-dev/tele-bots.git
   ```
2. **Install dependencies:**
   ```bash
   pkg update && pkg install nodejs git
   npm install
   ```
3. **Run in background:**
   ```bash
   nohup node index.js &
   ```

## 🏗️ Project Structure
- `modules/jobs/`: Core logic for scraping, cover letter generation, and Gmail drafting.
- `config/`: Centralized configuration management.
- `index.js`: Main bot entry point and Telegram command routing.

## 🇧🇧 Barbados Focus
The bot is specifically tuned to the Barbadian job market, prioritizing local boards and filtering for relevant regional roles in Marketing, Sales, and Digital sectors.

---
*Created with ❤️ for autonomous career growth.*