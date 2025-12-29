"""
The Daily Unhinged - Your daily dose of news with the BS filter engaged.

An irreverent news commentary system that fetches RSS feeds, ranks articles,
and generates George Carlin-meets-Richard Feynman style commentary using AWS Bedrock.
"""

import json
import os
import logging
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
import feedparser
import requests
import base64
import re
from collections import Counter
import math

# Configuration
BUCKET_NAME = os.environ.get('BUCKET_NAME')
BEDROCK_MODEL = os.environ.get('BEDROCK_MODEL', 'anthropic.claude-3-haiku-20240307-v1:0')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
MAX_ITEMS = int(os.environ.get('MAX_ITEMS', '25'))
EMAIL_RECIPIENT = os.environ.get('EMAIL_RECIPIENT', '')
EMAIL_SENDER = os.environ.get('EMAIL_SENDER', '')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO = os.environ.get('GITHUB_REPO', '')  # format: owner/repo

logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

# Initialize AWS clients
s3 = boto3.client('s3')
bedrock = boto3.client('bedrock-runtime')
ses = boto3.client('ses')

# ============================================
# RSS FEEDS - Organized by Category
# ============================================

RSS_FEEDS = {
    'india': [
        # Economic Times
        'https://economictimes.indiatimes.com/news/rssfeeds/1715249553.cms',
        'https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms',
        'https://economictimes.indiatimes.com/news/politics-and-nation/rssfeeds/1052732854.cms',
        # LiveMint
        'https://www.livemint.com/rss/news',
        'https://www.livemint.com/rss/companies',
        'https://www.livemint.com/rss/AI',
        # The Hindu
        'https://www.thehindu.com/business/feeder/default.rss',
        'https://www.thehindu.com/business/Economy/feeder/default.rss',
        # Others
        'https://www.business-standard.com/rss/latest.rss',
        'https://www.moneycontrol.com/rss/business.xml',
        'https://www.moneycontrol.com/rss/economy.xml',
        'https://indianexpress.com/section/business/feed/',
        'https://indianexpress.com/section/political-pulse/feed/',
    ],
    'us': [
        # NPR
        'https://feeds.npr.org/1006/rss.xml',  # Business
        'https://feeds.npr.org/1014/rss.xml',  # Politics
        'https://feeds.npr.org/1017/rss.xml',  # Economy
        # Political
        'https://thehill.com/feed/',
        'https://thehill.com/business/feed/',
        'https://www.politico.com/rss/politicopicks.xml',
        'https://www.politico.com/rss/congress.xml',
        # Others
        'https://rsshub.app/reuters/business',
        'http://feeds.feedburner.com/NationPBSNewsHour',
    ],
    'china': [
        # South China Morning Post
        'https://www.scmp.com/rss/4/feed',   # China News
        'https://www.scmp.com/rss/92/feed',  # Business
        'https://www.scmp.com/rss/91/feed',  # Economy
        'https://www.scmp.com/rss/5/feed',   # World
        # Others
        'https://chinadigitaltimes.net/feed/',
        'https://www.cgtn.com/rss/china.xml',
        'https://www.cgtn.com/rss/business.xml',
    ],
    'world': [
        # BBC
        'https://feeds.bbci.co.uk/news/world/rss.xml',
        'https://feeds.bbci.co.uk/news/business/rss.xml',
        'https://feeds.bbci.co.uk/news/world/asia/rss.xml',
        'https://feeds.bbci.co.uk/news/world/asia/india/rss.xml',
        'https://feeds.bbci.co.uk/news/world/asia/china/rss.xml',
        # Others
        'https://www.aljazeera.com/xml/rss/all.xml',
        'https://rss.dw.com/xml/rss-en-all',
        'https://rss.dw.com/xml/rss-en-bus',
        'https://www.france24.com/en/rss',
    ],
    'tech': [
        # TechCrunch
        'https://techcrunch.com/feed/',
        'https://techcrunch.com/category/artificial-intelligence/feed/',
        # AI Focus
        'https://arstechnica.com/ai/feed/',
        'https://www.theverge.com/ai-artificial-intelligence/rss/index.xml',
        'https://www.wired.com/feed/tag/ai/latest/rss',
        'https://venturebeat.com/category/ai/feed/',
        # Hacker News
        'https://hnrss.org/frontpage',
        'https://hnrss.org/best',
        # Others
        'https://www.technologyreview.com/feed/',
        'https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss',
    ]
}

