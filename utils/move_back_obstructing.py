import os

from obstructing_detection import *


def normalize(v):
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return v / norm


def calculate_travel_time(max_speed, max_acceleration, max_deceleration, distance):
    t_accel = max_speed / max_acceleration
    d_accel = 0.5 * max_acceleration * t_accel ** 2

    t_decel = max_speed / max_deceleration
    d_decel = 0.5 * max_deceleration * t_decel ** 2

    if d_accel + d_decel > distance:
        # If not, find the time using a different approach (not covered here)
        d_accel = d_decel = distance / 2
        t_accel = math.sqrt(d_accel * 2 / max_acceleration)
        t_decel = math.sqrt(d_decel * 2 / max_deceleration)
        return t_accel + t_decel

    d_cruise = distance - (d_accel + d_decel)
    t_cruise = d_cruise / max_speed

    t_total = t_accel + t_cruise + t_decel

    return t_total


def get_dist_to_centroid(standbys, shape, G, file_folder, ratio):
    input_file = f"{shape}_G{G}.xlsx"

    groups = read_cliques_xlsx(f"{file_folder}/{input_file}", ratio)

    dists = []

    for i, group in enumerate(groups):
        distances = [get_distance(standbys[i], coord) for coord in group]

        dists.extend(distances)

    return dists


def dist_to_move_all(standbys, shape, G, file_folder, ratio):
    input_file = f"{shape}_G{G}.xlsx"

    groups = read_cliques_xlsx(f"{file_folder}/{input_file}", ratio)

    avg_dists = []

    for i, group in enumerate(groups):
        distances = [get_distance(standbys[i], coord) for coord in group]

        avg_dists.append(statistics.mean(distances))

    return avg_dists


