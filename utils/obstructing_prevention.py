
from collections import Counter
import matplotlib as mpl
from obstructing_detection import *


def rotate_vector(vector, angle_degrees):
    # Convert angle to radians
    angle_radians = np.radians(angle_degrees)

    pivot = [0, 0, 1]

    # Rotation matrix for z-axis rotation
    rotation_matrix = np.array([[np.cos(angle_radians), -np.sin(angle_radians), 0],
                                [np.sin(angle_radians), np.cos(angle_radians), 0],
                                [0, 0, 1]])

    # Translate vector to origin (subtract pivot), rotate, then translate back (add pivot)
    rotated_vector = np.dot(rotation_matrix, np.array(vector) - np.array(pivot)) + pivot

    return rotated_vector

def check_obstructing(user_eye, points, ratio, standbys):
    potential_blocking_index = []

    num_of_standby = 0
    num_of_illum = 0

    for point in points:
        if point[3] == 1:
            num_of_standby += 1
        else:
            num_of_illum += 1

    obstructing_list = [0 for _ in range(0, num_of_standby)]

    distances = [get_distance(user_eye, point[:3]) for point in points]
    sorted_indices = np.argsort(distances)
    distances.sort()

    obstructing_coord = []
    blocked_coord = []
    blocking_index = []

    for index_dist in tqdm(range(len(sorted_indices))):
        p_index = sorted_indices[index_dist]

        if points[p_index][3] == 0:
            continue

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

        is_obstruct = False

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

                        obstructing_coord.append(points[p_index][0:3])
                        blocked_coord.append(point[0:3])
                        potential_blocking_index.append(p_index)

                        if any(is_visible):
                            is_obstruct = True
                            blocking_index.append(p_index)
                        break
        obstructing_list[p_index - num_of_illum] = is_obstruct
        # print(f"Ori:{standbys[p_index - num_of_illum]}, GT:{points[p_index][0:3]}")

    return obstructing_list, obstructing_coord, blocked_coord


def calculate_obstructing_omnidegree(ptcld_folder, meta_direc, ratio, G, shape, granularity, write_output=True):
    # fig = plt.figure()
    # ax = fig.add_subplot(projection='3d')

    output_path = f"{meta_direc}/obstructing/Q{ratio}/G{G}"
    if not os.path.exists(output_path):
        os.makedirs(output_path, exist_ok=True)

    txt_file = f"{shape}.txt"

    try:
        standby_file = f"{shape}_standby.txt"
        points, boundary, standbys = get_points_from_file(ratio, ptcld_folder, output_path, txt_file, standby_file)
    except Exception as e:
        print("File Doesn't Generated Yet, Re-generating")
        points, boundary, standbys, _ = get_points(shape, G, ptcld_folder, ratio)

    np.savetxt(f'{output_path}/points/{shape}_standby.txt', standbys, fmt='%f', delimiter=' ')
    user_shifting = 100

    user_pos = [boundary[0][0] / 2 + boundary[1][0] / 2, boundary[0][1] - user_shifting,
                boundary[0][2] / 2 + boundary[1][2] / 2]

    shape_center = [boundary[0][0] / 2 + boundary[1][0] / 2, boundary[0][1] / 2 + boundary[1][1] / 2,
                    boundary[0][2] / 2 + boundary[1][2] / 2]

    vector = np.array(user_pos) - np.array(shape_center)

    degree_obst_map = dict()

    for i in range(0, math.floor(360 / granularity)):
        try:
            points, boundary, standbys = get_points_from_file(ratio, ptcld_folder, output_path, txt_file, standby_file)
        except Exception as e:
            points, boundary, standbys, _ = get_points(shape, G, ptcld_folder, ratio)

        angle = i * granularity

        user_pos = shape_center + rotate_vector(vector, angle)
        # ax.scatter(*user_pos)

        print(f"START: {shape}, G: {G}, Ratio: {ratio}, Angle:{angle}")

        obstructing_list, obstructing_coord, blocked_coord = check_obstructing(user_pos, points, ratio, standbys)

        if not os.path.exists(f"{output_path}/points"):
            os.makedirs(f"{output_path}/points", exist_ok=True)

        if write_output:
            np.savetxt(f'{output_path}/points/{shape}_{granularity}_{i}.txt', obstructing_list, fmt='%d', delimiter=' ')

        np.savetxt(f'{output_path}/points/{shape}_{granularity}_{i}_blocking.txt', obstructing_coord, fmt='%f',
                   delimiter=' ')
        np.savetxt(f'{output_path}/points/{shape}_{granularity}_{i}_blocked.txt', blocked_coord, fmt='%f',
                   delimiter=' ')

        print(
            f"{shape}, G: {G}, Ratio: {ratio} ,view: {angle}, Number of Illuminating FLS: {Counter(obstructing_list)}")

        degree_obst_map[angle] = obstructing_list

    return degree_obst_map
    # plt.show()


