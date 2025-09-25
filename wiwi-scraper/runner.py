from dotenv import load_dotenv
from scraper import WiwiScraper
import asyncio

load_dotenv()

scraper = WiwiScraper()

scraper.run()

asyncio.run(scraper.run())