import re
import time
from datetime import datetime
from decimal import Decimal
from django.conf import settings
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from rest_framework.exceptions import ValidationError
from .models import Resource


class AgodaScraper:
    _CURRENCIES = { "USD": 7, "UAH": 95 }
    
    def __init__(self, base_url):
        self.name_source = "Agoda"
        self.base_url = base_url
    
    def apply_markup(self, price):
        multiplier = Decimal('1') + (Decimal(str(settings.HOTEL_MARKUP_PERCENT)) / Decimal('100'))
        return (price * multiplier).quantize(Decimal('0.01'))
    
    def get_driver(self):
        options = Options()
        options.add_argument("--headless=new")  # Required for Docker
        options.add_argument("--no-sandbox") # Required for Docker
        options.add_argument("--disable-dev-shm-usage") # To prevent crashes due to memory loss

        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

        service = Service("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=options)
        
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """   
        })
        return driver
    
    def get_city_id(self, driver, city_name):
        """
        The method extracts the city_id directly from the drop-down list of suggestions.
        """
        try:
            print(f"--- Quick ID search for: {city_name} ---")
            driver.get(self.base_url)
            wait = WebDriverWait(driver, 15)

            # 1. Find input and enter the city
            search_input = wait.until(EC.presence_of_element_located((By.ID, "textInput")))

            # Clicking via JS so banners don't get in the way
            driver.execute_script("arguments[0].click();", search_input)

            # Cleaning and input
            search_input.send_keys(Keys.CONTROL + "a", Keys.DELETE)
            for char in city_name:
                search_input.send_keys(char)
                time.sleep(0.1)

            print("The city has been entered, we're waiting for the list to appear in the DOM...")

            # 2. Wait a bit for Agoda to render the <ul>
            time.sleep(4)

            # 3. Look for the data-objectid attribute in all li
            # Loop through all the li's you found and take the ID of the first match.
            script = """
            let items = document.querySelectorAll('li[data-objectid]');
            if (items.length > 0) {
                return items[0].getAttribute('data-objectid');
            }
            // Backup option: search the entire page text if li doesn't work
            let anyElement = document.querySelector('[data-objectid]');
            return anyElement ? anyElement.getAttribute('data-objectid') : null;
            """

            city_id = driver.execute_script(script)

            if city_id:
                print(f"--- ID extracted: {city_id} ---")
                return str(city_id)
            else:
                print("JS didn't find the data-objectid. Try pressing ArrowDown to activate the list...")
                search_input.send_keys(Keys.ARROW_DOWN)
                time.sleep(1)
                city_id = driver.execute_script(script)
                if city_id: return str(city_id)

        except Exception as e:
            print(f"Error in method: {str(e)[:100]}")
            driver.save_screenshot("city_search_error.png")

        return None
 
    def get_length_of_stay(self, checkin_str, checkout_str):
        """
        Validates dates and returns the number of nights (los).
        Date format: 'YYYY-MM-DD'
        """
        try:
            # 1. Format check (must be YYYY-MM-DD)
            date_format = "%Y-%m-%d"
            checkin_date = datetime.strptime(checkin_str, date_format)
            checkout_date = datetime.strptime(checkout_str, date_format)

            # 2. Checking that dates are not in the past
            if checkin_date.date() < datetime.now().date():
                raise ValidationError("Дата заезда не может быть в прошлом.")

            # 3. Logical test: check-out later than check-in
            if checkout_date <= checkin_date:
                raise ValidationError("The check-out date must be later than the check-in date.")

            # 4. Calculating the difference in days
            delta = checkout_date - checkin_date
            return delta.days

        except ValueError:
            raise ValidationError("Invalid date format. Use YYYY-MM-DD.")
    
    
    def scrape_agoda(self, city, checkin, checkout, adults=2, rooms=1, children=0, currency_code="UAH"):

        driver = self.get_driver()
        # results_count = 0
        
        try:
                 
            city_id = self.get_city_id(driver, city)
            
            if not city_id:
                print("CRITICAL: city_id is None. Check city_search_error.png")
                return 0
            
            los = self.get_length_of_stay(checkin_str=checkin, checkout_str=checkout) 
            
            url = (
                f"{self.base_url}search?"
                f"city={city_id}&checkin={checkin}&los={los}&"
                f"rooms={rooms}&adults={adults}&cid=-1"
            )
        
            print(f"Set currency ...")
            currency_id = self._CURRENCIES.get(currency_code, 95)
            self.set_currency(driver=driver, currency_id=currency_id) # 7-USD, 95-UAH
            
            print(f"Starting Selenium scraping: {url}")
            driver.get(url)
            
            time.sleep(2)
            driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            
            try:
                time.sleep(3)
                page_body = driver.find_element(By.TAG_NAME, 'body')
                page_body.send_keys(Keys.ESCAPE)
                print("Sent ESCAPE to close potential banners")
            except:
                pass
            
            # Wait for at least one card to appear (up to 30 seconds)
            wait = WebDriverWait(driver, 30)
            hotel_selector = '[data-selenium="hotel-item"], [data-testid="property-card"]'
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, hotel_selector)))
            print("Hotels found on page!")

            # Slow scrolling to allow elements to "load" into the DOM
            for _ in range(7):
                driver.execute_script("window.scrollBy(0, 1000);")
                time.sleep(2)

            hotel_cards = driver.find_elements(By.CSS_SELECTOR, '[data-selenium="hotel-item"]')
            print(f'Found potential blocks: {len(hotel_cards)}')

            results = []
            
            for card in hotel_cards[:10]:
                try:
                    name_el = card.find_elements(By.XPATH, ".//*[@data-selenium='hotel-name']")
                    description_el = card.find_elements(By.XPATH, ".//*[@data-selenium='popular-landmarks-text']")
                    price_el = card.find_elements(By.XPATH, ".//*[@data-selenium='display-price']")
                    currency_el = card.find_elements(By.XPATH, ".//*[@data-selenium='hotel-currency']")

                    if name_el and price_el:
                        # Take the first found element from the list and extract the text
                        name = name_el[0].text.strip()
                        description = description_el[0].text.strip()
                        price = price_el[0].text.strip()
                        currency = currency_el[0].text.strip()
                        
                        clean_price = re.sub(r'[^\d.]', '', price.replace(',', ''))
                        if not clean_price: continue
                        
                        raw_price = Decimal(clean_price)
                        final_price = self.apply_markup(raw_price)
                        
                        if name: # Check that the text is not empty
                            results.append(
                                {
                                    "name": name, 
                                    "description": description, 
                                    "price": final_price, 
                                    "currency": currency}
                            )
                            
                    # self.save_to_resource(self.name_source, hotel_id, title, clean_price, relative_url, url)
                            
                except Exception:
                    continue
            
            # Print just for test
            print(f"Hotels successfully collected: {len(results)}")
            for item in results:
                print(f"Hotel: {item['name']} | Description: {item['description']} Price: {item['price']} {item['currency']}")

            return len(results)
        
        finally:
            driver.quit()           

    
    def save_to_resouces(self, source, hotel_id, title, clean_price, relative_url, url):
        # Save or update in the database
        Resource.objects.update_or_create(
            external_id=f"agoda_{hotel_id}",
            defaults={
                'title': title,
                'price': Decimal(clean_price) if clean_price else 0,
                'source': source, # 'Agoda'
                'source_url': f"https://www.agoda.com{relative_url}" if relative_url else url
            }
        )
        
    def _get_currency_id(self, code):
        return {"USD": 7, "UAH": 95}.get(code, 95)
    
    
    def set_currency(self, driver, currency_id):
        url=f"https://www.agoda.com/api/cronos/layout/currency/set?currencyId={currency_id}"
        driver.get(url)
        time.sleep(3)
        