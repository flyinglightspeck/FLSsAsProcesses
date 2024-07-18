import math
import numpy
import numpy as np
import matplotlib.pyplot as plt
from config import Config


def generate_circle_coordinates(center, radius, height, num_points, group=0):
    groups = []
    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        x = center[0] + radius * math.cos(angle)
        y = center[1] + radius * math.sin(angle)
        groups.append(np.array([[x, y, height]]))
    return groups

if __name__ == "__main__":
    group_formation = generate_circle_coordinates([10,10,10], 5, 10, 3)

    print([group[0].tolist() for group in group_formation])
