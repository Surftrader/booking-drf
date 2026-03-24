from rest_framework.views import APIView
from rest_framework.response import Response
from .utils import AgodaScraper


class ScrapeAgodaView(APIView):
    
    def post(self, request):
        
        currency = request.data.get('currency', 'UAH')    
        city = request.data.get('city', 'Kyiv')
        checkin = request.data.get('checkin')
        checkout = request.data.get('checkout')
        adults = request.data.get('adults')
        rooms = request.data.get('rooms')
        children = request.data.get('children')       

        scraper = AgodaScraper(base_url="https://www.agoda.com/uk-ua/")

        try:
            count = scraper.scrape_agoda(
                city=city, checkin=checkin, 
                checkout=checkout, adults=adults, 
                rooms=rooms, children=children,
                currency_code=currency
            )
            return Response({"status": "success", "found": count})
        except Exception as e:
            # Catching our validation errors
            return Response({"error": str(e)}, status=400)
