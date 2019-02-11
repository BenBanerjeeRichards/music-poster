from typing import Tuple, List
import math


class Settings:
    def __init__(self, num_along: int, num_down: int, dim: int, excess_squares: int):
        self.num_along = num_along
        self.num_down = num_down
        self.dim = dim
        self.excess_squares = excess_squares
        self.excess_rows = 0
        self.excess_cols = 0
        self.num_in_incomplete_row = 0
        self.right_margin_px = 0
        self.bottom_margin_px = 0


def num_can_fit(width, height, settings):
    settings.num_along = int(width / settings.dim)
    settings.num_down = int(height / settings.dim)
    return settings.num_down * settings.num_along


def compute_settings(num_squares: int, width: int, height: int, sizes: List[Tuple[int, int]]):
    # Recompute num_squares according to their size
    N_posters = num_squares
    new_num_sq = 0
    for size, num in sizes:
        new_num_sq += (size * size) * num

    assert (new_num_sq >= num_squares)
    num_squares = new_num_sq

    total = 1000000000
    settings = Settings(0, 0, 1, 0)

    while total > num_squares:
        settings.dim += 1
        total = num_can_fit(width, height, settings)

    if total < num_squares:
        settings.dim -= 1

    assert (num_can_fit(width, height, settings) >= num_squares)

    # compute the excess number of squares
    settings.excess_squares = (settings.num_down * settings.num_along) - num_squares
    settings.excess_rows = int(settings.excess_squares / settings.num_along)
    ratio = settings.num_along / settings.num_down

    # Solve system of equations
    excess_x = int(settings.excess_squares / (ratio + 1))
    excess_y = settings.excess_squares - excess_x

    # If not enough of y just put all in x
    if excess_y < settings.num_down:
        excess_x += excess_y
        excess_y = 0

    # Now add remainder of y to x
    additional_y = excess_y - int((excess_y / settings.num_down)) * settings.num_down
    assert additional_y >= 0
    excess_y -= additional_y
    excess_x += additional_y

    assert (excess_x + excess_y == settings.excess_squares)

    settings.excess_rows = math.ceil(excess_x / settings.num_along)
    settings.excess_cols = math.ceil(excess_y / settings.num_down)

    settings.num_in_incomplete_row = int(
        settings.num_along * ((excess_x / settings.num_along) - int(excess_x / settings.num_along)))

    # Determine how much the margins are (assuming excess images cut off so we can round x down)
    # This allows for the image to be centered
    # Note margins are the full margin, not half

    settings.right_margin_px = math.ceil(
        settings.dim * (((width / settings.dim) - settings.num_along) + settings.excess_cols))
    settings.bottom_margin_px = math.ceil(
        settings.dim * (((height / settings.dim) - settings.num_down) + settings.excess_rows))

    print_settings(settings, width, height, sizes, N_posters)

    # Some sanity checks
    assert (settings.right_margin_px >= 0)
    assert (settings.bottom_margin_px >= 0)
    return settings


def print_settings(settings: Settings, canvas_width, canvas_height, counts, N_posters):
    num_sq = counts[0][1] + 4 * counts[1][1] + 16 * counts[2][1]
    print("across x down: ", settings.num_along, settings.num_down)
    print("width x height: ", canvas_width, canvas_height)
    print("N posters: ", N_posters)
    print("Counts: ", counts)
    print("New num posters", num_sq)
    print("Diff = ", settings.num_along * settings.num_down - num_sq)
    print("dim = ", settings.dim)
    print("Excess squares = ", settings.excess_squares)
    print("Excess cols = ", settings.excess_cols)
    print("Excess rows = ", settings.excess_rows)
    print("Num in final row = ", settings.num_in_incomplete_row)
    print("Right margin = ", settings.right_margin_px)
    print("Bottom margin = ", settings.bottom_margin_px)


if __name__ == '__main__':
    pass
