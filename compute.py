from typing import Tuple, List

class Settings:
    def __init__(self, num_along: int, num_down: int, dim: int):
        self.num_along = num_along
        self.num_down = num_down
        self.dim = dim


def num_can_fit(width, height, settings):
    settings.num_along = int(width / settings.dim)
    settings.num_down = int(height / settings.dim)
    return settings.num_down * settings.num_along


def compute_settings(num_squares: int, width: int, height: int, sizes: List[Tuple[int, int]]):
    # Recompute num_squares according to their size
    new_num_sq = 0
    for size, num in sizes:
        new_num_sq += (size * size) * num

    assert(new_num_sq >= num_squares)
    num_squares = new_num_sq

    total = 1000000000
    settings = Settings(0, 0, 1)

    old_total = total
    while total > num_squares:
        settings.dim += 1
        total = num_can_fit(width, height, settings)

    if total < num_squares:
        settings.dim -= 1
        total = num_can_fit(width, height, settings)

    assert(num_can_fit(width, height, settings) >= num_squares)
    return settings


if __name__ == '__main__':
    pass
