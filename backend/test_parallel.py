import asyncio
import time
from email_extractor import EmailExtractor
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

async def mock_callback(type, message, level=None, **kwargs):
    if type == 'log':
        print(f"[{level.upper()}] {message}")
    elif type == 'progress':
        print(f"[PROGRESS] {message}%")

async def main():
    urls = [
        "https://www.example.com",
        "https://www.google.com",
        "https://www.bing.com",
        "https://www.python.org",
        "https://www.github.com",
        "https://www.microsoft.com",
        "https://www.apple.com",
        "https://www.amazon.com",
        "https://www.netflix.com",
        "https://www.stackoverflow.com"
    ]
    
    print("Initializing extractor...")
    extractor = EmailExtractor(headless=True)
    await extractor.initialize()
    
    start_time = time.time()
    try:
        print(f"Starting extraction for {len(urls)} URLs...")
        await extractor.extract_from_urls(urls, mock_callback)
    finally:
        await extractor.close()
        
    end_time = time.time()
    duration = end_time - start_time
    print(f"Total time: {duration:.2f} seconds")
    print(f"Average time per URL: {duration/len(urls):.2f} seconds")

if __name__ == "__main__":
    asyncio.run(main())
