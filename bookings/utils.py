import asyncio
from playwright.sync_api import sync_playwright
from .models import Resource
from decimal import Decimal
import re
from django.conf import settings


class AgodaScraper:
    def scrape_agoda(self, city="bali"):
        with sync_playwright() as p:
            # Run browser (headless=True for working in the background)
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Example URL for Agoda (need to substitute actual search pattern)
            url = f"https://www.agoda.com/search?city={city}"
            
            try:
                page.goto(url, wait_until="networkidle")
                
                # Wait for loading of the cards, which you sent
                page.wait_for_selector('.DatelessPropertyCard')
                
                cards = page.query_selector_all('.DatelessPropertyCard')
                results_count = 0

                for card in cards[:10]: # Take the first 10
                    # Extract data using your classes
                    title_elem = card.query_selector('.DatelessPropertyCard__ContentHeader')
                    price_elem = card.query_selector('.DatelessPropertyCard__AdditionalPriceCurrency')
                    hotel_id = card.get_attribute('data-hotel-id')
                    relative_url = card.get_attribute('data-element-url')

                    if title_elem and price_elem:
                        title = title_elem.inner_text().strip()
                        price_raw = price_elem.inner_text().strip()
                        
                        # Clear the price: we leave only the numbers
                        clean_price = re.sub(r'[^\d.]', '', price_raw)
                        
                        # Сохраняем или обновляем в БД
                        Resource.objects.update_or_create(
                            external_id=f"agoda_{hotel_id}",
                            defaults={
                                'title': title,
                                'price': Decimal(clean_price) if clean_price else 0,
                                'source': 'Agoda',
                                'source_url': f"https://www.agoda.com{relative_url}" if relative_url else url
                            }
                        )
                        results_count += 1
                
                browser.close()
                return results_count
            except Exception as e:
                print(f"Agoda Scraping Error: {e}")
                browser.close()
                return 0


        def apply_markup(self, price):
            multiplier = 1 + (settings.HOTEL_MARKUP_PERCENT / 100)
            return price * multiplier

        raw_price = Decimal(price_val)
        final_price = self.apply_markup(raw_price)
