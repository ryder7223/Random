# You may need to install requests and beautifulsoup4
# pip install requests beautifulsoup4

import requests, os
from bs4 import BeautifulSoup

def get_weather_forecast():
    """
    Fetches and displays the weather forecast for Perth from the Bureau of Meteorology website.
    """
    #url = "http://www.bom.gov.au/wa/forecasts/perth.shtml"
    state = input("wa (Western Australia)\nnt (Northern Territory\ntas (Tasmania)\nnsw (New South Wales)\nsa (South Australia)\nqld (Queensland)\nvic (Victoria)\nact (Australian Capital Territory)\n\nEnter a state name to check: ")
    place = input("Enter a town/city name to check: ")
    url = f"http://www.bom.gov.au/{state}/forecasts/{place}.shtml"
    
    print(f"Fetching weather data from: {url}")

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the URL: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')

    # Find the forecast issued date and time
    forecast_issued = soup.find('p', class_='date')
    if forecast_issued:
        print(forecast_issued.get_text(strip=True))
    
    print("=" * 40)

    # Find all the day containers.
    # The structure is <div class="day ...">
    forecast_days = soup.find_all('div', class_=lambda x: x and 'day' in x.split())

    if not forecast_days:
        print("Could not find any forecast days on the page.")
        return
    os.system("cls")
    for day in forecast_days:
        day_title_tag = day.find('h2')
        if not day_title_tag:
            continue
    
        day_title = day_title_tag.get_text(strip=True)
        print(f"\n{day_title.upper()}")
        print("-" * (len(day_title) + 6))

        forecast_div = day.find('div', class_='forecast')
        if forecast_div:
            # Summary
            summary_tag = forecast_div.find('dd', class_='summary')
            if summary_tag:
                summary = summary_tag.get_text(strip=True)
                print(f"🔹 Summary: {summary}")

            # Min/Max Temp
            min_temp_em = forecast_div.find('em', class_='min')
            if min_temp_em:
                print(f"🔹 Min Temp: {min_temp_em.get_text(strip=True)}°C")

            max_temp_em = forecast_div.find('em', class_='max')
            if max_temp_em:
                print(f"🔹 Max Temp: {max_temp_em.get_text(strip=True)}°C")

            # Rain information
            rain_dd_tags = forecast_div.find_all('dd', class_='rain')
            for rain_dd in rain_dd_tags:
                text_content = rain_dd.get_text()
                if 'Possible rainfall' in text_content:
                    rainfall_amount_em = rain_dd.find('em', class_='rain')
                    if rainfall_amount_em:
                        print(f"🔹 Possible rainfall: {rainfall_amount_em.get_text(strip=True)}")
                elif 'Chance of any rain' in text_content:
                    rain_chance_em = rain_dd.find('em', class_='pop')
                    if rain_chance_em:
                        # Clean up text which might have newlines and extra spaces
                        rain_text = ' '.join(rain_chance_em.get_text(strip=True).split())
                        print(f"🔹 Chance of rain: {rain_text}")

            # Perth area details
            perth_area_h3 = forecast_div.find('h3', string='Perth area')
            if perth_area_h3:
                details_p = perth_area_h3.find_next_sibling('p')
                if details_p:
                    print(f"🔹 Details: {details_p.get_text(strip=True)}")

        # Alerts
        uv_alert_p = day.find('p', class_='alert')
        if uv_alert_p:
            print(f"🔸 UV Alert: {uv_alert_p.get_text(strip=True)}")

        fire_danger_dl = day.find('dl', class_='alert')
        if fire_danger_dl:
            dt = fire_danger_dl.find('dt')
            if dt and 'Fire Danger' in dt.get_text(strip=True):
                print("🔸 Fire Danger:")
                dds = fire_danger_dl.find_all('dd')
                for dd in dds:
                    print(f"     - {dd.get_text(strip=True)}")
        
        print("-" * (len(day_title) + 6))


if __name__ == "__main__":
    while 1:
        get_weather_forecast() 
        input()
        os.system("cls")