from PIL import Image
import random
import requests
import shutil
import os
from compute import *
import json
import dateutil.parser

ALBUMS_TO_IGNORE = [
    "3UVJu0QdTJBfGJBl1AMWEM"  # Remaster version of Either/Or - just use original instead
]


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

    def __init__(self, width, height, left_margin, top_margin):
        self.width = width
        self.height = height
        self.left_margin = left_margin
        self.top_margin = top_margin
        self.base = Image.new("RGB", (width, height), "white")

    def add_image(self, image: Image, x_pos: float, y_pos: float):
        self.base.paste(image, (x_pos + self.left_margin, y_pos + self.top_margin))

    def save(self):
        self.base.save("out.png")


class PosterFitter:

    def __init__(self, images: [Image], poster: PosterImage):
        self.images = images
        self.poster = poster

        # Soft widths we use that are expanded as needed
        self.width = 0
        self.height = 0


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
        return y * self.n_x + x

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

    def random_place(self, aid: str, size: int, border_basic=0, border_bottom_x=0, border_bottom_y=0):
        # First get list of coords with unallocated space
        spaces = []
        for x in range(self.n_x):
            for y in range(self.n_y):
                can_place = self.can_place_at(x, y, size)
                in_border = (
                                    x + border_bottom_x + size - 1 < self.n_x and y + border_bottom_y + size - 1 < self.n_y) and (
                                    x >= border_basic and y >= border_basic)
                if can_place and in_border:
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

    def place_first_fit(self, aid: str, size: int):
        for y in range(self.n_y):
            for x in range(self.n_x):
                if self.can_place_at(x, y, size):
                    self.placements[aid] = (x, y)
                    self.alloc_square(x, y, size)
                    self.placement_size[aid] = size
                    return True

        return False

    def idx_to_coords(self, idx):
        x_pos = idx % self.n_x
        y_pos = int(idx / self.n_x)
        return x_pos, y_pos

    def alloc_all_size_ones(self, album_ids):
        idx = 0
        for aid in album_ids:
            while self.places[idx] == 1:
                idx += 1

            x, y = self.idx_to_coords(idx)
            self.placements[aid] = (x, y)
            self.alloc_square(x, y, 1)
            self.placement_size[aid] = 1

    def find_aid_for_index(self, idx):
        x, y = self.idx_to_coords(idx)
        for aid in self.placements:
            if self.placements[aid] == (x, y):
                return aid

    def remove_final_ones(self):
        row = self.n_y - 1
        while row > 0:
            if self.is_free(0, row):
                row -= 1
                continue

            for col in range(self.n_x):
                idx = self._xy_to_index(col, row)
                if self.places[idx] == 0:
                    break

                aid = self.find_aid_for_index(idx)
                self.places[idx] = 0
                self.placement_size[aid] = 0
                del self.placements[aid]
            break


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


def get_files(base_dir: str):
    files = os.listdir(base_dir)
    if ".DS_Store" in files:
        files.remove(".DS_Store")

    for aid in ALBUMS_TO_IGNORE:
        if f"{aid}.png" in files:
            files.remove(f"{aid}.png")
            print(f"Removed {aid}")

    return files


def do_allocation(settings: Settings, posters):
    placement = Placement(settings.num_along - settings.excess_cols, settings.num_down)

    i = 0
    for size, posters_for_size in enumerate(reversed(posters)):
        size = len(posters) - size
        placement.print_placement()
        print()

        if size == 1:
            placement.alloc_all_size_ones(map(lambda p: poster_id(p), posters_for_size))
            break

        for poster in posters_for_size:
            i += 1

            border = 1 + settings.excess_rows
            if not placement.random_place(poster_id(poster), size, 1, border, border):
                assert False

            if i % 100 == 0:
                print(f"Progress: {i}")
    placement.print_placement()
    print("Remove ones:")
    placement.remove_final_ones()
    placement.print_placement()
    return placement


def main():
    freq = album_frequency()
    brackets = get_brackets(freq)

    base_dir = "artwork"
    canvas_height = 9933
    canvas_width = 14043

    # canvas_height = 1000
    # canvas_width = 1400

    files = get_files(base_dir)

    N_posters = len(files)

    posters = [[], [], []]
    counts = [0, 0, 0]

    for file in files:
        aid = poster_id(file)
        size = get_size(freq, brackets, aid)
        posters[size - 1].append(file)
        counts[size - 1] += 1

    posters = [posters[0], posters[1], [], posters[2]]

    settings = compute_settings(N_posters, canvas_width, canvas_height,
                                [(1, counts[0]), (2, counts[1]), (4, counts[2])])
    poster_image = PosterImage(canvas_width, canvas_height, int(settings.right_margin_px / 2),
                               int(settings.bottom_margin_px / 2))

    # Remove small number of albums we can't fit exactly in one square
    # Not yet sorted so we are removing posters with smallest num. of plays
    # posters[0] = posters[0][settings.num_in_incomplete_row:]
    placement = do_allocation(settings, posters)

    i = 0
    N = len(placement.placements.keys())
    for aid in placement.placements:
        i += 1
        image = Image.open(f"{base_dir}/{aid}.png")
        image = resize_for_size(image, placement.placement_size[aid], settings)
        x_row, y_row = placement.placements[aid]
        x = x_row * settings.dim
        y = y_row * settings.dim
        poster_image.add_image(image, x, y)
        if i % 10 == 0:
            print(f"{int(100 * i / N)}% Placing images")

    print("Done - saving")
    poster_image.save()


if __name__ == "__main__": main()