def run_with_multiProcess(ptcld_folder, meta_dir, illum_to_disp_ratio, granularity):
    for k in [3, 20]:
        for shape in ["skateboard", "dragon", "hat"]:
            calculate_obstructing_omnidegree(ptcld_folder, meta_dir, illum_to_disp_ratio, k, shape, granularity)


def prevent_obstructions(ptcld_folder, meta_direc, ratio, G, shape, granularity, obstructing_maps=None):
    output_path = f"{meta_direc}/obstructing/Q{ratio}/G{G}"

    txt_file = f"{shape}.txt"
    standby_file = f"{shape}_standby.txt"

    try:
        _, boundary, standbys = get_points_from_file(ratio, ptcld_folder, output_path, txt_file, standby_file)
    except Exception as e:
        _, boundary, standbys, _ = get_points(shape, G, ptcld_folder, ratio)

    points = read_coordinates(f"{ptcld_folder}/{txt_file}", ' ')
    points = np.array(points)
    points = points * ratio


    if obstructing_maps:
        combined_obstruction_map = np.sum(obstructing_maps.values())
    else:
        combined_obstruction_map = read_obstruction_maps(output_path, shape, granularity)

    print(sum(combined_obstruction_map))
    # return
    standbys = standbys[:, :3]
    # get the indices of the elements that are non-zero
    obs_idx = np.nonzero(combined_obstruction_map)
    obs_stb_coords = standbys[obs_idx]

    if ratio >= 3:
        closest_ill_coords = closest_points(standbys, points[:, :3])
        new_obs_stb_coords = closest_ill_coords + np.array([0, 0, -1])
        # print(new_obs_stb_coords)
        # return
        # print(standbys)
        # standbys[list(obs_idx)] = new_obs_stb_coords
        standbys = new_obs_stb_coords
        # print(standbys)

        move_back_path = f"{meta_dir}/obstructing/Q{ratio}/G{G}"

        if not os.path.exists(f"{move_back_path}/points"):
            os.makedirs(f"{move_back_path}/points", exist_ok=True)

        np.savetxt(f'{move_back_path}/points/{shape}_back_standby.txt', standbys, fmt='%d', delimiter=' ')


def closest_points(A, B):
    """
    Find the closest point in B to each point in A.

    Parameters:
    A (numpy array): an array of 3D coordinates.
    B (numpy array): another array of 3D coordinates.

    Returns:
    numpy array: an array of the closest points in B for each point in A.
    """
    closest_indices = np.argmin(np.linalg.norm(A[:, np.newaxis] - B, axis=2), axis=1)
    return B[closest_indices]


def read_obstruction_maps(output_path, shape, granularity):
    maps =[]
    for i in range(360 // granularity):
        maps.append(np.loadtxt(f'{output_path}/points/{shape}_{granularity}_{i}.txt'))

    return np.sum(maps, axis=0)


if __name__ == "__main__":
    mpl.use('macosx')

    ptcld_folder = "../assets/pointcloud"
    meta_dir = "../assets"

    # We assume the user walk as a circle, centering the center of the shape.
    # Each time, the user will walk and the vector pointing from the center of the shape toward the user's eye will form
    # a {granularity} degree angle with the previous one.
    granularity = 10  # the granularity of degree changes.

    Q_list = [1, 3, 5, 10]  # This is the list of Illumination cell to display cell ratio you would like to test.


    # Select these base on the group formation you have, see '../assets/pointclouds'
    G_list = [3, 20]  # This is the size of group constructed by the group formation technique that you would like to test.
    shape_list = ["skateboard", "dragon", "hat"]  # This is the list of shape to run this on

    # for illum_to_disp_ratio in Q_list:
    #     for G in G_list:
    #         for shape in shape_list:
    #             calculate_obstructing_omnidegree(ptcld_folder, meta_dir, illum_to_disp_ratio, G, shape, granularity)

    for illum_to_disp_ratio in Q_list:
        for G in G_list:
            for shape in shape_list:
                prevent_obstructions(ptcld_folder, meta_dir, illum_to_disp_ratio, G, shape, granularity)