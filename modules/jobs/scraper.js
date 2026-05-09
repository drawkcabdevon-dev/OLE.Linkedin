const path = require('path');
const fs = require('fs');

/**
 * Lightweight Scraper using Native Node.js Fetch (No Playwright required!)
 * Optimized for Barbados job market.
 */

// Helper to fetch HTML and parse it using Regex (Fast & Lightweight)
async function fetchHtml(url) {
    try {
        const response = await fetch(url, {
            headers: {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            },
            signal: AbortSignal.timeout(15000)
        });
        if (!response.ok) return null;
        return await response.text();
    } catch (e) {
        console.error(`  [Fetch Error] ${url}: ${e.message}`);
        return null;
    }
}

const scrapeLinkedIn = async () => {
    // LinkedIn heavily blocks non-browser traffic, but we can try a basic public search URL
    const url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=Marketing&location=Barbados&f_AL=true";
    console.log("  [LinkedIn] Fetching lightweight guest feed...");
    
    const html = await fetchHtml(url);
    if (!html) return [];

    const results = [];
    // Basic regex to find job IDs and titles in the guest feed
    const jobMatches = [...html.matchAll(/job-search-card__title">([\s\S]*?)<\/h3>[\s\S]*?href="(.*?)"/g)];
    
    for (const match of jobMatches.slice(0, 5)) {
        const title = match[1].trim();
        const fullUrl = match[2].split('?')[0];
        const jobId = fullUrl.split('-').pop();

        results.push({
            id: `li_${jobId}`,
            title,
            company: "LinkedIn Lead",
            url: fullUrl,
            summary: `${title} - Real-time lead from LinkedIn Barbados.`,
            location: "Barbados",
            source: "LinkedIn"
        });
    }
    return results;
};

const scrapeCaribbeanJobs = async () => {
    const url = "https://www.caribbeanjobs.com/ShowResults.aspx?Keywords=Marketing&Location=Barbados";
    console.log("  [CaribbeanJobs] Fetching...");
    
    const html = await fetchHtml(url);
    if (!html) return [];

    const results = [];
    // Regex to find job titles and links
    const jobMatches = [...html.matchAll(/<h2><a href="(.*?)">(.*?)<\/a><\/h2>/g)];
    
    for (const match of jobMatches.slice(0, 5)) {
        const href = match[1];
        const title = match[2].trim();
        const fullUrl = href.startsWith('http') ? href : `https://www.caribbeanjobs.com${href}`;

        results.push({
            id: `cj_${Math.random().toString(36).substr(2, 5)}`,
            title,
            company: "Caribbean Employer",
            url: fullUrl,
            summary: `${title} - Marketing vacancy in Barbados via CaribbeanJobs.`,
            location: "Barbados",
            source: "CaribbeanJobs"
        });
    }
    return results;
};

const scrapeBarbadosJobRegister = async () => {
    const url = "https://barbadosjobregister.gov.bb/vacancy/search?search=marketing";
    console.log("  [GovRegister] Fetching...");
    
    const html = await fetchHtml(url);
    if (!html) return [];

    const results = [];
    // Find vacancy titles and links
    const jobMatches = [...html.matchAll(/href="(\/vacancy\/view\/.*?)"[\s\S]*?>(.*?)<\/a>/g)];

    for (const match of jobMatches.slice(0, 5)) {
        const href = match[1];
        const title = match[2].trim();
        if (title.includes('<')) continue; // Skip HTML noise

        results.push({
            id: `bjr_${Math.random().toString(36).substr(2, 5)}`,
            title,
            company: "Barbados Government Lead",
            url: `https://barbadosjobregister.gov.bb${href}`,
            summary: `${title} - Local Barbadian vacancy.`,
            location: "Barbados",
            source: "BarbadosJobRegister"
        });
    }
    return results;
};

const scrapeJobs = async () => {
    console.log("\n🚀 Starting ultra-lightweight job scrape...");
    
    const [li, cj, bjr] = await Promise.all([
        scrapeLinkedIn(),
        scrapeCaribbeanJobs(),
        scrapeBarbadosJobRegister()
    ]);

    const all = [...li, ...cj, ...bjr];
    console.log(`✅ Scrape complete. Found ${all.length} jobs.\n`);
    return all;
};

module.exports = { scrapeJobs };
