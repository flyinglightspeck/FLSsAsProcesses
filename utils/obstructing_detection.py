import csv
import os
import statistics
import math
import numpy as np
import pandas as pd
from tqdm import tqdm
import multiprocessing as mp
import matplotlib.pyplot as plt


def is_cell_overlap(point, cube_center, length):
    return all(abs(p - c) < length - 0.00000000001 for p, c in zip(point, cube_center))


def is_disp_cell_overlap(coord1, coord2):
    return is_cell_overlap(coord1, coord2, 1)


def is_inside_cube(point, cube_center, length):
    return all(abs(p - c) < length / 2 - 0.00000000001 for p, c in zip(point, cube_center))


def is_in_illum_cell(coord1, coord2, ratio):
    return is_inside_cube(coord1, coord2, ratio - 1)


def read_cliques_xlsx(path, ratio):
    df = pd.read_excel(path, sheet_name='cliques')
    group_list = []

    for c in df["7 coordinates"]:
        coord_list = np.array(eval(c))
        coord_list = coord_list * ratio
        group_list.append(coord_list)

    return group_list


def get_points_from_file(ratio, pointcloud_folder, output_path, poitcloud_file, standby_file):
    group_standby_coord = read_coordinates(f"{output_path}/points/{standby_file}", ' ', 1)

    points = read_coordinates(f"{pointcloud_folder}/{poitcloud_file}", ' ')

    points = np.array(points)
    points = points * ratio

    point_boundary = [
        [min(points[:, 0]), min(points[:, 1]), min(points[:, 2])],
        [max(points[:, 0]), max(points[:, 1]), max(points[:, 2])]
    ]

    for coord in group_standby_coord:
        points = np.concatenate((points, [coord]), axis=0)

    return points, point_boundary, np.array(group_standby_coord)


def read_coordinates(file_path, delimeter=' ', type=0):
    coordinates = []
    try:
        with open(file_path, 'r') as file:
            for line in file:
                # Split the line by spaces and convert each part to a float
                coord = [float(x) for x in line.strip().split(delimeter)]
                if len(coord) == 3:  # Ensure that there are exactly 3 coordinates
                    coord.append(type)
                    coordinates.append(coord)
                elif len(coord) == 4:  # Ensure that there are exactly 3 coordinates
                    coord[3] = type
                    coordinates.append(coord)
                else:
                    print(f"Invalid coordinate data on line: {line.strip()}")
        return np.array(coordinates)
    except FileNotFoundError:
        print(f"The file at path {file_path} does not exist.")
        return None
    except Exception as e:
        print(f"An error occurred 5: {e}")
        return None


def get_standby_coords(groups, G):
    group_standby_coord = []

    for i in range(len(groups)):

        group = groups[i]

        if G:
            member_count = group.shape[0]
            sum_x = np.sum(group[:, 0])
            sum_y = np.sum(group[:, 1])
            sum_z = np.sum(group[:, 2])
            stand_by_coord = [
                float(round(sum_x / member_count)),
                float(round(sum_y / member_count)),
                float(round(sum_z / member_count)),
            ]
            group_standby_coord.append(stand_by_coord)

    return group_standby_coord


def get_distance(point1, point2):
    return np.linalg.norm(np.array(point1) - np.array(point2))


def ray_cell_intersection(origin, direction, point, ratio, is_standby):
    """Check if a ray intersects with a cube."""
    # Cube dimensions
    if is_standby:
        half_size = 0.5
    else:
        half_size = 0.5 * ratio

    min_corner = point - half_size
    max_corner = point + half_size

    # Compute intersection of ray with all six bbox planes
    inv_direction = 1.0 / direction
    tmin = (min_corner - origin) * inv_direction
    tmax = (max_corner - origin) * inv_direction

    # Reorder intersections to find overall min/max
    tmin, tmax = np.minimum(tmin, tmax), np.maximum(tmin, tmax)

    tmin_max = np.max(tmin)
    tmax_min = np.min(tmax)

    # If tmax_min is less than tmin_max, then no intersection
    if tmax_min < tmin_max:
        return False

    # If both tmin_max and tmax_min are negative, then ray is in opposite direction
    if tmax_min < 0:
        return False

    return True