def solve_single_view(shape, G, ratio, view, lastview, user_eye, group_file, output_path, test=False, file_surfix="standby"):
    tag = f"Solving: {shape}, G: {G}, Ratio: {ratio} ,{view}"
    print(tag)

    txt_file = f"{shape}.txt"
    standby_file = f"{shape}{lastview}_standby.txt"

    try:
        points, boundary, standbys = get_points_from_file(ratio, group_file, output_path, txt_file, standby_file)
    except Exception as e:
        print("File Doesn't Generated Yet, Re-generating")
        points, boundary, standbys, _ = get_points(shape, G, group_file, ratio)

    if not test:
        ori_dists_center = get_dist_to_centroid(standbys[:, 0:3], shape, G, group_file, ratio)
    else:
        ori_dists_center = [0]

    dist_illum = {}
    dist_standby = {}
    dist_between = []

    obstructing = read_coordinates(f"{output_path}/points/{shape}_{view}_blocking.txt", ' ')
    blocked_by = read_coordinates(f"{output_path}/points/{shape}_{view}_blocked.txt", ' ')

    if len(obstructing) == 0:

        if not os.path.exists(f"{output_path}/points"):
            os.makedirs(f"{output_path}/points", exist_ok=True)
        np.savetxt(f'{output_path}/points/{shape}_{view}_standby.txt', standbys, fmt='%f', delimiter=' ')
        metrics = [shape, G, ratio, view, 0, 0, 0,
                   0, 0, 0,
                   0, 0, 0,
                   0, 0, 0,
                   0, 0, 0,
                   0, 0
                   ]
        return metrics

    obstructing = np.array(obstructing)[:, 0:3]
    blocked_by = np.array(blocked_by)[:, 0:3]

    obs_list = []
    for coord in obstructing:
        # find_flag = False

        point_ids = np.where(np.all(points[:, 0:3] == coord, axis=1))[0]
        if len(point_ids) == 0:
            print(f"Obstructing Not Found: {coord}, " + tag)
        else:
            obs_list.append(point_ids[0])
        # for index, row in enumerate(points[:, 0:3]):
        # if get_distance(row, coord) < 0.3:
        #     obs_list.append(index)
        #     find_flag = True
        #     break
        # if not find_flag:
        #     print(f"Obstructing Not Found: {coord}, " + tag)

    standby_list = []
    for coord in obstructing:
        point_ids = np.where(np.all(standbys[:, 0:3] == coord, axis=1))[0][0]
        # if len(point_ids) == 0:
        #     print(f"Standby Not Found: {coord}, " + tag)
        # else:
        standby_list.append(point_ids)

    blocked_list = []
    multiple_blocking = {}
    for blocked_index, coord in enumerate(blocked_by):

        point_ids = np.where(np.all(points[:, 0:3] == coord, axis=1))[0][0]
        # if len(point_ids) == 0:
        #     print(f"Blocked Not Found: {coord}, " + tag)
        # else:
        blocked_list.append(point_ids)
        if point_ids in multiple_blocking.keys():
            if standby_list[blocked_index] not in multiple_blocking[point_ids]:
                multiple_blocking[point_ids].append(standby_list[blocked_index])
                # if len(multiple_blocking[point_ids]) == 4:
                #     for pid in multiple_blocking[point_ids]:
                #         print(standbys[pid][0:3])
        else:
            multiple_blocking[point_ids] = [standby_list[blocked_index]]

    obstruct_pairs = dict()

    # Match obstructing FLSs with only one illuminating FLS, they just needs to move once
    for uni_index in set(standby_list):
        blocked_list_indexes = np.where(standby_list == uni_index)[0]
        pair_index = None
        min_dist = float('inf')
        blocked_index_list = []
        for blocked_list_index in blocked_list_indexes:
            blocked_index_list.append(blocked_list[blocked_list_index])

        for blocked_index in set(blocked_index_list):
            dist_between.append(get_distance(standbys[uni_index][0:3], points[blocked_index][0:3]))
            dist = get_distance(user_eye, points[blocked_index][0:3])
            if dist < min_dist:
                min_dist = dist
                pair_index = blocked_index
            obstruct_pairs[blocked_list_indexes[0]] = pair_index

    multi_obst = []
    for blocking_list in list(multiple_blocking.values()):
        multi_obst.append(len(blocking_list))

    step_length = 1

    key_list = list(obstruct_pairs.keys())

    for key in key_list:
        dist_standby[standby_list[key]] = 0
        dist_illum[obstruct_pairs[key]] = 0

    change_mapping = {}
    # block_mapping = {}
    for key_index in tqdm(range(len(key_list))):
        key = key_list[key_index]
        obstructing_index = key
        standby_index = standby_list[obstructing_index]

        origin_illum_index = obstruct_pairs[key]
        if origin_illum_index in change_mapping.keys():
            illum_index = change_mapping[origin_illum_index]
        else:
            illum_index = origin_illum_index

        illum_coord = points[illum_index][0:3]

        gaze_vec = normalize(np.array(illum_coord) - user_eye)

        new_coord = illum_coord + gaze_vec

        new_pos = np.round(new_coord)

        check_times = 1
        while (not all([not is_disp_cell_overlap(new_pos, p) for p in points])
               or move_back_still_visible(user_eye, ratio, new_pos, illum_coord)):
            # for p in points:
            #     if is_disp_cell_overlap(new_pos, p):
            #         print("FOUND", p, np.where(np.all(points == p, axis=1))[0])

            new_coord += gaze_vec * step_length
            new_pos = np.round(new_coord)
            check_times += 1

        dist_standby[standby_index] += get_distance(illum_coord, obstructing[obstructing_index])
        dist_illum[origin_illum_index] += get_distance(illum_coord, new_pos)

        # print(standby_index, check_times, get_distance(illum_coord, obstructing[obstructing_index]), get_distance(illum_coord, new_pos), dist_illum[origin_illum_index], origin_illum_index)

        # points[illum_index][0:3] = new_pos
        # if change_mapping[origin_illum_index] != origin_illum_index:
        #
        #
        #     if not move_back_still_visible(user_eye, ratio, new_pos, illum_coord):
        #
        # block_mapping[origin_illum_index].append(points[obs_list[obstructing_index]][0:3])
        points[obs_list[obstructing_index]][0:3] = new_pos
        standbys[standby_list[obstructing_index]][0:3] = new_pos

        change_mapping[origin_illum_index] = obs_list[obstructing_index]

    if not os.path.exists(f"{output_path}/points"):
        os.makedirs(f"{output_path}/points", exist_ok=True)
    np.savetxt(f'{output_path}/points/{shape}_{view}_{file_surfix}.txt', standbys, fmt='%f', delimiter=' ')

    if not test:
        dists_center = get_dist_to_centroid(standbys[:, 0:3], shape, G, group_file, ratio)
    else:
        dists_center = [0]

    max_speed = max_acceleration = max_deceleration = 6.11

    dist_illum_list = list(dist_illum.values())
    dist_standby_list = list(dist_standby.values())

    metrics = [shape, G, ratio, view,
               min(dist_illum_list), max(dist_illum_list), statistics.mean(dist_illum_list),
               min(dist_standby_list), max(dist_standby_list), statistics.mean(dist_standby_list),
               len(obstruct_pairs.values()),
               min(dist_between), max(dist_between), statistics.mean(dist_between),
               min(multi_obst), max(multi_obst), statistics.mean(multi_obst),
               min(ori_dists_center), max(ori_dists_center), statistics.mean(ori_dists_center),
               calculate_travel_time(max_speed, max_acceleration, max_deceleration, statistics.mean(ori_dists_center)),
               min(dists_center), max(dists_center), statistics.mean(dists_center),
               calculate_travel_time(max_speed, max_acceleration, max_deceleration, statistics.mean(dists_center)),
               (statistics.mean(dists_center) / statistics.mean(ori_dists_center)) - 1 if statistics.mean(
                   ori_dists_center) > 0 else 0,
               (calculate_travel_time(max_speed, max_acceleration, max_deceleration, statistics.mean(dists_center)) /
                calculate_travel_time(max_speed, max_acceleration, max_deceleration,
                                      statistics.mean(ori_dists_center))) - 1
               if statistics.mean(ori_dists_center) > 0 else 0,
               multi_obst
               ]

    return metrics