# ============================================
# PRIORITY KEYWORDS for Scoring
# ============================================

PRIORITY_KEYWORDS = {
    'high': [
        'recession', 'inflation', 'rate cut', 'rate hike', 'fed', 'rbi', 'gdp',
        'layoff', 'layoffs', 'acquisition', 'ipo', 'bankruptcy', 'sanctions',
        'tariff', 'tariffs', 'openai', 'anthropic', 'regulation', 'crisis',
        'war', 'invasion', 'nuclear', 'default', 'crash', 'surge', 'plunge',
        'breakthrough', 'ai regulation', 'chatgpt', 'gemini', 'llm'
    ],
    'medium': [
        'earnings', 'profit', 'revenue', 'stock', 'market', 'policy',
        'election', 'trade', 'investment', 'startup', 'funding', 'merger',
        'antitrust', 'privacy', 'cybersecurity', 'hack', 'breach', 'chip',
        'semiconductor', 'ev', 'electric vehicle', 'renewable', 'climate'
    ],
    'low': [
        'update', 'report', 'analysis', 'review', 'launches', 'announces'
    ]
}

# ============================================
# SYSTEM PROMPT - The Voice
# ============================================

SYSTEM_PROMPT = """You are The Daily Unhinged - a news commentator combining the analytical sharpness of a scientist with the irreverent honesty of a stand-up comedian. Your voice merges four influences:

**From George Carlin**: Hunt euphemisms relentlessly. When institutions use soft language to hide hard truths, call it out. "Rightsizing" means layoffs. "Exploring strategic options" means we have no plan. The more syllables, the more suspicious you become.

**From Doug Stanhope**: Be brutally honest. Don't hedge to seem balanced when facts are clear. Take positions and own them. You're skeptical of all authority—government, corporate, media—but your skepticism comes from reasoning, not reflexive contrarianism.

**From Richard Feynman**: Explain complex things simply. Apply "cargo cult" detection—asking whether something has the form of rigor without the substance. Be genuinely curious but allergic to hand-waving.

**From Richard Dawkins**: Dismantle bad arguments with precision. Name logical fallacies. Place burden of proof correctly. Find wonder in reality, not mystification.

**YOUR STYLE:**
- Be direct. State what's actually happening before any hedging.
- Use profanity sparingly but effectively—it signals "no pretense zone"
- Use concrete analogies and vivid language
- When you catch BS, name exactly what kind of BS it is
- Commend genuinely good things with the same directness you criticize bad things
- Short punchy sentences mixed with longer analytical ones
- Never hedge with "some might argue" or "it could be said that"

**AVOID:**
- Don't be relentlessly negative—genuine praise and wonder are part of this voice
- Don't punch down at ordinary people; punch up at systems and power
- Don't use academic jargon or corporate speak (unless mocking it)
- Don't both-sides issues where facts clearly favor one interpretation

**YOUR PURPOSE:**
Help readers understand what's actually happening behind headlines. Expose media manipulation, translate economic jargon into plain English, and identify when powerful interests manufacture consent. You're a bullshit filter with a sense of humor and genuine intellectual curiosity."""


def fetch_feeds(feed_urls: list) -> list:
    """Fetch multiple RSS feeds in parallel."""
    items = []

    def fetch_one(url: str) -> list:
        try:
            feed = feedparser.parse(url)
            return [{
                'title': entry.get('title', '').strip(),
                'link': entry.get('link', ''),
                'summary': (entry.get('summary', '') or entry.get('description', ''))[:500],
                'source': feed.feed.get('title', url.split('/')[2]),
                'published': entry.get('published', ''),
                'feed_url': url
            } for entry in feed.entries[:10] if entry.get('title')]
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return []

    with ThreadPoolExecutor(max_workers=15) as executor:
        future_to_url = {executor.submit(fetch_one, url): url for url in feed_urls}
        for future in as_completed(future_to_url):
            try:
                result = future.result()
                items.extend(result)
            except Exception as e:
                logger.warning(f"Feed fetch error: {e}")

    logger.info(f"Fetched {len(items)} items from {len(feed_urls)} feeds")
    return items