def get_vertices(cell_center, is_standby, ratio):
    if is_standby:
        offsets = [-0.5, 0.5]
    else:
        offsets = [-0.5 * ratio, 0.5 * ratio]

    vertices = [cell_center + np.array([x, y, z]) for x in offsets for y in offsets for z in offsets]
    vertices.append(np.array(cell_center))
    vertices = np.array(vertices)
    return vertices


def move_back_still_visible(user_eye, ratio, new_pos, illum_cell):
    vertices = get_vertices(new_pos, True, ratio)

    for v_index, vertex in enumerate(vertices):

        direction = (vertex - user_eye)
        direction /= np.linalg.norm(direction)
        direction[direction == 0] = 1e-10

        if not ray_cell_intersection(user_eye, direction, illum_cell, ratio, False):
            return True

    return False


def check_visible_cell(user_eye, points, ratio):
    visible, blocking, blocked, blocking_index, potential_blocking_index = [], [], [], [], []

    distances = [get_distance(user_eye, point[:3]) for point in points]
    sorted_indices = np.argsort(distances)
    distances.sort()

    for index_dist in tqdm(range(len(sorted_indices))):
        p_index = sorted_indices[index_dist]

        cell_center = points[p_index][0:3]
        vertices = get_vertices(cell_center, points[p_index][3], ratio)

        checklist_end = index_dist
        if points[p_index][3]:
            while (distances[checklist_end] - distances[index_dist]) < ratio / 2 and checklist_end < len(distances) - 1:
                checklist_end += 1

        check_list = sorted_indices[:checklist_end]

        is_visible = [True for _ in range(len(vertices))]
        possible_visible = [True for _ in range(len(vertices))]

        b_list = []

        for v_index, vertex in enumerate(vertices):

            direction = (vertex - user_eye)
            direction /= np.linalg.norm(direction)
            direction[direction == 0] = 1e-10

            for check_index in check_list:
                if p_index == check_index:
                    continue

                point = points[check_index]

                if ray_cell_intersection(user_eye, direction, point[0:3], ratio, point[3]):
                    is_visible[v_index] = False
                    if point[3] == 0:
                        possible_visible[v_index] = False
                        break
                    else:
                        b_list.append(check_index)


        if any(is_visible):
            visible.append(points[p_index])

        if points[p_index][3] and any(possible_visible):
            for v_index, vertex in enumerate(vertices):

                direction = (vertex - user_eye)
                direction /= np.linalg.norm(direction)
                direction[direction == 0] = 1e-10

                for check_index in sorted_indices[index_dist:]:
                    if p_index == check_index:
                        continue

                    point = points[check_index]

                    if point[3] != 1 and ray_cell_intersection(user_eye, direction, point[0:3], ratio,
                                                               point[3]) and p_index not in potential_blocking_index:
                        blocking.append(points[p_index][0:3])
                        blocked.append(point[0:3])
                        potential_blocking_index.append(p_index)
                        if any(is_visible):
                            blocking_index.append(p_index)
                        break

    return np.array(visible), np.array(blocking), np.array(blocked), np.unique(blocking_index)


def get_points(shape, G, file_folder, ratio):
    input_file = f"{shape}_G{G}.xlsx"

    txt_file = f"{shape}.txt"

    groups = read_cliques_xlsx(f"{file_folder}/{input_file}", ratio)

    group_standby_coord = get_standby_coords(groups, G)

    points = read_coordinates(f"{file_folder}/{txt_file}")

    points = np.array(points)
    points = points * ratio

    point_boundary = [
        [min(points[:, 0]), min(points[:, 1]), min(points[:, 2])],
        [max(points[:, 0]), max(points[:, 1]), max(points[:, 2])]
    ]

    center = np.array([
        (min(points[:, 0]) + max(points[:, 0])) / 2,
        (min(points[:, 1]) + max(points[:, 1])) / 2,
        (min(points[:, 2]) + max(points[:, 2])) / 2
    ])

    check_times = []
    standbys = []

    for i in tqdm(range(len(group_standby_coord))):
        coord = group_standby_coord[i]

        coords = points[:, :3]

        check = 0
        if not all([not is_disp_cell_overlap(coord, c) for c in coords]):

            overlap = True
            rims_check = 1

            while overlap:
                directions = []
                for x in range(-rims_check, rims_check + 1, 1):
                    for y in range(-rims_check, rims_check + 1, 1):
                        for z in range(-rims_check, rims_check + 1, 1):
                            if x == 0 and y == 0 and z == 0:
                                continue
                            directions.append([x, y, z])

                directions = sorted(directions, key=lambda d: get_distance(d, center))
                directions = np.array(directions)

                for dirc in directions:
                    new_coord = coord + dirc * 1
                    check += 1
                    if all([not is_disp_cell_overlap(new_coord, c) for c in coords]):
                        overlap = False
                        coord = new_coord.tolist()
                        break

                if overlap:
                    if rims_check % 10 == 0:
                        print(f"Rim: {rims_check}")
                    rims_check += 1
                # break
        check_times.append(check)
        coord.append(1)
        standbys.append(coord)
        points = np.concatenate((points, [coord]), axis=0)

    return points, point_boundary, np.array(standbys), check_times


