from PIL import Image
import random
import requests
import shutil
import os
from compute import *
import json
import dateutil.parser


class Track:
    def __init__(self, date, song_id, artist_id, album_id, song, artist, album, large_cover=None, med_cover=None,
                 small_cover=None):
        self.date = date
        self.song_id = song_id
        self.artist_id = artist_id
        self.album_id = album_id

        self.song = song
        self.artist = artist
        self.album = album

        #    Artwork
        self.small_cover = small_cover
        self.medium_cover = med_cover
        self.large_cover = large_cover

    def __str__(self):
        return "[{}] {} - {} on {}".format(self.date, self.artist, self.song, self.album)


class PosterImage:

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.base = Image.new("RGB", (width, height), "black")

    def add_image(self, image: Image, x_pos: float, y_pos: float):
        # assert (0 <= x_pos <= 1)
        # assert (0 <= y_pos <= 1)
        # assert (self.can_fit_at(image, x_pos, y_pos))
        self.base.paste(image, (x_pos, y_pos))

    def can_fit_at(self, image: Image, x_pos: float, y_pos: float):
        assert (0 <= x_pos <= 1)
        assert (0 <= y_pos <= 1)
        end_x = int(x_pos * self.width) + image.width
        end_y = int(y_pos * self.width) + image.height
        return end_x <= self.width and end_y <= self.height

    def save(self):
        self.base.save("out.png")


class PosterFitter:

    def __init__(self, images: [Image], poster: PosterImage):
        self.images = images
        self.poster = poster

        # Soft widths we use that are expanded as needed
        self.width = 0
        self.height = 0


def download_art():
    for item in open("Spotify-listening-data/art.csv").read().split("\n"):
        url = item.split(",")[1]
        id = item.split(",")[0]

        print("Downloading {}".format(id))
        response = requests.get(url, stream=True)
        with open('artwork/{}.png'.format(id), 'wb') as out_file:
            shutil.copyfileobj(response.raw, out_file)
        del response


class Placement:

    def __init__(self, n_x, n_y):
        self.n_x = n_x
        self.n_y = n_y
        self.places = [0] * self.n_x * self.n_y
        self.placements = {}  # Map from album id to coordinates
        self.placement_size = {}

    def print_placement(self):
        for y in range(self.n_y):
            # print("{}| ".format(y), end="")

            for x in range(self.n_x):
                idx = self._xy_to_index(x, y)
                print(self.places[idx], end=" ")

            print()

    def _xy_to_index(self, x, y):
        return x * self.n_y + y

    def alloc(self, x, y):
        pos = self._xy_to_index(x, y)
        assert (self.places[pos] == 0)
        self.places[pos] = 1

    def alloc_square(self, x, y, size):
        if size == 1:
            self.alloc(x, y)
            return

        for x_add in range(size):
            for y_add in range(size):
                self.alloc(x + x_add, y + y_add)

    def is_free(self, x, y):
        return self.places[self._xy_to_index(x, y)] == 0

    def can_place_at(self, x, y, size):
        if x + size - 1 >= self.n_x:
            return False

        if y + size - 1 >= self.n_y:
            return False

        for x_add in range(size):
            for y_add in range(size):
                if not self.is_free(x + x_add, y + y_add):
                    return False

        return True

    def random_coord(self) -> Tuple[int, int]:
        return random.randint(0, self.n_x - 1), random.randint(0, self.n_y - 1)

    def random_place(self, aid: str, size: int):
        # First get list of coords with unallocated space
        spaces = []
        for x in range(self.n_x):
            for y in range(self.n_y):
                can_place = self.can_place_at(x, y, size)
                if can_place:
                    spaces.append((x, y))

        if len(spaces) == 0:
            # Failed to find place
            print("ERROR: FAILED TO FIND ALLOCATION FOR SIZE = {} ".format(size))
            self.print_placement()
            return False

        x, y = random.choice(spaces)
        self.placements[aid] = (x, y)
        self.placement_size[aid] = size
        self.alloc_square(x, y, size)
        return True

    def idx_to_coords(self, idx):
        x_pos = int(idx / self.n_x)
        y_pos = idx - (x_pos * self.n_x)
        return x_pos, y_pos

    def find_aid_for_index(self, idx):
        x, y = self.idx_to_coords(idx)
        for aid in self.placements:
            if self.placements[aid] == (x, y):
                return aid

    def push_zeros_to_bottom(self):
        ones_barrier_idx = 0  # Goes forward
        zero_barrier_idx = self.n_y * self.n_x - 1  # Goes backwards

        while ones_barrier_idx < zero_barrier_idx:

            # one_barrier = everything behind is a one so find a zero to move down
            while self.places[ones_barrier_idx] == 1:
                ones_barrier_idx += 1

            # We have a zero, so replace with a one from lower down
            # Find next one which MUST be of size 1 (larger sizes don't bother)
            aid = self.find_aid_for_index(zero_barrier_idx)

            while self.places[zero_barrier_idx] == 0 or (aid is None or self.placement_size[aid] > 1):
                zero_barrier_idx -= 1
                aid = self.find_aid_for_index(zero_barrier_idx)

            # Now do the flip flop
            self.placements[aid] = self.idx_to_coords(ones_barrier_idx)
            self.places[ones_barrier_idx] = 1
            self.places[zero_barrier_idx] = 0
            zero_barrier_idx -= 1
            ones_barrier_idx += 1


