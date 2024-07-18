import json
from itertools import chain

import numpy as np
import pandas as pd
import os
import csv
import math
import ast

from matplotlib import pyplot as plt

from config import Config
from worker.metrics import gen_point_metrics_no_group
from utils.file import write_csv
from utils.log import logger


def get_report_metrics(dir_meta, time_range, group_num):
    json_file_path = os.path.join(dir_meta, 'charts.json')
    csv_path_flss = os.path.join(dir_meta, 'flss.csv')
    csv_path_points = os.path.join(dir_meta, 'illuminating.csv')

    try:
        # Read the JSON file
        with open(json_file_path, 'r') as json_file:
            data = json.load(json_file)

        metrics = []

        for metric_name in ['dispatched', 'failed', 'mid_flight', 'illuminating']:
            if data[metric_name]['t'][-1] < time_range[1]:
                metrics.append(data[metric_name]['y'][-1])
            else:
                for i in range(len(data[metric_name]['t']) - 1, -1, -1):
                    if data[metric_name]['t'][i] <= time_range[1]:
                        metrics.append(data[metric_name]['y'][i])
                        break

        # for metric_name in ['mid_flight', 'illuminating']:
        #     avg_value = 0
        #     counter = 0
        #     for i in range(len(data[metric_name]['t'])):
        #         if time_range[0] <= data[metric_name]['t'][i] <= time_range[1]:
        #             avg_value += data[metric_name]['y'][i]
        #             counter += 1
        #     try:
        #         metrics.append(avg_value / counter)
        #     except Exception as e:
        #         print(f"An error occurred: {e}")
        #         metrics.append(0)

        metrics.extend(get_metrics_by_name(csv_path_flss, time_range[0], '27_time_to_fail'))
        metrics.extend(get_metrics_by_name(csv_path_flss, time_range[0], '26_dist_traveled'))

        metrics.extend(get_mttr_by_group(csv_path_points, 1))

    except Exception as e:
        print(f"An error occurred: {e}")

    return metrics


def read_sanity_metrics(dir_meta, time_range):
    json_file_path = os.path.join(dir_meta, 'charts.json')
    csv_path_mttf = os.path.join(dir_meta, 'flss.csv')
    csv_path_mttr = os.path.join(dir_meta, 'illuminating.csv')
    try:
        # Read the JSON file
        with open(json_file_path, 'r') as json_file:
            data = json.load(json_file)

        metrics = []

        if data['failed']['t'][-1] < time_range[1]:
            metrics.append(data['failed']['y'][-1])
        else:
            for i in range(len(data['failed']['t']) - 1, -1, -1):
                if data['failed']['t'][i] <= time_range[1]:
                    metrics.append(data['failed']['y'][i])
                    break

        for metric_name in ['mid_flight', 'illuminating']:
            avg_value = 0
            counter = 0
            for i in range(len(data[metric_name]['t'])):
                if time_range[0] <= data[metric_name]['t'][i] <= time_range[1]:
                    avg_value += data[metric_name]['y'][i]
                    counter += 1
            try:
                if counter > 0:
                    metrics.append(avg_value / counter)
                else:
                    metrics.append(0)
            except Exception as e:
                print(f"An error occurred: {e}")
                metrics.append(0)

        metrics.append(calculate_mean(csv_path_mttf, "27_time_to_fail"))
        metrics.append(calculate_mttr(csv_path_mttr))

    except Exception as e:
        print(f"An error occurred: {e}")

    return metrics