def solve_obstructing(group_file, meta_direc, ratio, G_list, shape_list):
    title = [
        "Shape", "G", "Ratio", "View",
        "Min Dist Illum", "Max Dist Illum", "Avg Dist Illum",
        "Min Dist Standby", "Max Dist Standby", "Avg Dist Standby",
        "Moved Illuminating FLSs",
        "Min Dist Between", "Max Dist Between", "Avg Dist Between",
        "Min Obstructing FLSs", "Max Obstructing FLSs", "Avg Obstructing FLSs",
        "Min Ori Dist To Center", "Max Ori Dist To Center", "Avg Ori Dist To Center", "Origin MTID",
        "Min Dist To Center", "Max Dist To Center", "Avg Dist To Center", "MTID",
        "Dist To Center Change", "MTID Change", "Obstructing Nums"]
    result = [title]
    report_path = f"{meta_direc}/obstructing/Q{ratio}"
    if not os.path.exists(report_path):
        os.makedirs(report_path, exist_ok=True)

    for G in G_list:

        output_path = f"{meta_direc}/obstructing/Q{ratio}/G{G}"
        if not os.path.exists(output_path):
            os.makedirs(output_path, exist_ok=True)

        for shape in shape_list:

            txt_file = f"{shape}.txt"
            standby_file = f"{shape}_standby.txt"
            points, boundary, standbys = get_points_from_file(ratio, group_file, output_path, txt_file, standby_file)

            eye_positions = [
                # top
                [boundary[0][0] / 2 + boundary[1][0] / 2, boundary[0][1] / 2 + boundary[1][1] / 2,
                 boundary[1][2] + 100],
                # down
                [boundary[0][0] / 2 + boundary[1][0] / 2, boundary[0][1] / 2 + boundary[1][1] / 2,
                 boundary[0][2] - 100],
                # left
                [boundary[0][0] - 100, boundary[0][1] / 2 + boundary[1][1] / 2,
                 boundary[0][0] / 2 + boundary[1][0] / 2],
                # right
                [boundary[1][0] + 100, boundary[0][1] / 2 + boundary[1][1] / 2,
                 boundary[0][0] / 2 + boundary[1][0] / 2],
                # front
                [boundary[0][0] / 2 + boundary[1][0] / 2, boundary[0][1] - 100,
                 boundary[0][0] / 2 + boundary[1][0] / 2],
                # back
                [boundary[0][0] / 2 + boundary[1][0] / 2, boundary[1][1] + 100,
                 boundary[0][0] / 2 + boundary[1][0] / 2]
            ]

            views = ["top", "bottom", "left", "right", "front", "back"]

            # np.savetxt(f'{output_path}/points/{shape}_standby_solve.txt', standbys, fmt='%f', delimiter=' ')

            for i in range(len(views)):
                view = views[i]
                user_eye = eye_positions[i]
                lastview = ""
                metrics = solve_single_view(shape, G, ratio, view, lastview, user_eye, group_file, output_path,
                                            test=False)
                print(list(zip(title, metrics)))
                result.append(metrics)
    with open(f'{report_path}/solve_Q{ratio}.csv', mode='w', newline='') as file:
        writer = csv.writer(file)

        # Write the data from the list to the CSV file
        for row in result:
            writer.writerow(row)


if __name__ == "__main__":

    file_folder = "../assets/pointcloud"
    meta_dir = "../assets"
    Q_list = [1, 3, 5, 10]  # This is the list of Illumination cell to display cell ratio you would like to test.

    # Select these base on the group formation you have, see '../assets/pointclouds'
    k_list = [3, 20]  # This is the size of group constructed by the group formation technique that you would like to test.
    shape_list = ["skateboard", "dragon", "hat"]  # This is the list of shape to run this on

    for illum_to_disp_ratio in Q_list:
        solve_obstructing(file_folder, meta_dir, illum_to_disp_ratio, k_list, shape_list)
