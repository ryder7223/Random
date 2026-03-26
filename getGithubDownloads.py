import requests
import json

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
			print(f"Release Name: {i['name']}")
			print(f"Filename: {j['name']}")
			print(f"Downloads: {j['download_count']}\n")

		if j["name"] not in downloadDict:
			downloadDict[j["name"]] = {
				"releases": {},
				"total": 0
			}

		downloadDict[j["name"]]["releases"][releaseName] = int(j["download_count"])
		downloadDict[j["name"]]["total"] += int(j["download_count"])
		totalDownloads += int(j["download_count"])

sortOrder = None	 # options: "most", "least", None
mostDownloads = max(downloadDict, key=lambda i: downloadDict[i]['total'])
leastDownloads = min(downloadDict, key=lambda i: downloadDict[i]['total'])
maxLen = int(max(len(i) for i in downloadDict) + len(" "*max([len(mostDownloads), len(leastDownloads)])))
mdString = "Most Downloaded: " + mostDownloads
ldString = "Least Downloaded: " + leastDownloads

print("Downloads:")

items = list(downloadDict.items())
if sortOrder == "most":
	items.sort(key=lambda x: x[1]['total'], reverse=True)
elif sortOrder == "least":
	items.sort(key=lambda x: x[1]['total'])

for name, data in items:
	print(f"{name.ljust(maxLen)}  {data['total']:>10}")

print(f"\nTotal Downloads: {totalDownloads}")
print(f"{mdString.ljust(maxLen)}  {downloadDict[mostDownloads]['total']:>10}")
print(f"{ldString.ljust(maxLen)}  {downloadDict[leastDownloads]['total']:>10}")
input()
