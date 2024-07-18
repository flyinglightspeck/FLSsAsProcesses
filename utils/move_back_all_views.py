import csv
import os

from move_back_obstructing import solve_single_view
from obstructing_detection import calculate_single_view, get_points_from_file
import multiprocessing as mp


def solve_all_views(group_file, meta_direc, ratio, G, shape):

    print(f"{shape}, Q={ratio}, G={G}")

    result_find = [
        ["Shape", "G", "Ratio", "View", "Visible_Illum", "Obstructing FLS"]]

    result_solve = [[
        "Shape", "G", "Ratio", "View",
        "Min Dist Illum", "Max Dist Illum", "Avg Dist Illum",
        "Min Dist Standby", "Max Dist Standby", "Avg Dist Standby",
        "Moved Illuminating FLSs",
        "Min Dist Between", "Max Dist Between", "Avg Dist Between",
        "Min Obstructing FLSs", "Max Obstructing FLSs", "Avg Obstructing FLSs",
        "Min Ori Dist To Center", "Max Ori Dist To Center", "Avg Ori Dist To Center", "Origin MTID",
        "Min Dist To Center", "Max Dist To Center", "Avg Dist To Center", "MTID",
        "Dist To Center Change", "MTID Change", "Obstructing Nums"]]

    report_path = f"{meta_direc}/obstructing/Q{ratio}"
    if not os.path.exists(report_path):
        os.makedirs(report_path, exist_ok=True)

    output_path = f"{meta_direc}/obstructing/Q{ratio}/G{G}"
    if not os.path.exists(output_path):
        os.makedirs(output_path, exist_ok=True)

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
    # views = ["top"]

    for i in range(len(views)):

        view = views[i]
        user_eye = eye_positions[i]

        txt_file = f"{shape}.txt"
        standby_file = f"{shape}_{views[i-1]}_standby.txt" if i > 1 else f"{shape}_back_standby.txt"
        points, boundary, standbys = get_points_from_file(ratio, group_file, output_path, txt_file, standby_file)

        metrics_find = calculate_single_view(shape, G, ratio, view, points, user_eye, output_path)
        result_find.append(metrics_find)

        metrics_solve = solve_single_view(shape, G, ratio, view, "_" + views[i - 1] if i > 1 else "_back", user_eye,
                                          group_file, output_path)

        print(metrics_solve)

        result_solve.append(metrics_solve)


    with open(f'{report_path}/report_detect_Q{ratio}_G{G}_{shape}_sec.csv', mode='w', newline='') as file:
        writer = csv.writer(file)

        # Write the data from the list to the CSV file
        for row in result_find:
            writer.writerow(row)

    with open(f'{report_path}/report_solve_Q{ratio}_G{G}_{shape}_sec.csv', mode='w', newline='') as file:
        writer = csv.writer(file)

        # Write the data from the list to the CSV file
        for row in result_solve:
            writer.writerow(row)



if __name__ == "__main__":

    file_folder = "../assets/pointcloud"
    meta_dir = "../assets/"

    Q_list = [1, 3, 5, 10]  # This is the list of Illumination cell to display cell ratio you would like to test.

    # Select these base on the group formation you have, see '../assets/pointclouds'
    G_list = [3, 20]  # This is the size of group constructed by the group formation technique that you would like to test.
    shape_list = ["skateboard", "dragon", "hat"]  # This is the list of shape to run this on

    for illum_to_disp_ratio in Q_list:
        for G in G_list:
            for shape in shape_list:
                solve_all_views(file_folder, meta_dir, illum_to_disp_ratio, G, shape)