def keyword_score(headline: str) -> int:
    """Score headline by keyword importance."""
    headline_lower = headline.lower()
    score = 0

    for word in PRIORITY_KEYWORDS['high']:
        if word in headline_lower:
            score += 10
    for word in PRIORITY_KEYWORDS['medium']:
        if word in headline_lower:
            score += 3
    for word in PRIORITY_KEYWORDS['low']:
        if word in headline_lower:
            score += 1

    return score


def simple_tfidf_score(headline: str, all_headlines: list, priority_words: list) -> float:
    """Calculate a simple TF-IDF-like score without sklearn."""
    # Tokenize
    words = re.findall(r'\b[a-zA-Z]{3,}\b', headline.lower())
    if not words:
        return 0.0

    # Stop words to filter out
    stop_words = {'the', 'and', 'for', 'that', 'with', 'this', 'from', 'are', 'was',
                  'will', 'have', 'has', 'been', 'were', 'being', 'their', 'its',
                  'but', 'not', 'they', 'which', 'would', 'could', 'about', 'into',
                  'more', 'some', 'than', 'when', 'what', 'there', 'can', 'all'}

    words = [w for w in words if w not in stop_words]
    if not words:
        return 0.0

    # Term frequency in this headline
    word_counts = Counter(words)

    # Document frequency across all headlines
    all_words_flat = []
    for h in all_headlines:
        all_words_flat.extend(re.findall(r'\b[a-zA-Z]{3,}\b', h.lower()))
    doc_freq = Counter(all_words_flat)
    num_docs = len(all_headlines)

    # Calculate TF-IDF for priority words
    score = 0.0
    for word in priority_words:
        if word in word_counts:
            tf = word_counts[word] / len(words)
            idf = math.log((num_docs + 1) / (doc_freq.get(word, 0) + 1)) + 1
            score += tf * idf

    return score


def rank_and_filter(items: list, max_items: int = 25) -> list:
    """Rank items using keyword scoring and simple TF-IDF, then deduplicate."""
    if not items:
        return []

    # Extract headlines
    headlines = [item['title'] for item in items]

    # All priority words for TF-IDF
    all_priority_words = (
        PRIORITY_KEYWORDS['high'] +
        PRIORITY_KEYWORDS['medium'] +
        PRIORITY_KEYWORDS['low']
    )

    # Calculate scores
    for item in items:
        kw_score = keyword_score(item['title'])
        tfidf_score = simple_tfidf_score(item['title'], headlines, all_priority_words)
        item['score'] = kw_score + (tfidf_score * 5)

    # Sort by score
    items.sort(key=lambda x: x.get('score', 0), reverse=True)

    # Deduplicate by title similarity
    seen_hashes = set()
    unique_items = []

    for item in items:
        # Create hash from normalized title
        title_normalized = ''.join(item['title'].lower().split())
        title_hash = hashlib.md5(title_normalized.encode()).hexdigest()[:16]

        if title_hash not in seen_hashes:
            seen_hashes.add(title_hash)
            unique_items.append(item)

    logger.info(f"Filtered {len(items)} items to {len(unique_items)} unique items, returning top {max_items}")
    return unique_items[:max_items]


