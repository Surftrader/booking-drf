from rest_framework.views import APIView
from rest_framework.response import Response
from .utils import AgodaScraper


class ScrapeAgodaView(APIView):
    # For now, we'll leave access to everyone for the test, then we'll add IsAdminUser
    def post(self, request):
        # We take the city from JSON or 'bali' by default
        city = request.data.get('city', 'bali') 
        scraper = AgodaScraper()
        count = scraper.scrape_agoda(city)
        
        return Response({
            "message": f"Successfully scraped {count} hotels from Agoda for {city}"
        })
