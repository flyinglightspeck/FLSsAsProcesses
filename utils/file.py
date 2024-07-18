import math
import os
import json
import csv
import sys

import numpy as np

from config import Config
from test_config import TestConfig
import pandas as pd
import glob
import re
import utils
from utils import logger

from worker.metrics import merge_timelines, gen_charts_trimed, gen_point_metrics, trim_timeline, point_to_id, \
    gen_point_metrics_no_group, gen_charts


def write_json(fid, results, directory, is_clique):
    file_name = f"{fid:05}.c.json" if is_clique else f"{fid:05}.json"
    with open(os.path.join(directory, 'json', file_name), "w") as f:
        json.dump(results, f)


def write_csv(directory, rows, file_name):
    logger.debug(f"WRITE_CSV_FILE {file_name}")
    with open(os.path.join(directory, f'{file_name}.csv'), 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(rows)


def create_csv_from_json(config, init_num, directory, fig_dir, group_map):
    if not os.path.exists(directory):
        return

    headers_set = set()
    rows = []
    node_rows = []

    json_dir = os.path.join(directory, 'json')
    filenames = os.listdir(json_dir)
    filenames.sort()

    for filename in filenames:
        if filename.endswith('.json'):
            with open(os.path.join(json_dir, filename)) as f:
                try:
                    data = json.load(f)
                    headers_set = headers_set.union(set(list(data.keys())))
                except json.decoder.JSONDecodeError:
                    print(filename)

    headers = list(headers_set)
    headers.sort()
    rows.append(['fid'] + headers)
    node_rows.append(['fid'] + headers)

    weights = []
    min_dists = []
    avg_dists = []
    max_dists = []
    timelines = []
    for filename in filenames:
        if filename.endswith('.json'):
            with open(os.path.join(json_dir, filename)) as f:
                try:
                    data = json.load(f)
                    fid = filename.split('.')[0]
                    row = [fid] + [data[h] if h in data else 0 for h in headers]
                    node_rows.append(row)
                    timelines.append(data['timeline'])
                except json.decoder.JSONDecodeError:
                    print(filename)

    # with open(os.path.join(directory, 'cliques.csv'), 'w', newline='') as csvfile:
    #     writer = csv.writer(csvfile)
    #     writer.writerows(rows)

    with open(os.path.join(directory, 'flss.csv'), 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(node_rows)

    merged_timeline = merge_timelines(timelines)

    num_metrics = [0, 0, 0, 0]
    start_time = 0

    trimed_timeline = merged_timeline
    if config.RESET_AFTER_INITIAL_DEPLOY:
        trimed_timeline, num_metrics, start_time = trim_timeline(merged_timeline, init_num)

    with open(os.path.join(directory, 'bucket_face_G0_R90_T60_S6_PTrue.json'), "w") as f:
        json.dump(trimed_timeline, f)

    chart_data = gen_charts_trimed(trimed_timeline, start_time, num_metrics, fig_dir)
    with open(os.path.join(directory, 'charts.json'), "w") as f:
        json.dump(chart_data, f)

    point_metrics, standby_metrics = gen_point_metrics(merged_timeline, start_time, group_map)
    write_csv(directory, point_metrics, 'illuminating')
    write_csv(directory, standby_metrics, 'standby')


def write_hds_time(hds, directory, nid):
    if not os.path.exists(directory):
        return

    headers = ['timestamp(s)', 'relative_time(s)', 'hd']
    rows = [headers]

    for i in range(len(hds)):
        row = [hds[i][0], hds[i][0] - hds[0][0], hds[i][1]]
        rows.append(row)

    with open(os.path.join(directory, f'hd-n{nid}.csv'), 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(rows)


def write_hds_round(hds, rounds, directory, nid):
    if not os.path.exists(directory):
        return

    headers = ['round', 'time(s)', 'hd']
    rows = [headers]

    for i in range(len(hds)):
        row = [i + 1, rounds[i + 1] - rounds[0], hds[i][1]]
        rows.append(row)

    with open(os.path.join(directory, f'hd-n{nid}.csv'), 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(rows)


def write_swarms(swarms, rounds, directory, nid):
    headers = [
        'timestamp(s)',
        'relative times(s)',
        'num_swarms',
        'average_swarm_size',
        'largest_swarm',
        'smallest_swarm',
    ]

    rows = [headers]

    for i in range(len(swarms)):
        t = swarms[i][0] - rounds[0]
        num_swarms = len(swarms[i][1])
        sizes = swarms[i][1].values()

        row = [swarms[i][0], t, num_swarms, sum(sizes) / num_swarms, max(sizes), min(sizes)]
        rows.append(row)

    with open(os.path.join(directory, f'swarms-n{nid}.csv'), 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(rows)


def write_configs(directory, date_time):
    headers = ['config', 'value']
    rows = [headers]

    kargs = vars(Config).items()
    if TestConfig.ENABLED:
        kargs = vars(TestConfig).items()

    for k, v in kargs:
        if not k.startswith('__'):
            rows.append([k, v])
    rows.append(["datetime", date_time])

    with open(os.path.join(directory, 'config.csv'), 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(rows)


def combine_csvs(directory, xlsx_dir, file_name):
    csv_files = glob.glob(f"{directory}/*.csv")

    with pd.ExcelWriter(os.path.join(xlsx_dir, f'{file_name}.xlsx'), mode='w') as writer:
        for csv_file in csv_files:
            df = pd.read_csv(csv_file)
            sheet_name = csv_file.split('/')[-1][:-4]
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    # shutil.rmtree(os.path.join(directory))


def combine_xlsx(directory):
    xlsx_files = glob.glob(f"{directory}/*.xlsx")

    with pd.ExcelWriter(os.path.join(directory, 'summary.xlsx')) as writer:
        dfs = []
        for file in sorted(xlsx_files):
            print(file)
            df = pd.read_excel(file, sheet_name='metrics')
            m = re.search(r'G:(\d+)_Q:(\d+)', file)
            g = m.group(1)
            q = m.group(2)

            df2 = pd.DataFrame([g, q])
            df3 = pd.concat([df2, df.value])
            dfs.append(df3)
        pd.concat([pd.concat([pd.DataFrame(['g', 'q']), df.metric])] + dfs, axis=1).to_excel(writer, index=False)


def read_cliques_xlsx(path):
    df = pd.read_excel(path, sheet_name='cliques')
    group_list = []

    for c in df["7 coordinates"]:
        coord_list = np.array(eval(c))
        # coord_list[:, 2] += 100
        group_list.append(coord_list)

    return group_list, [max(eval(d)) + 1 if eval(d) != [] else 1 for d in df["6 dist between each pair"]]


def read_point_info_from_cliques_xlsx(path):
    df = pd.read_excel(path, sheet_name='metrics')
    filtered_row = df[df['metric'] == 'number of cliques']
    group_num = filtered_row['value'].iloc[0]
    group_num = int(group_num)
    filtered_row = df[df['metric'] == 'number of single nodes']
    if Config.G == 0:
        total_point_num = group_num * 3 + int(filtered_row['value'].iloc[0])

        # logger.info(f"total illum num: {total_point_num}")
        group_num = 0
    else:
        total_point_num = group_num * Config.G + int(filtered_row['value'].iloc[0])

    # Get the value from the 'Value' column for the filtered row
    # logger.info(f"INITIAL ILLUM NUM {total_point_num} TYPE={type(total_point_num)}")
    return total_point_num, group_num


def get_group_mapping(path):
    group_id = []

    df = pd.read_excel(path, sheet_name='cliques')
    group_map = dict()
    for i, row in enumerate(df["7 coordinates"]):
        for coord in eval(row):
            pid = point_to_id(coord)
            group_map[pid] = i
            if i not in group_id:
                group_id.append(i)

    return group_map, group_id


def get_time_range(json_file_path, intial_num, set_end_time=None):
    time_range = []

    with open(json_file_path, 'r') as json_file:
        data = json.load(json_file)

    metric_name = 'dispatched'

    for i in range(len(data[metric_name]['t'])):
        if data[metric_name]['y'][i] >= intial_num:
            time_range.append(data[metric_name]['t'][i])
            break
    if len(time_range) <= 0:
        time_range.append(intial_num / Config.DISPATCH_RATE)

    if set_end_time is not None:
        time_range.append(set_end_time)
    else:
        time_range.append(Config.DURATION + 1)
    return time_range


def create_csv_from_json_no_group(config, init_num, directory, initial_fls_num, fig_dir):
    if not os.path.exists(directory):
        return

    headers_set = set()
    rows = []
    node_rows = []

    json_dir = os.path.join(directory, 'json')
    filenames = os.listdir(json_dir)
    filenames.sort()

    for filename in filenames:
        if filename.endswith('.json'):
            with open(os.path.join(json_dir, filename)) as f:
                try:
                    data = json.load(f)
                    headers_set = headers_set.union(set(list(data.keys())))
                except json.decoder.JSONDecodeError:
                    print(filename)

    headers = list(headers_set)
    headers.sort()
    rows.append(['fid'] + headers)
    node_rows.append(['fid'] + headers)

    weights = []
    min_dists = []
    avg_dists = []
    max_dists = []
    timelines = []
    for filename in filenames:
        if filename.endswith('.json'):
            with open(os.path.join(json_dir, filename)) as f:
                try:
                    data = json.load(f)
                    fid = filename.split('.')[0]
                    row = [fid] + [data[h] if h in data else 0 for h in headers]
                    node_rows.append(row)
                    timelines.append(data['timeline'])
                except json.decoder.JSONDecodeError:
                    print(filename)

    with open(os.path.join(directory, 'flss.csv'), 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(node_rows)

    merged_timeline = merge_timelines(timelines)

    # trimed_timeline = merged_timeline

    # if config.RESET_AFTER_INITIAL_DEPLOY:
    #     # num_metrics: [illuminating_failed, standby_failed, illuminating, standby, mid_flight]
    #     trimed_timeline, num_metrics, start_time = trim_timeline(merged_timeline, init_num)

    with open(os.path.join(directory, 'bucket_face_G0_R90_T60_S6_PTrue.json'), "w") as f:
        json.dump(merged_timeline, f)

    chart_data = gen_charts(merged_timeline, fig_dir)
    with open(os.path.join(directory, 'charts.json'), "w") as f:
        json.dump(chart_data, f)

    if initial_fls_num > 0:
        time_range = get_time_range(os.path.join(directory, 'charts.json'), initial_fls_num)
    else:
        time_range = [0, Config.DURATION + 1]

    point_metrics, standby_metrics = gen_point_metrics_no_group(merged_timeline, time_range[0])
    write_csv(directory, point_metrics, 'illuminating')
    write_csv(directory, standby_metrics, 'standby')

    return time_range


if __name__ == "__main__":
    if len(sys.argv) == 4:
        dir_in = sys.argv[1]
        dir_out = sys.argv[2]
        name = sys.argv[3]
    else:
        dir_in, dir_out, name = "../results/butterfly/H:2/1687746648", "../results/butterfly/H:2", "agg"
    create_csv_from_json(dir_in, 0)