def calculate_mttr(csv_path):
    wait_list = []

    with open(csv_path, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                if row['hub wait times'] != "[]":
                    wait_list.extend(row['hub wait times'][1:-1].split(', '))
                if row['standby wait times'] != "[]":
                    wait_list.extend(row['standby wait times'][1:-1].split(', '))
            except ValueError:
                # Skip rows where the value is not a number
                continue

    if not wait_list:
        return -1

    float_list = [float(s) for s in wait_list]
    return sum(float_list) / len(float_list)


def calculate_mean(csv_path, column_heading):
    values = []

    with open(csv_path, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                value = float(row[column_heading])
                if value > 0:
                    values.append(value)
            except ValueError:
                # Skip rows where the value is not a number
                continue

    if not values:
        return None

    return sum(values) / len(values)

def get_last_min_QoI(file_path, total_points, end_time):
    with open(file_path, 'r') as file:
        data = json.load(file)

    # Extract the 'illuminating' data
    illuminating_data = data.get('illuminating', {})
    timestamps = illuminating_data.get('t', [])
    values = illuminating_data.get('y', [])

    # Calculate the average value per second
    # Assuming the timestamps are in seconds and are integers
    averages_per_second = []
    for second in range(end_time - 60, end_time + 1):
        values_in_second = [value for timestamp, value in zip(timestamps, values) if (timestamp >= second and timestamp< second + 1)]
        if values_in_second:
            averages_per_second.append(np.mean(values_in_second))

    # Calculate the overall average of the averages per second
    overall_average = np.mean(averages_per_second) if averages_per_second else None

    if total_points == 0:
        return 0

    return overall_average/total_points


def get_metrics_by_name(csv_path, start_time, metric_name):
    values = []
    with open(csv_path, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                # Reset after initial FLSs dispatched, only count those were not initial FLSs
                # if eval(row[metric_name]) >= 0 and eval(row['timeline'])[0][0] >= start_time:
                if eval(row[metric_name]) >= 0:
                    values.append(eval(row[metric_name]))
            except ValueError:
                # Skip rows where the value is not a number
                continue

    if not values:
        return [0, 0, 0, 0]
    values.sort()

    mid = len(values) // 2
    median = (values[mid] + values[~mid]) / 2

    return [sum(values) / len(values), values[0], values[-1], median]


def get_mttr_by_group(csv_path, group_num):
    mttr = [[] for i in range(group_num)]
    with open(csv_path, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                group_id = int(row['group_id'])

                if row['hub wait times'] != "[]":
                    mttr[group_id].extend(eval(row['hub wait times']))

                if row['standby wait times'] != "[]":
                    mttr[group_id].extend(eval(row['standby wait times']))

            except ValueError:
                # Skip rows where the value is not a number
                continue

    if mttr is None or mttr == [[] for i in range(group_num)]:
        return [0, 0, 0, 0]

    mttr_all = (list(chain.from_iterable(mttr)))
    mttr_all.sort()

    mid = len(mttr_all) // 2
    median = (mttr_all[mid] + mttr_all[~mid]) / 2

    return [sum(mttr_all) / len(mttr_all), mttr_all[0], mttr_all[-1], median]


def get_mttr(csv_path):
    mttr = []
    with open(csv_path, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                if row['hub wait times'] != "[]":
                    mttr.extend(eval(row['hub wait times']))

                if row['standby wait times'] != "[]":
                    mttr.extend(eval(row['standby wait times']))

            except ValueError:
                # Skip rows where the value is not a number
                continue

    if not mttr:
        return [0, 0, 0, 0]

    mttr_all = (list(chain.from_iterable(mttr)))
    mttr_all.sort()
    mid = len(mttr_all) // 2
    median = (mttr_all[mid] + mttr_all[~mid]) / 2

    return [sum(mttr_all) / len(mttr_all), mttr_all[0], mttr_all[-1], median]


def get_report_metrics_no_group(dir_meta, time_range):
    json_file_path = os.path.join(dir_meta, 'charts.json')
    csv_path_flss = os.path.join(dir_meta, 'flss.csv')
    csv_path_points = os.path.join(dir_meta, 'illuminating.csv')

    try:
        # Read the JSON file
        with open(json_file_path, 'r') as json_file:
            data = json.load(json_file)

        metrics = []

        for metric_name in ['illuminating', 'dispatched', 'failed']:

            if data[metric_name]['t'][-1] < time_range[0]:
                metrics.append(data[metric_name]['y'][-1])
            else:
                for i in range(len(data[metric_name]['t'])):
                    if data[metric_name]['t'][i] >= time_range[0]:
                        if i < 0:
                            metrics.append(0)
                        elif data[metric_name]['t'][i] > time_range[0]:
                            metrics.append(data[metric_name]['y'][i - 1])
                        else:
                            metrics.append(data[metric_name]['y'][i])
                        break

            if data[metric_name]['t'][0] > time_range[1]:
                metrics.append(data[metric_name]['y'][0] - metrics[-1])
            else:
                for i in range(len(data[metric_name]['t']) - 1, -1, -1):
                    if data[metric_name]['t'][i] <= time_range[1]:
                        metrics.append(data[metric_name]['y'][i] - metrics[-1])
                        break

        initial_illum_num = metrics[2]
        metrics[1] += metrics[0]
        metrics[0] = metrics[0]/initial_illum_num if initial_illum_num > 0 else 0
        metrics[1] = metrics[1]/initial_illum_num if initial_illum_num > 0 else 0

        metrics.insert(0, get_last_min_QoI(json_file_path, initial_illum_num, Config.DURATION))

        logger.info(f"QoI In Last Min: {metrics[0]}")

        for metric_name in ['mid_flight', 'illuminating', 'standby']:
            if data[metric_name]['t'][0] > time_range[1]:
                metrics.append(data[metric_name]['y'][0])
            else:
                for i in range(len(data[metric_name]['t']) - 1, -1, -1):
                    if data[metric_name]['t'][i] <= time_range[1]:
                        metrics.append(data[metric_name]['y'][i])
                        break

        metrics.extend(get_metrics_by_name(csv_path_flss, time_range[0], '27_time_to_fail'))
        metrics.extend(get_metrics_by_name(csv_path_flss, time_range[0], '26_dist_traveled'))

        metrics.extend(get_mttr_by_group(csv_path_points, 1))

    except Exception as e:
        print(f"An error occurred: {e}")

    return metrics


# def create_csv_from_timeline(directory):
#     if not os.path.exists(directory):
#         return
#
#     with open(os.path.join(directory, '.json'), "r") as file:
#         timeline = json.load(file)
#
#     point_metrics, standby_metrics = gen_point_metrics_no_group(timeline, 0)
#     write_csv(directory, point_metrics, 'illuminating')
#     write_csv(directory, standby_metrics, 'standby')
#
#     return timeline


def write_final_report(csv_file_path, target_file_path, name, group_num, time_range):
    # if os.path.exists(os.path.join(csv_file_path, name +'_final_report.csv')):
    #     return

    report_key = [
        "QoI in Last Minute",
        "QoI Before Reset",
        "QoI After Reset",
        "Dispatched Before Reset",
        "Dispatched After Reset",
        "Failure Before Reset",
        "Failure After Reset",
        "Mid-Flight",
        "Illuminating",
        "Stationary Standby",
        "Avg Travel Time",
        "Min Travel Time",
        "Max Travel Time",
        "Median Travel Time",
        "Avg Dist Traveled",
        "Min Dist Traveled",
        "Max Dist Traveled",
        "Median Dist Traveled",
        "Avg MTID",
        "Min MTID",
        "Max MTID",
        "Median MTID",
        "Deploy Rate Before Reset",
        "Deploy Rate After Reset",
        "Number of Groups",
    ]
    report_metrics = get_report_metrics_no_group(csv_file_path, time_range)

    # logger.info(f"REPORT METRIC={report_metrics}")

    report_metrics = [metric for metric in report_metrics]

    if time_range[0] != 0:
        report_metrics.append(report_metrics[3] / (time_range[0]))
    else:
        report_metrics.append(0)

    report_metrics.append(report_metrics[4] / (Config.DURATION - time_range[0]))

    report_metrics.append(group_num)
    report = []

    for i in range(len(report_key)):
        report.append([report_key[i], report_metrics[i]])

    df = pd.read_csv(os.path.join(csv_file_path, 'flss.csv'))
    df = df[df['timeline'].apply(lambda x: ast.literal_eval(x)[0][0]) >= time_range[0]]

    # 3. Split the dataframe based on the condition
    dist1 = df[df['timeline'].str.contains(' 1, ')]

    # exclude standby FLSs that failed on its way to recover a failed Illuminating FLS
    dist2 = df[~df['timeline'].str.contains(' 1, ')]
    dist2 = dist2[~dist2['timeline'].str.contains(' 4, ')]

    dist3 = df[df['timeline'].str.contains(' 2, ')]
    dist3 = dist3[dist3['timeline'].str.contains(' 6, ')]
    dist_3_list = []
    for i in dist3.index:
        fls_timeline = eval(dist3['timeline'][i])
        for event in fls_timeline:
            if event[1] == 2:
                standby_coord = event[2]
            elif event[1] == 6:
                dist_3_list.append(distance_between(standby_coord, event[2]))
                break

    dist4 = df[df['timeline'].str.contains(' 6, ')]
    dist4 = dist4[~dist4['timeline'].str.contains(' 2, ')]

    dispatcher_coords = get_dispatcher_coords()

    dist_standby_hub_to_centroid = df[df['timeline'].str.contains(' 2, ')]
    dist_hub_to_centroid = []

    for i in dist_standby_hub_to_centroid.index:
        fls_timeline = eval(dist_standby_hub_to_centroid['timeline'][i])

        for event in fls_timeline:
            if event[1] == 2:
                standby_coord = event[2]
                dispatcher_coord = check_dispatcher(dispatcher_coords, standby_coord)
                dist_hub_to_centroid.append(distance_between(dispatcher_coord, standby_coord))
                break

    dist_standby_hub_to_fail_before_centroid = df[df['timeline'].str.contains(' 5, ')]
    dist_standby_hub_to_fail_before_centroid = dist_standby_hub_to_fail_before_centroid[
        ~dist_standby_hub_to_fail_before_centroid['timeline'].str.contains(' 4, ')]

    dist_standby_centroid_to_fail_before_recovered = df[df['timeline'].str.contains(' 2, ')]

    dist_standby_centroid_to_fail_before_recovered = dist_standby_centroid_to_fail_before_recovered[
        dist_standby_centroid_to_fail_before_recovered['timeline'].str.contains(' 4, ')]
    dist_standby_centroid_to_fail_before_recovered = dist_standby_centroid_to_fail_before_recovered[
        dist_standby_centroid_to_fail_before_recovered['timeline'].str.contains(' 5, ')]
    dist_standby_centroid_to_fail_before_recovered = dist_standby_centroid_to_fail_before_recovered[
        ~dist_standby_centroid_to_fail_before_recovered['timeline'].str.contains(' 6, ')]
    dist_centroid_to_fail = []
    for i in dist_standby_centroid_to_fail_before_recovered.index:
        fls_timeline = eval(dist_standby_centroid_to_fail_before_recovered['timeline'][i])
        for event in fls_timeline:
            if event[1] == 2:
                standby_coord = event[2]
                dispatcher_coord = check_dispatcher(dispatcher_coords, standby_coord)
                dist_centroid_to_fail.append(dist_standby_centroid_to_fail_before_recovered['26_dist_traveled'][i] -
                                             distance_between(dispatcher_coord, standby_coord))
                break

    # Extract '26_dist_traveled' column values
    dist1_values = dist1['26_dist_traveled']
    dist2_values = dist2['26_dist_traveled']
    # dist3_values = dist3['26_dist_traveled']
    dist4_values = dist4['26_dist_traveled']
    # dist_standby_hub_to_centroid = dist_standby_hub_to_centroid['26_dist_traveled']
    dist_standby_hub_to_fail_before_centroid = dist_standby_hub_to_fail_before_centroid['26_dist_traveled']
    # dist_standby_centroid_to_fail_before_recovered = dist_standby_centroid_to_fail_before_recovered['26_dist_traveled']

    min_value = []
    max_value = []
    average_value = []
    median_value = []

    # 4. Calculate the required statistics for sheet1
    values = [dist1_values, dist2_values, dist_3_list, dist4_values,
              dist_hub_to_centroid,
              dist_standby_hub_to_fail_before_centroid,
              dist_centroid_to_fail]

    for value in values:
        if not isinstance(value, list):
            value = value.tolist()
        value.sort()

        mid = len(value) // 2
        median = (value[mid] + value[~mid]) / 2 if mid > 0 else 0

        min_value.append(value[0] if len(value) > 0 else 0)
        max_value.append(value[-1] if len(value) > 0 else 0)
        average_value.append(sum(value) / len(value) if len(value) > 0 else 0)
        median_value.append(median)

    titles_type = ['dist_arrived_illuminate', 'dist_failed_midflight_illuminate',
                   'dist_stationary_standby_recover_illuminate', 'dist_midflight_standby_recover_illuminate',
                   'dist_standby_hub_to_centroid',
                   'dist_standby_hub_to_fail_before_centroid', 'dist_standby_centroid_to_fail_before_recovered']

    for i, title in enumerate(titles_type):
        report.append(['Min_' + title, min_value[i]])
        report.append(['Max_' + title, max_value[i]])
        report.append(['Avg_' + title, average_value[i]])
        report.append(['Median_' + title, median_value[i]])

    df = pd.read_csv(os.path.join(csv_file_path, 'illuminating.csv'))
    recover_by_hub = df['recovered by hub']
    recover_by_standby = df['recovered by standby']

    report.append(['Illuminate Recovered_By_HUB', sum(recover_by_hub)])
    report.append(['Illuminate Recovered_By_Standby', sum(recover_by_standby)])

    df = pd.read_csv(os.path.join(csv_file_path, 'standby.csv'))
    standby_recover_by_hub = df['recovered by hub']

    report.append(['Stdby_Recovered_By_Hub', sum(standby_recover_by_hub)])

    df = pd.read_csv(os.path.join(csv_file_path, 'metrics.csv'))
    filtered_row = df[df['Metric'] == 'Queued FLSs']
    report.append(['Num_FLSs_Queued', filtered_row['Value'].iloc[0]])

    with open(os.path.join(csv_file_path, 'bucket_face_G0_R90_T60_S6_PTrue.json'), 'r') as json_file:
        events = json.load(json_file)
        failed_standby = 0
        failed_illum = 0
        for event in events:
            if event[0] <= time_range[0]:
                continue
            if event[1] == 3:
                failed_illum += 1
            elif event[1] == 5:
                failed_standby += 1

    report.append(['Failed Illuminating FLS', failed_illum])
    report.append(['Failed Standby FLS', failed_standby])

    filtered_row = df[df['Metric'] == 'Handled failures']
    report.append(['Hub_Deployed_FLS', filtered_row['Value'].iloc[0]])
    filtered_row = df[df['Metric'] == 'Handled replica illuminating FLSs']
    # filtered_row = df[df['Metric'] == 'Dispatched replica illuminating FLSs']
    report.append(['Hub_Deployed_FLS_To_Illuminate', filtered_row['Value'].iloc[0]])
    filtered_row = df[df['Metric'] == 'Handled replica standby FLSs']
    # filtered_row = df[df['Metric'] == 'Dispatched replica standby FLSs']
    report.append(['Hub_Deployed_FLS_For_Standby', filtered_row['Value'].iloc[0]])

    df = pd.DataFrame(data=None, columns=['', 'Value'])
    for row in report:
        # if len(df) >= 35:
        #     break
        df.loc[len(df)] = row

    try:
        name = name.replace("_test0", "")
        writer = pd.ExcelWriter(os.path.join(target_file_path, name + '_final_report.xlsx'), engine='openpyxl')

        df.to_excel(writer, sheet_name='Metrics')

        with open(os.path.join(csv_file_path, 'charts.json'), 'r') as json_file:
            function_of_time = json.load(json_file)

        # metric_names = ['illuminating']
        # for metric_name in metric_names:
        #     df = pd.DataFrame()
        #     df['Time'] = function_of_time[metric_name]['t']
        #     df['Value'] = function_of_time[metric_name]['y']
        #     df.to_excel(writer, sheet_name=metric_name)

        df = pd.read_csv(os.path.join(csv_file_path, 'config.csv'))
        df.to_excel(writer, sheet_name='Config')

        df = pd.read_csv(os.path.join(csv_file_path, 'dispatcher.csv'))
        # all_fls_num = sum(df['num_dispatched'][:-2])

        all_fls_num = sum(df['num_dispatched'])
        df.to_excel(writer, sheet_name='Dispatcher')

        writer.close()

        check_correctness(os.path.join(target_file_path, name + '_final_report.xlsx'), all_fls_num)
    except Exception as e:
        print(e)


def get_dispatcher_coords(center=None):
    l = 60
    w = 60
    dispatcher_coords = [0, 0, 0]

    if Config.SANITY_TEST == 1:
        height = min([2, math.sqrt(Config.SANITY_TEST_CONFIG[1][1])])
        radius = math.sqrt(Config.SANITY_TEST_CONFIG[1][1] ** 2 - height ** 2)
        center = [radius + 1, radius + 1, 0]

    elif Config.SANITY_TEST >= 2:
        radius = Config.STANDBY_TEST_CONFIG[0][1]
        center = [radius + 1, radius + 1, 0]

    if Config.DISPATCHERS == 1:
        if Config.SANITY_TEST > 0:
            dispatcher_coords = [center]
        else:
            dispatcher_coords = [[l / 2, w / 2, 0]]
            dispatcher_coords = [[0, 0, 0]]

    elif Config.DISPATCHERS == 3:
        if Config.SHAPE == "skateboard":
            dispatcher_coords = [[8.5, 22, 0], [19, 50.6, 0], [29, 76, 0]]
        else:
            dispatcher_coords = [[l / 2, w / 2, 0], [l, w, 0], [0, 0, 0]]
    elif Config.DISPATCHERS == 4:
        if Config.SHAPE == "skateboard":
            dispatcher_coords = [[8.5, 22, 0], [8.5, 76, 0], [29, 22, 0], [29, 76, 0]]
        else:
            dispatcher_coords = [[l / 4, w / 4, 0], [l * 3 / 4, w / 4, 0], [l / 4, w * 3 / 4, 0], [l * 3 / 4, w * 3 / 4, 0]]

    elif Config.DISPATCHERS == 5:
        dispatcher_coords = [[l / 2, w / 2, 0], [l, 0, 0], [0, w, 0], [l, w, 0], [0, 0, 0]]

    return dispatcher_coords


def distance_between(coord1, coord2):
    return ((coord2[0] - coord1[0]) ** 2 + (coord2[1] - coord1[1]) ** 2 + (coord2[2] - coord1[2]) ** 2) ** 0.5


def check_dispatcher(dispatcher_coords, coord):
    # Calculate distances from coord to each coordinate in dispatcher_coords
    distances = [distance_between(c, coord) for c in dispatcher_coords]

    # Find the index of the smallest distance
    min_index = distances.index(min(distances))

    # Return the coordinate from dispatcher_coords that corresponds to the smallest distance
    return dispatcher_coords[min_index]


def check_correctness(file_path, all_fls_num):
    logger.info(f"CHECKING REPORT: {file_path}")
    # Read the Excel file into a DataFrame
    df = pd.read_excel(file_path, engine='openpyxl')

    mid_flight = get_value_in_row(df, "Mid-Flight")
    illuminating = get_value_in_row(df, "Illuminating")
    stationary_standby = get_value_in_row(df, "Stationary Standby")
    dispatched_before_reset = get_value_in_row(df, "Dispatched Before Reset")
    dispatched_after_reset = get_value_in_row(df, "Dispatched After Reset")
    failure_before_reset = get_value_in_row(df, "Failure Before Reset")
    failure_after_reset = get_value_in_row(df, "Failure After Reset")
    group_num = get_value_in_row(df, "Number of Groups")
    in_que_fls = get_value_in_row(df, "Num_FLSs_Queued")
    # in_que_fls = get_value_in_row(df, "Queued FLSs")
    failed_illum = get_value_in_row(df, "Failed Illuminating FLS")
    failed_standby = get_value_in_row(df, "Failed Standby FLS")
    hub_deployed = get_value_in_row(df, "Hub_Deployed_FLS")
    hub_deployed_illum = get_value_in_row(df, "Hub_Deployed_FLS_To_Illuminate")
    hub_deployed_standby = get_value_in_row(df, "Hub_Deployed_FLS_For_Standby")
    Max_dist_arrived_illuminate = get_value_in_row(df, "Max_dist_arrived_illuminate")
    Max_dist_standby_hub_to_centroid = get_value_in_row(df, "Max_dist_standby_hub_to_centroid")
    Max_dist_stationary_standby_recover_illuminate = get_value_in_row(df,
                                                                      "Max_dist_stationary_standby_recover_illuminate")
    Min_dist_failed_midflight_illuminate = get_value_in_row(df, "Min_dist_failed_midflight_illuminate")
    Max_dist_failed_midflight_illuminate = get_value_in_row(df, "Max_dist_failed_midflight_illuminate")
    Max_dist_midflight_standby_recover_illuminate = get_value_in_row(df,
                                                                     "Max_dist_midflight_standby_recover_illuminate")
    Min_dist_standby_hub_to_centroid = get_value_in_row(df, "Min_dist_standby_hub_to_centroid")
    Min_dist_midflight_standby_recover_illuminate = get_value_in_row(df,
                                                                     "Min_dist_midflight_standby_recover_illuminate")
    Min_dist_standby_hub_to_fail_before_centroid = get_value_in_row(df, "Min_dist_standby_hub_to_fail_before_centroid")
    Max_dist_standby_hub_to_fail_before_centroid = get_value_in_row(df, "Max_dist_standby_hub_to_fail_before_centroid")
    Min_dist_standby_centroid_to_fail_before_recovered = get_value_in_row(df,
                                                                          "Min_dist_standby_centroid_to_fail_before_recovered")
    Max_dist_standby_centroid_to_fail_before_recovered = get_value_in_row(df,
                                                                          "Max_dist_standby_centroid_to_fail_before_recovered")

    if_error = False

    total_dispatched = dispatched_before_reset + dispatched_after_reset

    if abs((mid_flight + illuminating + stationary_standby) - (
            total_dispatched - (failure_before_reset + failure_after_reset))) > 0.1:
        logger.info(
            "Equation not satisfied: Mid Flight + Illuminating + Stationary Standby = Total Dispatched - Total Failed")
        if_error = True

    if abs(in_que_fls - (all_fls_num - total_dispatched)) > 0.00001:
        logger.info(
            f"Equation not satisfied: Num_FLSs_Queued: {in_que_fls} = SUM(FLSs put into dispatching Queue by all dispatcher): {all_fls_num} - Total Dispatched: {total_dispatched}")
        if_error = True

    if abs(failure_after_reset - (failed_illum + failed_standby)) > 0.00001:
        logger.info("Equation not satisfied: Failed After Reset = Failed Illuminating FLS + Failed Standby FLS")
        if_error = True

    if abs(hub_deployed - (hub_deployed_illum + hub_deployed_standby)) > 0.00001:
        logger.info(
            f"Equation not satisfied: Hub_Deployed_FLS: {hub_deployed} = Hub_Deployed_FLS_To_Illuminate: {hub_deployed_illum} + Hub_Deployed_FLS_for_Standby: {hub_deployed_standby}")
        if_error = True

    if abs(hub_deployed - (all_fls_num - (mid_flight + illuminating + stationary_standby) - in_que_fls)) > 0.00001:
        logger.info(
            f"Equation not satisfied: Hub_Deployed_FLS: {hub_deployed} = SUM(FLSs put into dispatching Queue by all dispatcher): {all_fls_num} - "
            f"(Mid Flight + Illuminating + Stationary Standby): {mid_flight + illuminating + stationary_standby} - Num_FLSs_Queued: {in_que_fls}")
        if_error = True

    if (Max_dist_stationary_standby_recover_illuminate + 0.0001 > 0 and Max_dist_standby_hub_to_centroid + 0.0001 > 0
            and (not (Max_dist_arrived_illuminate <= (
                    Max_dist_stationary_standby_recover_illuminate + Max_dist_standby_hub_to_centroid)))):
        logger.info(
            "CONSTRAINT VIOLATED: Max_dist_arrived_illuminate <= Max_dist_stationary_standby_recover_illuminate + Max_dist_standby_hub_to_centroid")
        if_error = True

    if not (Min_dist_failed_midflight_illuminate + 0.0001 >= 0):
        logger.info("CONSTRAINT VIOLATED: Min_dist_failed_midflight_illuminate >= 0")
        if_error = True

    if Config.SANITY_TEST != 3 and not (Max_dist_failed_midflight_illuminate <= Max_dist_arrived_illuminate + 0.0001):
        logger.info("CONSTRAINT VIOLATED: Max_dist_failed_midflight_illuminate <= Max_dist_arrived_illuminate")
        if_error = True

    if not (Min_dist_midflight_standby_recover_illuminate + 0.0001 >= 0):
        logger.info("CONSTRAINT VIOLATED: Min_dist_midflight_standby_recover_illuminate >= 0")
        if_error = True

    if not (Max_dist_midflight_standby_recover_illuminate <= (
            Max_dist_stationary_standby_recover_illuminate + Max_dist_standby_hub_to_centroid + 0.0001)):
        logger.info(
            "CONSTRAINT VIOLATED: Max_dist_midflight_standby_recover_illuminate <= Max_dist_stationary_standby_recover_illuminate + Max_dist_standby_hub_to_centroid")
        if_error = True

    if not (Min_dist_standby_hub_to_centroid + 0.0001 >= 0):
        logger.info("CONSTRAINT VIOLATED: Min_dist_standby_hub_to_centroid >= 0")
        if_error = True

    if not (Min_dist_standby_hub_to_fail_before_centroid + 0.0001 >= 0):
        logger.info("CONSTRAINT VIOLATED: Min_dist_standby_hub_to_fail_before_centroid >= 0")
        if_error = True

    if not (Max_dist_standby_hub_to_fail_before_centroid <= Max_dist_standby_hub_to_centroid + 0.0001):
        logger.info(
            "CONSTRAINT VIOLATED: Max_dist_standby_hub_to_fail_before_centroid <= Max_dist_standby_hub_to_centroid")
        if_error = True

    if not (Max_dist_standby_centroid_to_fail_before_recovered <= Max_dist_stationary_standby_recover_illuminate + 0.0001):
        logger.info(
            "CONSTRAINT VIOLATED: Max_dist_standby_centroid_to_fail_before_recovered <= Max_dist_stationary_standby_recover_illuminate")
        if_error = True

    if not (Min_dist_standby_centroid_to_fail_before_recovered + 0.0001 >= 0):
        logger.info(
            "CONSTRAINT VIOLATED: Min_dist_standby_centroid_to_fail_before_recovered >= 0")
        if_error = True

    if not if_error:
        logger.info(f"FINAL REPORT CORRECT")
    else:
        logger.info(f"FINAL REPORT WRONG")


def get_value_in_row(df, row_title):
    # Filter rows where 'Metrics' column has the value 'Queued FLSs'
    filtered_row = df[df['Unnamed: 1'] == row_title]

    # Get the value from the 'Value' column for the filtered row
    return filtered_row['Value'].iloc[0]


if __name__ == "__main__":

    name = "skateboard_D1_R3000_T60_S30_PTrue"

    for G in [0, 3, 20]:
        folder_path = f"DIRECTORY/G{G}/{name}"
        input_file = f"flss.csv"

        print(f"=================G{G}=================")

        df = pd.read_csv(os.path.join(folder_path, input_file))

        arrived_illum = df[df['timeline'].str.contains(' 1, ')]
        arrived_illum = arrived_illum['26_dist_traveled']
        print(f"Avg Dist Arrived Illum: {sum(arrived_illum)/ len(arrived_illum)}, num:{len(arrived_illum)}")

        midflight_failed_illum = df[df['timeline'].str.contains(' 3, ')]
        midflight_failed_illum = midflight_failed_illum[~midflight_failed_illum['timeline'].str.contains(' 1, ')]
        midflight_failed_illum = midflight_failed_illum[~midflight_failed_illum['timeline'].str.contains(' 4, ')]
        midflight_failed_illum = midflight_failed_illum['26_dist_traveled']
        print(f"Avg Dist Midflight Failed Illum: {sum(midflight_failed_illum)/ len(midflight_failed_illum) if len(midflight_failed_illum)>0 else 0}, num:{len(midflight_failed_illum)}")

        midflight = df[~df['timeline'].str.contains(' 3, ')]
        midflight = midflight[~midflight['timeline'].str.contains(' 1, ')]
        midflight = midflight[~midflight['timeline'].str.contains(' 5, ')]
        midflight = midflight[~midflight['timeline'].str.contains(' 6, ')]
        midflight = midflight[~midflight['timeline'].str.contains(' 2, ')]

        midflight_standby_recover = df[df['timeline'].str.contains(' 2, ')]
        midflight_standby_recover = midflight_standby_recover[midflight_standby_recover['timeline'].str.contains(' 4, ')]
        midflight_standby_recover = midflight_standby_recover[~midflight_standby_recover['timeline'].str.contains(' 5, ')]
        midflight_standby_recover = midflight_standby_recover[~midflight_standby_recover['timeline'].str.contains(' 6, ')]

        midflight = pd.concat([midflight, midflight_standby_recover])
        midflight = midflight['26_dist_traveled']
        print(f"Avg Dist Midflight FLS: {sum(midflight) / len(midflight) if len(midflight) > 0 else 0}, num:{len(midflight)}")

        midflight_standby_recovered = df[df['timeline'].str.contains(' 6, ')]
        midflight_standby_recovered = midflight_standby_recovered[~midflight_standby_recovered['timeline'].str.contains(' 2, ')]
        midflight_standby_recovered = midflight_standby_recovered['26_dist_traveled']
        print(
            f"Avg Dist Midflight Standby Recover Illum: {sum(midflight_standby_recovered) / len(midflight_standby_recovered) if len(midflight_standby_recovered) > 0 else 0}, num:{len(midflight_standby_recovered)}")

        stationary_standby_recovered = df[df['timeline'].str.contains(' 6, ')]
        stationary_standby_recovered = stationary_standby_recovered[stationary_standby_recovered['timeline'].str.contains(' 2, ')]
        stationary_standby_recovered = stationary_standby_recovered['26_dist_traveled']
        print(f"Avg Dist Stationary Standby Recover Illum: {sum(stationary_standby_recovered) / len(stationary_standby_recovered) if len(stationary_standby_recovered) > 0 else 0}, num:{len(stationary_standby_recovered)}")

        standby_failed = df[df['timeline'].str.contains(' 5, ')]
        standby_failed = standby_failed[~standby_failed['timeline'].str.contains(' 6, ')]
        standby_failed = standby_failed['26_dist_traveled']
        print(f"Avg Dist Standby Midflight Failed: {sum(standby_failed) / len(standby_failed) if len(standby_failed)>0 else 0}, num:{len(standby_failed)}")

        standby_stationary = df[df['timeline'].str.contains(' 2, ')]
        standby_stationary = standby_stationary[~standby_stationary['timeline'].str.contains(' 4, ')]
        standby_stationary = standby_stationary[~standby_stationary['timeline'].str.contains(' 5, ')]
        standby_stationary = standby_stationary['26_dist_traveled']
        print(f"Avg Dist Standby Stationary: {sum(standby_stationary) / len(standby_stationary) if len(standby_stationary)>0 else 0}, num:{len(standby_stationary)}")


        dists = df['26_dist_traveled']
        print(f"Total Avg Dist:{sum(dists)/len(dists)}, num: {len(dists)}")
        print(f"Diff Type num sum: {len(arrived_illum) + len(midflight_failed_illum) + len(midflight) + len(midflight_standby_recovered) +len(stationary_standby_recovered) + len(standby_failed) + len(standby_stationary)}")