def generate_commentary(items: list) -> tuple:
    """Generate commentary using AWS Bedrock. Returns (commentary_text, items_with_links)."""
    if not items:
        return "No news items to comment on today. Either the world is perfectly fine (unlikely) or the RSS feeds are broken.", []

    # Prepare items for the prompt (top 10 for commentary)
    items_for_commentary = items[:10]
    items_text = "\n\n".join([
        f"**{i+1}. {item['title']}** ({item['source']})\n{item.get('summary', '')[:300]}"
        for i, item in enumerate(items_for_commentary)
    ])

    prompt = f"""Analyze these news items and provide sharp, witty commentary for each. For each item:
- Give 2-3 sentences of incisive commentary
- Focus on what the headline doesn't say, hidden agendas, economic implications
- Translate any jargon or euphemisms to plain English
- If something is genuinely good news, acknowledge it

{items_text}

Respond with numbered commentaries (1-{min(10, len(items_for_commentary))}) matching each item. Be concise but cutting."""

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2500,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}]
    })

    try:
        response = bedrock.invoke_model(modelId=BEDROCK_MODEL, body=body)
        result = json.loads(response['body'].read())
        commentary = result['content'][0]['text']
        return commentary, items_for_commentary
    except Exception as e:
        logger.error(f"Bedrock call failed: {e}")
        return f"*Commentary generation failed: {e}. The AI is taking a smoke break.*", items_for_commentary


def categorize_items(all_items: list, feeds_config: dict) -> dict:
    """Organize items by category based on their source feed."""
    category_items = {cat: [] for cat in feeds_config.keys()}

    for item in all_items:
        feed_url = item.get('feed_url', '')
        for category, urls in feeds_config.items():
            if any(url in feed_url or feed_url in url for url in urls):
                category_items[category].append(item)
                break

    return category_items


def add_links_to_commentary(commentary: str, items: list) -> str:
    """Add source links to each numbered commentary item."""
    lines = commentary.split('\n')
    result_lines = []

    for line in lines:
        # Check if line starts with a number (commentary item)
        match = re.match(r'^(\d+)\.?\s*(.*)$', line.strip())
        if match:
            num = int(match.group(1))
            rest = match.group(2)

            # Get corresponding item if exists
            if 1 <= num <= len(items):
                item = items[num - 1]
                link = item.get('link', '')
                title = item.get('title', '')[:50]
                source = item.get('source', 'Source')

                # Add link at the end of the commentary
                if link:
                    # Format: number. commentary text [🔗 Source](link)
                    result_lines.append(f"**{num}.** {rest}")
                    result_lines.append(f"   [🔗 {source}]({link})")
                    result_lines.append("")
                else:
                    result_lines.append(line)
            else:
                result_lines.append(line)
        else:
            result_lines.append(line)

    return '\n'.join(result_lines)


def generate_markdown(top_items: list, commentary: str, commentary_items: list, category_items: dict) -> str:
    """Generate the final markdown digest."""
    today = datetime.now().strftime('%B %d, %Y')
    today_iso = datetime.now().strftime('%Y-%m-%d')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')

    # Add links to commentary
    commentary_with_links = add_links_to_commentary(commentary, commentary_items)

    md = f"""---
date: {today_iso}
title: "The Daily Unhinged - {today}"
---

# The Daily Unhinged
## {today}

*Your daily dose of news with the BS filter engaged.*

---

## Top Stories with Commentary

{commentary_with_links}

---

"""

    # Add category sections
    category_titles = {
        'india': 'India',
        'us': 'United States',
        'china': 'China',
        'world': 'World',
        'tech': 'Tech & AI'
    }

    for category, cat_items in category_items.items():
        if cat_items:
            title = category_titles.get(category, category.title())
            md += f"## {title} Headlines\n\n"

            # Show top 7 items per category
            for item in cat_items[:7]:
                source = item.get('source', 'Unknown')
                md += f"- [{item['title']}]({item['link']}) *({source})*\n"
            md += "\n"

    md += f"""---

*Generated by The Daily Unhinged at {timestamp}*
*Powered by AWS Lambda + Bedrock (Claude 3 Haiku)*
*Remember: Question everything, especially this newsletter.*
"""

    return md


