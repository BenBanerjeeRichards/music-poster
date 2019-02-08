import requests
import shutil


def download_art():
    art = open("Spotify-listening-data/art-small.csv").read().split("\n")
    N = len(art)
    i = 0
    for item in art:
        i += 1
        if len(item) == 0:
            continue
        url = item.split(",")[1]
        id = item.split(",")[0]

        print(f"Downloading [{int(100 * (i / N))}%]  {id}")
        response = requests.get(url, stream=True)
        with open('artwork-small/{}.png'.format(id), 'wb') as out_file:
            shutil.copyfileobj(response.raw, out_file)
        del response


if __name__ == '__main__':
    download_art()