def resize_for_size(image: Image, size: int, settings: Settings) -> Image:
    return image.resize((settings.dim * size, settings.dim * size), Image.ANTIALIAS)


def poster_id(file: str):
    return file.split(".")[0]


def process_tracks() -> List[Track]:
    tracks = []

    # Remember the json files are not really json
    with open("Spotify-listening-data/tracks.json", "r") as f:
        for track_str in f.read().split("\n"):
            if len(track_str) > 1:
                track_json = json.loads(track_str)
                dt = dateutil.parser.parse(track_json["played_at"]["$date"])
                track = Track(dt, track_json["track"]["id"],
                              track_json["track"]["artists"][0]["id"],
                              track_json["track"]["album"]["id"],
                              track_json["track"]["name"],
                              track_json["track"]["artists"][0]["name"],
                              track_json["track"]["album"]["name"])
                tracks.append(track)

    # Now sort by date
    return sorted(tracks, key=lambda x: x.date)


def album_frequency():
    albums = {}
    for track in process_tracks():
        if track.album_id in albums:
            albums[track.album_id] += 1
        else:
            albums[track.album_id] = 1

    return albums


def get_brackets(a_freq):
    freqs = sorted(a_freq.values())
    top_prop = 0.01
    middle_prop = 0.1
    bottom_prop = 1 - (top_prop + middle_prop)

    bottom_end = int(bottom_prop * len(freqs))
    middle_end = int(bottom_end + middle_prop * len(freqs))

    bottom = freqs[0:bottom_end]
    middle = freqs[bottom_end:middle_end]
    top = freqs[middle_end:-1]

    return top[0], middle[0], bottom[0]


def get_size(freq, brackets, aid: str):
    if aid not in freq:
        # Not PC!
        print(f"aid {aid} not in freqs!")
        return 1

    top, middle, bottom = brackets

    npl = freq[aid]
    if npl > top:
        return 3

    if npl > middle:
        return 2

    return 1


def main():
    freq = album_frequency()
    brackets = get_brackets(freq)

    # placement.alloc_square(11, 0, 2)
    # placement.alloc_square(13, 2, 2)
    # placement.print_placement()
    # print(placement.can_place_at(13, 0, 2))
    # return
    base_dir = "artwork-100"
    canvas_height = 1000
    canvas_width = int(canvas_height * 1.41)  # A4
    poster_image = PosterImage(canvas_width, canvas_height)
    files = os.listdir(base_dir)
    if ".DS_Store" in files:
        files.remove(".DS_Store")
    N_posters = len(files)

    posters = [[], [], []]
    counts = [0, 0, 0]

    for file in files:
        aid = poster_id(file)
        size = get_size(freq, brackets, aid)
        posters[size - 1].append(file)
        counts[size - 1] += 1

    posters = [posters[0], posters[1], [], posters[2]]

    print(posters)
    print(counts)

    settings = compute_settings(N_posters, canvas_width, canvas_height,
                                [(1, counts[0]), (2, counts[1]), (4, counts[2])])
    print(settings.num_along, settings.num_down)
    placement = Placement(settings.num_along, settings.num_down)

    i = 0
    for size, posters_for_size in enumerate(reversed(posters)):
        size = len(posters) - size
        placement.print_placement()
        print()
        for poster in posters_for_size:
            i += 1
            if not placement.random_place(poster_id(poster), size):
                assert False

            if i % 100 == 0:
                print(f"Progress: {i}")

    print("DONE DONE DONE")
    placement.print_placement()
    placement.push_zeros_to_bottom()
    print("MOVED: ")
    placement.print_placement()



    for aid in placement.placements:
        image = Image.open(f"{base_dir}/{aid}.png")
        image = resize_for_size(image, placement.placement_size[aid], settings)
        x_row, y_row = placement.placements[aid]
        x = x_row * settings.dim
        y = y_row * settings.dim
        poster_image.add_image(image, x, y)

    poster_image.save()


if __name__ == "__main__": main()
