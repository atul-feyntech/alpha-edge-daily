#!/usr/bin/env python3
"""
The Daily Unhinged - Local Testing Script

Test RSS fetching and ranking locally without deploying to AWS.
"""

import os
import sys
import json
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set environment variables for local testing
os.environ['BUCKET_NAME'] = 'test-bucket-local'
os.environ['LOG_LEVEL'] = 'DEBUG'
os.environ['MAX_ITEMS'] = '10'

# Now import the lambda function
from lambda_function import (
    RSS_FEEDS,
    fetch_feeds,
    keyword_score,
    rank_and_filter,
    categorize_items,
    generate_markdown,
    simple_tfidf_score,
    PRIORITY_KEYWORDS
)


def test_single_feed():
    """Test fetching a single RSS feed."""
    print("\n" + "="*60)
    print("TEST 1: Single Feed Fetch")
    print("="*60)

    test_url = 'https://feeds.bbci.co.uk/news/world/rss.xml'
    print(f"Fetching: {test_url}")

    items = fetch_feeds([test_url])

    print(f"Fetched {len(items)} items")

    if items:
        print("\nSample item:")
        sample = items[0]
        print(f"  Title: {sample['title'][:80]}...")
        print(f"  Source: {sample['source']}")
        print(f"  Link: {sample['link'][:60]}...")

    return len(items) > 0


def test_multiple_feeds():
    """Test fetching multiple feeds in parallel."""
    print("\n" + "="*60)
    print("TEST 2: Multiple Feeds (Parallel Fetch)")
    print("="*60)

    # Test with one feed from each category
    test_urls = [
        'https://feeds.bbci.co.uk/news/business/rss.xml',
        'https://techcrunch.com/category/artificial-intelligence/feed/',
        'https://feeds.npr.org/1014/rss.xml',
    ]

    print(f"Fetching {len(test_urls)} feeds in parallel...")
    start = datetime.now()
    items = fetch_feeds(test_urls)
    elapsed = (datetime.now() - start).total_seconds()

    print(f"Fetched {len(items)} items in {elapsed:.2f}s")

    # Show sources
    sources = set(item['source'] for item in items)
    print(f"Sources: {', '.join(sources)}")

    return len(items) > 0


def test_keyword_scoring():
    """Test keyword scoring function."""
    print("\n" + "="*60)
    print("TEST 3: Keyword Scoring")
    print("="*60)

    test_headlines = [
        "Fed announces rate cut amid recession fears",
        "OpenAI releases new GPT model",
        "Local bakery opens new location",
        "Company announces layoffs, stock crashes",
        "Weather update for the weekend",
        "Inflation hits 10-year high as GDP growth slows",
    ]

    print("Testing headlines:\n")
    for headline in test_headlines:
        score = keyword_score(headline)
        print(f"  [{score:3d}] {headline}")

    return True


def test_ranking():
    """Test the full ranking pipeline."""
    print("\n" + "="*60)
    print("TEST 4: TF-IDF Ranking Pipeline")
    print("="*60)

    # Fetch some real items
    items = fetch_feeds([
        'https://feeds.bbci.co.uk/news/business/rss.xml',
        'https://techcrunch.com/feed/',
    ])

    if not items:
        print("No items to rank!")
        return False

    print(f"\nRanking {len(items)} items...")
    ranked = rank_and_filter(items, max_items=10)

    print(f"\nTop 10 ranked items:")
    for i, item in enumerate(ranked, 1):
        score = item.get('score', 0)
        print(f"  {i}. [{score:.1f}] {item['title'][:60]}...")

    return len(ranked) > 0


def test_all_feeds():
    """Test fetching ALL configured feeds (warning: slow)."""
    print("\n" + "="*60)
    print("TEST 5: Full Feed Fetch (ALL FEEDS)")
    print("="*60)

    all_urls = []
    for urls in RSS_FEEDS.values():
        all_urls.extend(urls)

    print(f"Fetching {len(all_urls)} feeds...")
    start = datetime.now()
    items = fetch_feeds(all_urls)
    elapsed = (datetime.now() - start).total_seconds()

    print(f"Fetched {len(items)} items in {elapsed:.2f}s")

    # Category breakdown
    category_items = categorize_items(items, RSS_FEEDS)
    print("\nItems by category:")
    for cat, cat_items in category_items.items():
        print(f"  {cat}: {len(cat_items)} items")

    # Rank and show top items
    ranked = rank_and_filter(items, max_items=15)
    print(f"\nTop 15 items across all feeds:")
    for i, item in enumerate(ranked, 1):
        score = item.get('score', 0)
        print(f"  {i}. [{score:.1f}] {item['title'][:55]}... ({item['source'][:20]})")

    return len(items) > 0


def test_markdown_generation():
    """Test markdown output generation."""
    print("\n" + "="*60)
    print("TEST 6: Markdown Generation")
    print("="*60)

    # Fetch some items
    items = fetch_feeds(['https://feeds.bbci.co.uk/news/world/rss.xml'])

    if not items:
        print("No items for markdown generation!")
        return False

    ranked = rank_and_filter(items, max_items=5)
    category_items = categorize_items(items, RSS_FEEDS)

    # Generate markdown with mock commentary
    mock_commentary = """
**1. Sample commentary for the first headline**

This is where the witty analysis would go. Something about euphemisms and power structures.

**2. Commentary continues**

More irreverent observations here.
"""

    markdown = generate_markdown(ranked, mock_commentary, category_items)

    print("Generated markdown preview (first 1000 chars):")
    print("-" * 40)
    print(markdown[:1000])
    print("-" * 40)
    print(f"\nTotal markdown length: {len(markdown)} characters")

    return len(markdown) > 0


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("   THE DAILY UNHINGED - LOCAL TEST SUITE")
    print("="*60)

    tests = [
        ("Single Feed Fetch", test_single_feed),
        ("Multiple Feeds (Parallel)", test_multiple_feeds),
        ("Keyword Scoring", test_keyword_scoring),
        ("TF-IDF Ranking", test_ranking),
        ("Markdown Generation", test_markdown_generation),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n ERROR in {name}: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        symbol = "✓" if passed else "✗"
        print(f"  {symbol} {name}: {status}")
        if not passed:
            all_passed = False

    print("")

    if all_passed:
        print("All tests passed! Ready for deployment.")
    else:
        print("Some tests failed. Check the output above.")

    # Ask if user wants to run the full feed test
    if '--full' in sys.argv:
        test_all_feeds()
    else:
        print("\nTip: Run with --full to test ALL RSS feeds")

    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
