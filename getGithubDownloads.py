import requests
import json
import pprint

user = "werwolv"
repo = "imhex"

url = f"https://api.github.com/repos/{user}/{repo}/releases"
response = requests.get(url)
jsonurl = json.loads(response.text)
totalDownloads = 0
extendedPrint = False

downloadDict = {}

for i in jsonurl:
	releaseName = i["name"]
	for j in i["assets"]:
		if extendedPrint:
			print(f"Release Name: {i["name"]}")
			print(f"Filename: {j["name"]}")
			print(f"Downloads: {j["download_count"]}\n")

		if j["name"] not in downloadDict:
			downloadDict[j["name"]] = {
				"releases": {},
				"total": 0
			}

		downloadDict[j["name"]]["releases"][i["name"]] = int(j["download_count"])
		downloadDict[j["name"]]["total"] += int(j["download_count"])
		totalDownloads += int(j["download_count"])

print("Downloads:")
maxLen = max(len(i) for i in downloadDict)
for i in downloadDict:
	print(f"{i.ljust(maxLen)}  {downloadDict[i]['total']:>10}")

print(f"\nTotal Downloads: {totalDownloads}")
input()