def calculate_single_view(shape, G, ratio, view, points, camera, output_path):
    print(f"START: {shape}, G: {G}, Ratio: {ratio} ,{view}")

    visible, blocking, blocked_by, blocking_index = check_visible_cell(camera, points, ratio)

    visible_illum = []
    visible_standby = []
    for point in visible:
        if point[3] == 1:
            visible_standby.append(point[0:3])
        else:
            visible_illum.append(point[0:3])

    visible_illum = np.array(visible_illum)
    np.unique(visible_illum, axis=0)

    visible_standby = np.array(visible_standby)
    np.unique(visible_standby, axis=0)

    blocking = np.array(blocking)
    np.unique(blocking, axis=0)

    blocked_by = np.array(blocked_by)
    np.unique(blocked_by, axis=0)

    if not os.path.exists(f"{output_path}/points"):
        os.makedirs(f"{output_path}/points", exist_ok=True)

    np.savetxt(f'{output_path}/points/{shape}_{view}_visible_illum.txt', visible_illum, fmt='%f',
               delimiter=' ')
    np.savetxt(f'{output_path}/points/{shape}_{view}_visible_standby.txt', visible_standby,
               fmt='%f',
               delimiter=' ')
    np.savetxt(f'{output_path}/points/{shape}_{view}_blocking.txt', blocking, fmt='%f',
               delimiter=' ')
    np.savetxt(f'{output_path}/points/{shape}_{view}_blocked.txt', blocked_by, fmt='%f',
               delimiter=' ')

    print(
        f"{shape}, G: {G}, Ratio: {ratio} ,{view} view: Number of Illuminating FLS: {len(visible_illum)}, Visible Standby FLS: {len(visible_standby)},  Obstructing Number: {len(blocking_index)}")

    metric = [shape, G, ratio, view, len(visible_illum), len(blocking_index)]
    return metric


