import requests
from bs4 import BeautifulSoup
import logging

class WebSearch:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def search(self, query, max_results=5):
        try:
            response = requests.get(f"https://duckduckgo.com/html?q={query}")
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            for result in soup.find_all('a', class_='result__a'):
                results.append(result.text)
            return results[:max_results]
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erreur réseau : {e}")
            return []

    def get_summary(self, query):
        try:
            response = requests.get(f"https://duckduckgo.com/html?q={query}")
            soup = BeautifulSoup(response.text, 'html.parser')
            summary = soup.find('div', class_='result__summary').text
            return summary
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erreur réseau : {e}")
            return None

# Test du module
if __name__ == '__main__':
    web_search = WebSearch()
    query = "intelligence artificielle"
    results = web_search.search(query)
    print(results)
    summary = web_search.get_summary(query)
    print(summary)
