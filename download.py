import requests
import shutil
import os

def download_art(ext: str= ""):
    art = open(f"Spotify-listening-data/art{ext}.csv").read().split("\n")
    existing_files = os.listdir(f"artwork{ext}")

    N = len(art)
    i = 0
    for item in art:
        i += 1
        if len(item) == 0:
            continue
        url = item.split(",")[1]
        id = item.split(",")[0]

        if f"{id}.png" in existing_files:
            print("skipping existing file")
            continue

        print(f"Downloading [{int(100 * (i / N))}%]  {id}")
        response = requests.get(url, stream=True)
        with open(f"artwork{ext}/{id}.png", "wb") as out_file:
            shutil.copyfileobj(response.raw, out_file)
        del response


if __name__ == '__main__':
    download_art()