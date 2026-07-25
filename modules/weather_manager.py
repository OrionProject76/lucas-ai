import requests

class WeatherManager:
    def get_current(self, city):
        try:
            response = requests.get(f"http://wttr.in/{city}?format=3")
            data = response.text.splitlines()
            if len(data) > 1:
                temperature = data[0].split()[2]
                condition = data[1].split()[0]
                wind = data[2].split()[2]
                humidity = data[3].split()[2]
                return {
                    "temperature": temperature,
                    "condition": condition,
                    "wind": wind,
                    "humidity": humidity
                }
            else:
                raise ValueError("Ville invalide")
        except requests.exceptions.RequestException as e:
            print(f"Erreur de connexion : {e}")
            return None

    def format_for_display(self, data):
        if data is not None:
            return f"Météo actuelle à {data['temperature']}°C, avec une condition de {data['condition']}, un vent de {data['wind']} et une humidité de {data['humidity']}%"
        else:
            return "Erreur : ville invalide ou pas de connexion"

# Test
weather_manager = WeatherManager()
print(weather_manager.get_current("Paris"))
