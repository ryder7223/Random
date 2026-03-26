import requests
import json

user = "ryder7223"
repo = "Auto-Practice"
fileName = "ryder7223.autopractice.geode"

url = f"https://api.github.com/repos/{user}/{repo}/releases"
response = requests.get(url)
jsonurl = json.loads(response.text)
downloadCount = "None"
totalDownloadCount = 0

for i in jsonurl:
	for j in i["assets"]:
		if j["name"] == fileName:
			print(f"Release Name: {i["name"]}")
			print(f"Filename: {j["name"]}")
			print(f"Downloads: {j["download_count"]}\n")
			totalDownloadCount += int(j["download_count"])

print(f"Total Downloads: {totalDownloadCount}")
input()