def calculate_obstructing(group_file, meta_direc, ratio, G, shape):
    result = [
        ["Shape", "G", "Ratio", "View", "Visible_Illum", "Obstructing FLS", "Min Times Checked",
         "Mean Times Checked",
         "Max Times Checked"]]

    report_path = f"{meta_direc}/obstructing/Q{ratio}"
    if not os.path.exists(report_path):
        os.makedirs(report_path, exist_ok=True)

    output_path = f"{meta_direc}/obstructing/Q{ratio}/G{G}"
    if not os.path.exists(output_path):
        os.makedirs(output_path, exist_ok=True)

    points, boundary, standbys, check_times = get_points(shape, G, file_folder, ratio)

    # points, boundary, standbys = get_points_from_file(ratio, group_file, output_path, f"{shape}.txt", f"{shape}_standby.txt")
    # check_times = [0]

    camera_shifting = 100

    cam_positions = [
        # top
        [boundary[0][0] / 2 + boundary[1][0] / 2, boundary[0][1] / 2 + boundary[1][1] / 2,
         boundary[1][2] + camera_shifting],
        # down
        [boundary[0][0] / 2 + boundary[1][0] / 2, boundary[0][1] / 2 + boundary[1][1] / 2,
         boundary[0][2] - camera_shifting],
        # left
        [boundary[0][0] - camera_shifting, boundary[0][1] / 2 + boundary[1][1] / 2,
         boundary[0][2] / 2 + boundary[1][2] / 2],
        # right
        [boundary[1][0] + camera_shifting, boundary[0][1] / 2 + boundary[1][1] / 2,
         boundary[0][2] / 2 + boundary[1][2] / 2],
        # front
        [boundary[0][0] / 2 + boundary[1][0] / 2, boundary[0][1] - camera_shifting,
         boundary[0][2] / 2 + boundary[1][2] / 2],
        # back
        [boundary[0][0] / 2 + boundary[1][0] / 2, boundary[1][1] + camera_shifting,
         boundary[0][2] / 2 + boundary[1][2] / 2]
    ]

    views = ["top", "bottom", "left", "right", "front", "back"]

    illum = []
    standby = []
    for coord in points:
        if coord[3] == 0:
            illum.append(coord[:3])
        else:
            standby.append(coord[:3])

    illum = np.array(illum)
    standby = np.array(standby)

    if not os.path.exists(f"{output_path}/points"):
        os.makedirs(f"{output_path}/points", exist_ok=True)

    np.savetxt(f'{output_path}/points/{shape}_illum.txt', illum, fmt='%f', delimiter=' ')
    np.savetxt(f'{output_path}/points/{shape}_standby.txt', standby, fmt='%f', delimiter=' ')

    for i in range(len(views)):

        print(f"START: {shape}, G: {G}, Ratio: {ratio} ,{views[i]}")

        camera = cam_positions[i]

        visible, blocking, blocked_by, blocking_index = check_visible_cell(camera, points, ratio)

        visible_illum = []
        visible_standby = []
        for point in visible:
            if point[3] == 1:
                visible_standby.append(point[0:3])
            else:
                visible_illum.append(point[0:3])

        visible_illum = np.array(visible_illum)
        np.unique(visible_illum, axis=0)

        visible_standby = np.array(visible_standby)
        np.unique(visible_standby, axis=0)

        blocking = np.array(blocking)
        np.unique(blocking, axis=0)

        blocked_by = np.array(blocked_by)
        np.unique(blocked_by, axis=0)

        np.savetxt(f'{output_path}/points/{shape}_{views[i]}_visible_illum.txt', visible_illum, fmt='%f',
                   delimiter=' ')
        np.savetxt(f'{output_path}/points/{shape}_{views[i]}_visible_standby.txt', visible_standby,
                   fmt='%f',
                   delimiter=' ')
        np.savetxt(f'{output_path}/points/{shape}_{views[i]}_blocking.txt', blocking, fmt='%f',
                   delimiter=' ')
        np.savetxt(f'{output_path}/points/{shape}_{views[i]}_blocked.txt', blocked_by, fmt='%f',
                   delimiter=' ')

        print(
            f"{shape}, G: {G}, Ratio: {ratio} ,{views[i]} view: Number of Illuminating FLS: {len(visible_illum)}, Visible Standby FLS: {len(visible_standby)},  Obstructing Number: {len(blocking_index)}")

        result.append(
            [shape, G, ratio, views[i], len(visible_illum), len(blocking_index), min(check_times),
             statistics.mean(check_times), max(check_times)])

    with open(f'{report_path}/report_Q{ratio}_G{G}_{shape}.csv', mode='w', newline='') as file:
        writer = csv.writer(file)

        # Write the data from the list to the CSV file
        for row in result:
            writer.writerow(row)


if __name__ == "__main__":

    file_folder = "../assets/pointcloud"
    meta_dir = "../assets"

    Q_list = [1, 3, 5, 10]  # This is the list of Illumination cell to display cell ratio you would like to test.

    # Select these base on the group formation you have, see '../assets/pointclouds'
    G_list = [3, 20]  # This is the size of group constructed by the group formation technique that you would like to test.
    shape_list = ["skateboard", "dragon", "hat"]  # This is the list of shape to run this on

    for illum_to_disp_ratio in Q_list:
        for G in G_list:
            for shape in shape_list:
                calculate_obstructing(file_folder, meta_dir, illum_to_disp_ratio, G, shape)