def markdown_to_html(markdown: str) -> str:
    """Convert markdown to HTML for email."""
    html = markdown

    # Headers
    html = re.sub(r'^# (.+)$', r'<h1 style="color: #1a1a2e; font-family: Georgia, serif;">\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2 style="color: #16213e; font-family: Georgia, serif; border-bottom: 2px solid #e94560; padding-bottom: 5px;">\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3 style="color: #0f3460;">\1</h3>', html, flags=re.MULTILINE)

    # Bold and italic
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em style="color: #666;">\1</em>', html)

    # Links
    html = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2" style="color: #e94560; text-decoration: none;">\1</a>', html)

    # List items
    html = re.sub(r'^- (.+)$', r'<li style="margin: 8px 0;">\1</li>', html, flags=re.MULTILINE)

    # Numbered items (commentary)
    html = re.sub(r'^(\d+)\. (.+)$', r'<div style="background: #f8f9fa; padding: 15px; margin: 10px 0; border-left: 4px solid #e94560; border-radius: 4px;"><strong style="color: #e94560;">\1.</strong> \2</div>', html, flags=re.MULTILINE)

    # Horizontal rules
    html = html.replace('---', '<hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">')

    # Paragraphs (double newlines)
    html = re.sub(r'\n\n', '</p><p style="line-height: 1.6; color: #333;">', html)

    # Wrap in HTML template
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                 max-width: 700px; margin: 0 auto; padding: 20px; background: #ffffff; color: #333;">
        <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                    color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; font-size: 28px;">The Daily Unhinged</h1>
            <p style="margin: 5px 0 0 0; opacity: 0.9;">Your daily dose of news with the BS filter engaged</p>
        </div>
        <div style="padding: 20px; background: #fff; border: 1px solid #eee; border-top: none; border-radius: 0 0 8px 8px;">
            <p style="line-height: 1.6; color: #333;">
            {html}
            </p>
        </div>
        <div style="text-align: center; padding: 20px; color: #888; font-size: 12px;">
            <p>You're receiving this because you subscribed to The Daily Unhinged.</p>
            <p>Powered by AWS Lambda + Bedrock</p>
        </div>
    </body>
    </html>
    """

    return html_template


def send_email(markdown: str, recipient: str, sender: str) -> bool:
    """Send the digest via email using SES."""
    if not recipient or not sender:
        logger.warning("Email not configured - skipping email send")
        return False

    today = datetime.now().strftime('%B %d, %Y')
    subject = f"The Daily Unhinged - {today}"

    html_body = markdown_to_html(markdown)

    try:
        response = ses.send_email(
            Source=sender,
            Destination={
                'ToAddresses': [recipient]
            },
            Message={
                'Subject': {
                    'Data': subject,
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Text': {
                        'Data': markdown,
                        'Charset': 'UTF-8'
                    },
                    'Html': {
                        'Data': html_body,
                        'Charset': 'UTF-8'
                    }
                }
            }
        )
        logger.info(f"Email sent successfully to {recipient}, MessageId: {response['MessageId']}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def push_to_github(markdown: str, date_str: str) -> bool:
    """Push the digest to GitHub repository."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        logger.warning("GitHub not configured - skipping GitHub push")
        return False

    # File path in the repo
    file_path = f"digests/{date_str}.md"

    # GitHub API URL
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"

    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json'
    }

    # Check if file exists (to get SHA for update)
    sha = None
    try:
        response = requests.get(api_url, headers=headers)
        if response.status_code == 200:
            sha = response.json().get('sha')
    except Exception as e:
        logger.warning(f"Could not check existing file: {e}")

    # Prepare the commit
    content_b64 = base64.b64encode(markdown.encode('utf-8')).decode('utf-8')

    data = {
        'message': f'Add digest for {date_str}',
        'content': content_b64,
        'branch': 'main'
    }

    if sha:
        data['sha'] = sha
        data['message'] = f'Update digest for {date_str}'

    try:
        response = requests.put(api_url, headers=headers, json=data)

        if response.status_code in [200, 201]:
            logger.info(f"Successfully pushed to GitHub: {file_path}")

            # Also update the index file with the new date
            update_github_index(date_str, headers)

            return True
        else:
            logger.error(f"GitHub push failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"GitHub push error: {e}")
        return False


def update_github_index(date_str: str, headers: dict) -> bool:
    """Update the index.json file with the new digest date."""
    index_path = "digests/index.json"
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{index_path}"

    # Get existing index
    dates = []
    sha = None

    try:
        response = requests.get(api_url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            sha = data.get('sha')
            content = base64.b64decode(data['content']).decode('utf-8')
            dates = json.loads(content)
    except Exception as e:
        logger.warning(f"Could not fetch index: {e}")

    # Add new date if not present
    if date_str not in dates:
        dates.append(date_str)
        dates.sort(reverse=True)  # Most recent first

    # Update the index
    content_b64 = base64.b64encode(json.dumps(dates, indent=2).encode('utf-8')).decode('utf-8')

    data = {
        'message': f'Update index with {date_str}',
        'content': content_b64,
        'branch': 'main'
    }

    if sha:
        data['sha'] = sha

    try:
        response = requests.put(api_url, headers=headers, json=data)
        if response.status_code in [200, 201]:
            logger.info("Index updated successfully")
            return True
        else:
            logger.warning(f"Index update failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Index update error: {e}")
        return False


def lambda_handler(event, context):
    """Main Lambda handler."""
    logger.info("The Daily Unhinged: Starting news digest generation")

    # Collect all feed URLs
    all_feed_urls = []
    for urls in RSS_FEEDS.values():
        all_feed_urls.extend(urls)

    logger.info(f"Fetching from {len(all_feed_urls)} RSS feeds")

    # Fetch all feeds
    all_items = fetch_feeds(all_feed_urls)

    if not all_items:
        logger.error("No items fetched from any feed")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'No items fetched from RSS feeds'})
        }

    # Rank and filter
    top_items = rank_and_filter(all_items, MAX_ITEMS)

    # Categorize for the digest
    category_items = categorize_items(all_items, RSS_FEEDS)

    # Generate commentary
    logger.info("Generating commentary via Bedrock")
    commentary, commentary_items = generate_commentary(top_items)

    # Generate markdown
    markdown = generate_markdown(top_items, commentary, commentary_items, category_items)

    # Upload to S3
    today = datetime.now().strftime('%Y-%m-%d')
    key = f"digests/{today}.md"

    try:
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=markdown.encode('utf-8'),
            ContentType='text/markdown; charset=utf-8'
        )
        logger.info(f"Digest uploaded to s3://{BUCKET_NAME}/{key}")
    except Exception as e:
        logger.error(f"S3 upload failed: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'S3 upload failed: {e}'})
        }

    # Send email if configured
    email_sent = False
    if EMAIL_RECIPIENT and EMAIL_SENDER:
        email_sent = send_email(markdown, EMAIL_RECIPIENT, EMAIL_SENDER)

    # Push to GitHub if configured
    github_pushed = False
    if GITHUB_TOKEN and GITHUB_REPO:
        github_pushed = push_to_github(markdown, today)

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'The Daily Unhinged digest generated successfully',
            'bucket': BUCKET_NAME,
            'key': key,
            'items_fetched': len(all_items),
            'items_processed': len(top_items),
            'email_sent': email_sent,
            'email_recipient': EMAIL_RECIPIENT if email_sent else None,
            'github_pushed': github_pushed,
            'github_repo': GITHUB_REPO if github_pushed else None
        })
    }


# For local testing
if __name__ == '__main__':
    # Set test environment variables
    os.environ['BUCKET_NAME'] = 'test-bucket'
    os.environ['LOG_LEVEL'] = 'DEBUG'

    logging.basicConfig(level=logging.DEBUG)

    # Test feed fetching
    print("Testing RSS feed fetching...")
    test_feeds = ['https://feeds.bbci.co.uk/news/world/rss.xml']
    items = fetch_feeds(test_feeds)
    print(f"Fetched {len(items)} items")

    if items:
        print("\nSample item:")
        print(json.dumps(items[0], indent=2))

        print("\nTesting ranking...")
        ranked = rank_and_filter(items, 5)
        for item in ranked:
            print(f"  [{item.get('score', 0):.1f}] {item['title'][:60]}...")
