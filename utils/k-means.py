import math

import pandas as pd
import numpy as np
from collections import Counter

from mtid import read_coordinates


def distance_between(coord1, coord2):
    return ((coord2[0] - coord1[0]) ** 2 + (coord2[1] - coord1[1]) ** 2 + (coord2[2] - coord1[2]) ** 2) ** 0.5


def kmeans(points, k, max_iterations=1000):
    centroids = points[np.random.choice(points.shape[0], k, replace=False)]
    iterations = {}
    for i in range(k):
        iterations[i] = -1

    for ite in range(max_iterations):
        # Assign each point to the nearest centroid
        distances = np.sqrt(((points - centroids[:, np.newaxis]) ** 2).sum(axis=2))
        group_id = np.argmin(distances, axis=0)

        # Compute new centroids from the mean of the points in the group
        new_centroids = np.array([points[group_id == i].mean(axis=0) for i in range(k)])

        exit_flag = True
        for i in range(len(new_centroids)):
            if iterations[i] < 0 and all(centroids[i] == new_centroids[i]):
                iterations[i] = ite
            elif iterations[i] < 0:
                exit_flag = False
        if exit_flag:
            return group_id, centroids

        centroids = new_centroids

    return group_id, centroids


def check_if_exhaust(file_path, k, max_iterations=1000):
    iterations = {}
    for i in range(k):
        iterations[i] = -1

    points, centroids = read_group_formation(file_path)

    for ite in range(max_iterations):
        # Assign each point to the nearest centroid
        distances = np.sqrt(((points - centroids[:, np.newaxis]) ** 2).sum(axis=2))
        closest_centroids = np.argmin(distances, axis=0)

        new_centroids = np.array([points[closest_centroids == i].mean(axis=0) for i in range(k)])

        exit_flag = True
        for i in range(len(new_centroids)):
            if iterations[i] < 0 and all(centroids[i] == new_centroids[i]):
                iterations[i] = ite
            elif iterations[i] < 0:
                exit_flag = False
        if exit_flag:
            return list(iterations.values())

    return list(iterations.values())


def read_group_formation(file_path):
    df = pd.read_excel(file_path)

    centers = []
    points = []
    for index, row in df.iterrows():
        coordinates = eval(row['7 coordinates'])

        coordinates_array = np.array(coordinates)

        center = np.mean(coordinates_array, axis=0)
        centers.append(center)
        points.extend(coordinates_array)

    return np.array(points), np.array(centers)


def write_group_formation(name, G, groups, pair_dists, center_dists):
    df = pd.DataFrame(
        {'7 coordinates': groups, '6 dist between each pair': pair_dists, '8 distance to center': center_dists})
    df.to_excel(f"../assets/pointcloud/{name}_G{G}.xlsx", sheet_name='cliques', index=False)


if __name__ == "__main__":
    # k = 253

    group_info = [["skateboard_G3", 576], ["skateboard_G20", 86], ["dragon_G3", 253], ["dragon_G20", 38],
                  ["hat_G3", 521], ["hat_G20", 78]]

    for info in group_info:
        name = info[0]
        group_size = info[1]

        file_path = f"../assets/pointcloud/{name}.txt"
        # points, _ = read_group_formation(file_path)

        points = read_coordinates(file_path)

        k = math.ceil(len(points)/group_size)

        points = np.array(points)

        assignments, centroids = kmeans(points, k)

        groups = {}

        for point, group_id in zip(points, assignments):
            if groups.get(group_id) is None:
                groups[group_id] = []

            groups[group_id].append(list(point))

        formation = []
        pair_dists = []
        center_dists = []

        for group in groups.values():
            pair_dist = []
            center_dist = []

            center = [sum(coord[0] for coord in group) / len(group),
                      sum(coord[1] for coord in group) / len(group),
                      sum(coord[2] for coord in group) / len(group)]

            for i in range(len(group)):

                center_dist.append(distance_between(group[i], center))

                for j in range(i + 1, len(group)):
                    pair_dist.append(distance_between(group[i], group[j]))

            if len(pair_dist) == 0:
                pair_dist.append(0)

            formation.append(str(group))
            pair_dists.append(str(pair_dist))
            center_dists.append(str(center_dist))

        write_group_formation(name, group_size, formation, pair_dists, center_dists)
