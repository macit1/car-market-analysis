import requests
import json
from bs4 import BeautifulSoup

url = "https://www.autoscout24.be/fr/offres/bmw-x1-16d-verwarmde-zetels-auto-koffer-lendensteun-diesel-brun-8911e840-f4dd-44ef-9e86-3933bdfc9155"
headers = {'User-Agent': 'Mozilla/5.0'}
res = requests.get(url, headers=headers)
soup = BeautifulSoup(res.text, 'html.parser')
sc = soup.find('script', id='__NEXT_DATA__')
dat = json.loads(sc.string)

listing = dat.get('props', {}).get('pageProps', {}).get('listingDetails', {})
v = listing.get('vehicle', {})

print("listing.title:", listing.get('title'))
print("vehicle.title:", v.get('title'))
print("vehicle.version:", v.get('version'))
print("vehicle.versionRaw:", v.get('versionRaw'))
print("vehicle keys:", list(v.keys()))
