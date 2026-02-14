from datetime import datetime, timedelta
import requests
import json

def formatDate(date: datetime) -> str:
	return date.strftime("%Y-%m-%d")

dates = []
dates.append(formatDate(datetime.today()))
dates.append(formatDate(datetime.today() + timedelta(days=1)))
dataArray = []
for i in dates:
	response = requests.post(f"https://nytimes.com/svc/wordle/v2/{i}.json")
	data = json.loads(response.text)
	word = data["solution"]
	dataArray.append(word)
print(f"Today's Wordle answer is {dataArray[0]}")
print(f"Tomorrows's Wordle answer is {dataArray[1]}")
input()