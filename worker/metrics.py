import json
import math
import heapq
import time

import numpy as np
from config import Config
import matplotlib.pyplot as plt
import matplotlib as mpl
import matplotlib.animation as animation


class MetricTypes:
    RECEIVED_MASSAGES = 0
    SENT_MESSAGES = 1
    DROPPED_MESSAGES = 2
    FAILURES = 3


class TimelineEvents:
    DISPATCH = 0  # standby or illuminating is dispatched
    ILLUMINATE = 1  # an illuminating FLS started to illuminate
    ILLUMINATE_STANDBY = 6  # a standby FLS started to illuminate
    STANDBY = 2  # a standby is arrived
    FAIL = 3  # an illumination FLS is failed
    REPLACE = 4  # a standby started to replace a failed FLS
    STANDBY_FAIL = 5  # a standby is failed


def update_dict_sum(obj, key):
    if key in obj:
        obj[key] += 1
    else:
        obj[key] = 1


def log_msg_hist(hist, msg_type, label, cat):
    key_number = f'{cat}0_num_{label}_{msg_type.name}'
    # key_num_cat = f'{cat}1_cat_num_{label}_{msg_type.get_cat()}'

    update_dict_sum(hist, key_number)
    # update_dict_sum(hist, key_num_cat)


def merge_timelines(timelines):
    lists = timelines
    heap = []
    for i, lst in enumerate(lists):
        if lst:
            heap.append((lst[0][0], i, 0))
    heapq.heapify(heap)

    merged = []
    while heap:
        val, lst_idx, elem_idx = heapq.heappop(heap)
        merged.append(lists[lst_idx][elem_idx] + [lst_idx])
        if elem_idx + 1 < len(lists[lst_idx]):
            next_elem = lists[lst_idx][elem_idx + 1][0]
            heapq.heappush(heap, (next_elem, lst_idx, elem_idx + 1))
    return merged


def trim_timeline(timeline, init_num):
    deployed = 0
    illuminating_failed = 0
    standby_failed = 0
    illuminating = 0
    standby = 0
    mid_flight = 0
    start_time = 0
    dispatch_event = []

    for i, event in enumerate(timeline):
        if event[1] == 0:
            dispatch_event.append(event)
            deployed += 1
            mid_flight += 1
        elif event[1] == 3:
            illuminating_failed += 1
            mid_flight -= 1
        elif event[1] == 5:
            standby_failed += 1
            mid_flight -= 1
        elif event[1] == 1 or event[1] == 6:
            illuminating += 1
            mid_flight -= 1
        elif event[1] == 2:
            standby += 1
            mid_flight -= 1

        if deployed >= init_num:
            timeline = timeline[i + 1:]
            start_time = event[0]
            break
    return timeline, [illuminating_failed, standby_failed, illuminating, standby, mid_flight], start_time


def _avg(values):
    if len(values):
        return sum(values) / len(values)
    return 0


def _min(values):
    if len(values):
        return min(values)
    return 0


def _max(values):
    if len(values):
        return max(values)
    return 0


def point_to_id(point):
    return '_'.join([str(p) for p in point])


def gen_point_metrics(events, start_time, group_map):
    fid_to_point = dict()
    illuminating_events = dict()
    standby_events = dict()

    metric_keys = [
        "point",
        "group_id",
        "failed",
        "recovered by hub",
        "recovered by standby",
        "hub wait times",
        "standby wait times",
        "hub min wait time",
        "hub avg wait time",
        "hub max wait time",
        "standby min wait time",
        "standby avg wait time",
        "standby max wait time",
    ]

    standby_metric_keys = [
        "point",
        "failed",
        "replace",
        "recovered by hub",
        "hub wait times",
        "hub min wait time",
        "hub avg wait time",
        "hub max wait time",
    ]

    illuminating_metrics = dict()
    standby_metrics = dict()
    pid_list = []

    for event in events:
        t = event[0]
        e = event[1]
        fid = event[-1]

        if e == TimelineEvents.DISPATCH:
            pid = point_to_id(event[2])
            fid_to_point[fid] = pid

            if pid not in pid_list:
                pid_list.append(pid)
                try:
                    illuminating_metrics[0, 3] = [pid, group_map[pid], 0, 0, 0, [], [], []]
                except Exception as e:
                    illuminating_metrics[0, 3] = [pid, 0, 0, 0, 0, [], [], []]

        elif e == TimelineEvents.FAIL and event[2] is False:
        # elif e == TimelineEvents.FAIL:
            pid = fid_to_point[fid]
            try:
                illuminating_events[pid].append([t, e])
            except Exception as e:
                if pid in standby_events:
                    if t > start_time:
                        standby_events[pid].append([t, e])
                else:
                    standby_events[pid] = [[t, e]]
                    standby_metrics[pid] = [pid, 0, 0, 0, [], []]
                standby_metrics[pid][2] += 1
                print(e)
                continue

            if t > start_time:
                illuminating_metrics[pid][2] += 1

        elif e == TimelineEvents.STANDBY_FAIL:
            # Check if the stand by FLS is in mid-flight
            pid = fid_to_point[fid]
            if pid in standby_events:
                standby_events[pid].append([t, e])
            else:
                standby_events[pid] = [[t, e]]
                standby_metrics[pid] = [pid, 0, 0, 0, [], []]

            standby_metrics[pid][1] += 1

        elif e == TimelineEvents.ILLUMINATE:
            pid = point_to_id(event[2])
            fid_to_point[fid] = pid
            if pid in illuminating_events:
                illuminating_events[pid].append([t, e])
                if t > start_time:
                    illuminating_metrics[pid][3] += 1
                    illuminating_metrics[pid][5].append(t - illuminating_events[pid][-2][0])
            else:
                illuminating_events[pid] = [[t, e]]
                try:
                    illuminating_metrics[0, 3] = [pid, group_map[pid], 0, 0, 0, [], [], []]
                except:
                    illuminating_metrics[0, 3] = [pid, 0, 0, 0, 0, [], [], []]

        elif e == TimelineEvents.ILLUMINATE_STANDBY:
            pid = point_to_id(event[2])
            fid_to_point[fid] = pid

            if pid in illuminating_events:
                illuminating_events[pid].append([t, e])

                if t > start_time:
                    illuminating_metrics[pid][4] += 1
                    illuminating_metrics[pid][6].append(t - illuminating_events[pid][-2][0])
            else:
                # Situations when the previous FLS who was assigned with this point never arrived
                illuminating_events[pid] = [[t, e]]
                try:
                    illuminating_metrics[0, 3] = [pid, group_map[pid], 0, 0, 0, [], [], []]
                except:
                    illuminating_metrics[0, 3] = [pid, 0, 0, 0, 0, [], [], []]

        elif e == TimelineEvents.STANDBY:
            pid = point_to_id(event[2])
            fid_to_point[fid] = pid
            if pid in standby_events:
                standby_events[pid].append([t, e])
                if t > start_time:
                    standby_metrics[pid][3] += 1
                    standby_metrics[pid][4].append(t - standby_events[pid][-2][0])
            else:
                standby_events[pid] = [[t, e]]
                standby_metrics[pid] = [pid, 0, 0, 0, [], []]

        elif e == TimelineEvents.REPLACE:
            pid = fid_to_point[fid]
            if pid in standby_events:
                if t > start_time:
                    standby_events[pid].append([t, e])
            else:
                standby_events[pid] = [[t, e]]
                standby_metrics[pid] = [pid, 0, 0, 0, []]

            standby_metrics[pid][2] += 1

    i_rows = list(illuminating_metrics.values())
    s_rows = list(standby_metrics.values())
    for row in i_rows:
        hub_w_t = row[5]
        standby_w_t = row[6]
        row.append(_min(hub_w_t))
        row.append(_avg(hub_w_t))
        row.append(_max(hub_w_t))
        row.append(_min(standby_w_t))
        row.append(_avg(standby_w_t))
        row.append(_max(standby_w_t))

    for row in s_rows:
        hub_w_t = row[4]
        row.append(_min(hub_w_t))
        row.append(_avg(hub_w_t))
        row.append(_max(hub_w_t))

    return [metric_keys] + i_rows, \
           [standby_metric_keys] + s_rows


def gen_point_metrics_no_group(events, start_time):
    fid_to_point = dict()
    illuminating_events = dict()
    standby_events = dict()

    metric_keys = [
        "point",
        "group_id",
        "failed",
        "recovered by hub",
        "recovered by standby",
        "hub wait times",
        "standby wait times",
        "hub min wait time",
        "hub avg wait time",
        "hub max wait time",
        "standby min wait time",
        "standby avg wait time",
        "standby max wait time",
    ]

    standby_metric_keys = [
        "point",
        "failed",
        "replace",
        "recovered by hub",
        "hub wait times",
        "hub min wait time",
        "hub avg wait time",
        "hub max wait time",
    ]

    illuminating_metrics = dict()
    standby_metrics = dict()
    pid_list = []

    for event in events:
        t = event[0]
        e = event[1]
        fid = event[-1]

        if e == TimelineEvents.DISPATCH:
            pid = point_to_id(event[2])
            fid_to_point[fid] = pid

            if pid not in pid_list:
                pid_list.append(pid)
                illuminating_events[pid] = [[t, e]]
                illuminating_metrics[pid] = [pid, 0, 0, 0, 0, [], []]

        # elif e == TimelineEvents.FAIL and event[2] is False:
        elif e == TimelineEvents.FAIL:
            pid = fid_to_point[fid]
            try:
                illuminating_events[pid].append([t, e])
            except Exception as e:
                if pid in standby_events:
                    if t > start_time:
                        standby_events[pid].append([t, e])
                else:
                    standby_events[pid] = [[t, e]]
                    standby_metrics[pid] = [pid, 0, 0, 0, []]
                standby_metrics[pid][2] += 1
                print(e)
                continue

            if t > start_time:
                illuminating_metrics[pid][2] += 1

        elif e == TimelineEvents.STANDBY_FAIL:
            # Check if the stand by FLS is in mid-flight
            pid = fid_to_point[fid]
            if pid in standby_events:
                standby_events[pid].append([t, e])
            else:
                standby_events[pid] = [[t, e]]
                standby_metrics[pid] = [pid, 0, 0, 0, []]

            standby_metrics[pid][1] += 1

        elif e == TimelineEvents.ILLUMINATE:
            pid = point_to_id(event[2])
            fid_to_point[fid] = pid
            if pid in illuminating_events:
                illuminating_events[pid].append([t, e])
                if t > start_time:
                    illuminating_metrics[pid][3] += 1
                    illuminating_metrics[pid][5].append(t - illuminating_events[pid][-2][0])
            else:
                illuminating_events[pid] = [[t, e]]
                illuminating_metrics[pid] = [pid, 0, 0, 0, 0, [], []]

        elif e == TimelineEvents.ILLUMINATE_STANDBY:
            pid = point_to_id(event[2])
            fid_to_point[fid] = pid

            if pid in illuminating_events:
                illuminating_events[pid].append([t, e])

                if t > start_time:
                    illuminating_metrics[pid][4] += 1
                    illuminating_metrics[pid][6].append(t - illuminating_events[pid][-2][0])
            else:
                # Situations when the previous FLS who was assigned with this point never arrived
                illuminating_events[pid] = [[t, e]]
                illuminating_metrics[pid] = [pid, 0, 0, 0, 0, [], []]

        elif e == TimelineEvents.STANDBY:
            pid = point_to_id(event[2])
            fid_to_point[fid] = pid
            if pid in standby_events:
                standby_events[pid].append([t, e])
                if t > start_time:
                    standby_metrics[pid][3] += 1
                    standby_metrics[pid][4].append(t - standby_events[pid][-2][0])
            else:
                standby_events[pid] = [[t, e]]
                standby_metrics[pid] = [pid, 0, 0, 0, []]

        elif e == TimelineEvents.REPLACE:
            pid = fid_to_point[fid]
            if pid in standby_events:
                if t > start_time:
                    standby_events[pid].append([t, e])
            else:
                standby_events[pid] = [[t, e]]
                standby_metrics[pid] = [pid, 0, 0, 0, []]

            standby_metrics[pid][2] += 1

    i_rows = list(illuminating_metrics.values())
    i_rows = [row for row in i_rows if (row[2] != 0 or row[5] != [] or row[6] != [])]

    s_rows = list(standby_metrics.values())
    for row in i_rows:
        hub_w_t = row[5]
        standby_w_t = row[6]
        row.append(_min(hub_w_t))
        row.append(_avg(hub_w_t))
        row.append(_max(hub_w_t))
        row.append(_min(standby_w_t))
        row.append(_avg(standby_w_t))
        row.append(_max(standby_w_t))

    for row in s_rows:
        hub_w_t = row[4]
        row.append(_min(hub_w_t))
        row.append(_avg(hub_w_t))
        row.append(_max(hub_w_t))

    return [metric_keys] + i_rows, \
           [standby_metric_keys] + s_rows


def gen_charts_trimed(events, start_time, num_metrics, fig_dir):
    # num_metrics: [illuminating_failed, standby_failed, illuminating, standby, mid_flight]

    dispatched = {"t": [start_time], "y": [0]}
    standby = {"t": [start_time], "y": [num_metrics[3]]}
    illuminating = {"t": [start_time], "y": [num_metrics[2]]}
    failed = {"t": [start_time], "y": [num_metrics[0] + num_metrics[1]]}
    mid_flight = {"t": [start_time], "y": [num_metrics[4]]}

    for event in events:
        t = event[0]
        e = event[1]
        if e == TimelineEvents.DISPATCH:
            dispatched["t"].append(t)
            dispatched["y"].append(dispatched["y"][-1] + 1)
            mid_flight["t"].append(t)
            mid_flight["y"].append(mid_flight["y"][-1] + 1)
        elif e == TimelineEvents.ILLUMINATE or e == TimelineEvents.ILLUMINATE_STANDBY:
            illuminating["t"].append(t)
            illuminating["y"].append(illuminating["y"][-1] + 1)
            mid_flight["t"].append(t)
            mid_flight["y"].append(mid_flight["y"][-1] - 1)
        elif e == TimelineEvents.STANDBY:
            standby["t"].append(t)
            standby["y"].append(standby["y"][-1] + 1)
            mid_flight["t"].append(t)
            mid_flight["y"].append(mid_flight["y"][-1] - 1)
        elif e == TimelineEvents.FAIL:
            failed["t"].append(t)
            failed["y"].append(failed["y"][-1] + 1)
            if event[2]:  # is mid-flight
                mid_flight["t"].append(t)
                mid_flight["y"].append(mid_flight["y"][-1] - 1)
            else:
                illuminating["t"].append(t)
                illuminating["y"].append(illuminating["y"][-1] - 1)
        elif e == TimelineEvents.STANDBY_FAIL:
            failed["t"].append(t)
            failed["y"].append(failed["y"][-1] + 1)
            if event[2]:  # is mid-flight
                mid_flight["t"].append(t)
                mid_flight["y"].append(mid_flight["y"][-1] - 1)
            else:
                standby["t"].append(t)
                standby["y"].append(standby["y"][-1] - 1)
        elif e == TimelineEvents.REPLACE:
            if not event[2]:  # enter this situation when FLS has arrived (standby or illuminating)
                mid_flight["t"].append(t)
                mid_flight["y"].append(mid_flight["y"][-1] + 1)
                standby["t"].append(t)
                standby["y"].append(standby["y"][-1] - 1)

    dispatched["t"].append(events[-1][0])
    dispatched["y"].append(dispatched["y"][-1])
    standby["t"].append(events[-1][0])
    standby["y"].append(standby["y"][-1])
    illuminating["t"].append(events[-1][0])
    illuminating["y"].append(illuminating["y"][-1])
    failed["t"].append(events[-1][0])
    failed["y"].append(failed["y"][-1])
    mid_flight["t"].append(events[-1][0])
    mid_flight["y"].append(mid_flight["y"][-1])

    plt.step([t - 1 for t in dispatched["t"]], dispatched["y"], where='post', label="Dispatched FLSs")
    plt.step([t - 1 for t in standby["t"]], standby["y"], where='post', label="Standby FLSs")
    plt.step([t - 1 for t in illuminating["t"]], illuminating["y"], where='post', label="Illuminating FLSs")
    plt.step([t - 1 for t in failed["t"]], failed["y"], where='post', label="Failed FLSs")
    plt.step([t - 1 for t in mid_flight["t"]], mid_flight["y"], where='post', label="Mid-flight FLSs")
    plt.gca().xaxis.set_major_locator(mpl.ticker.MaxNLocator(integer=True))
    plt.gca().yaxis.set_major_locator(mpl.ticker.MaxNLocator(integer=True))
    # Add a legend
    plt.legend()
    if Config.DEBUG:
        plt.show()
    else:
        plt.savefig(fig_dir)

    return {
        "dispatched": dispatched,
        "standby": standby,
        "illuminating": illuminating,
        "failed": failed,
        "mid_flight": mid_flight,
    }


def gen_charts(events, fig_dir):
    dispatched = {"t": [0], "y": [0]}
    standby = {"t": [0], "y": [0]}
    illuminating = {"t": [0], "y": [0]}
    failed = {"t": [0], "y": [0]}
    mid_flight = {"t": [0], "y": [0]}

    for event in events:
        t = event[0]
        e = event[1]
        if e == TimelineEvents.DISPATCH:
            dispatched["t"].append(t)
            dispatched["y"].append(dispatched["y"][-1] + 1)
            mid_flight["t"].append(t)
            mid_flight["y"].append(mid_flight["y"][-1] + 1)
        elif e == TimelineEvents.ILLUMINATE or e == TimelineEvents.ILLUMINATE_STANDBY:
            illuminating["t"].append(t)
            illuminating["y"].append(illuminating["y"][-1] + 1)
            mid_flight["t"].append(t)
            mid_flight["y"].append(mid_flight["y"][-1] - 1)
        elif e == TimelineEvents.STANDBY:
            standby["t"].append(t)
            standby["y"].append(standby["y"][-1] + 1)
            mid_flight["t"].append(t)
            mid_flight["y"].append(mid_flight["y"][-1] - 1)
        elif e == TimelineEvents.FAIL:
            failed["t"].append(t)
            failed["y"].append(failed["y"][-1] + 1)
            if event[2]:  # is mid-flight
                mid_flight["t"].append(t)
                mid_flight["y"].append(mid_flight["y"][-1] - 1)
            else:
                illuminating["t"].append(t)
                illuminating["y"].append(illuminating["y"][-1] - 1)
        elif e == TimelineEvents.STANDBY_FAIL:
            failed["t"].append(t)
            failed["y"].append(failed["y"][-1] + 1)
            if event[2]:  # is mid-flight
                mid_flight["t"].append(t)
                mid_flight["y"].append(mid_flight["y"][-1] - 1)
            else:
                standby["t"].append(t)
                standby["y"].append(standby["y"][-1] - 1)
        elif e == TimelineEvents.REPLACE:
            if not event[2]:  # enter this situation when FLS has arrived (standby or illuminating)
                mid_flight["t"].append(t)
                mid_flight["y"].append(mid_flight["y"][-1] + 1)
                standby["t"].append(t)
                standby["y"].append(standby["y"][-1] - 1)

    dispatched["t"].append(events[-1][0])
    dispatched["y"].append(dispatched["y"][-1])
    standby["t"].append(events[-1][0])
    standby["y"].append(standby["y"][-1])
    illuminating["t"].append(events[-1][0])
    illuminating["y"].append(illuminating["y"][-1])
    failed["t"].append(events[-1][0])
    failed["y"].append(failed["y"][-1])
    mid_flight["t"].append(events[-1][0])
    mid_flight["y"].append(mid_flight["y"][-1])

    # print(dispatched["t"], dispatched["y"])
    plt.step(dispatched["t"], dispatched["y"], where='post', label="Dispatched FLSs")
    plt.step(standby["t"], standby["y"], where='post', label="Standby FLSs")
    plt.step(illuminating["t"], illuminating["y"], where='post', label="Illuminating FLSs")
    plt.step(failed["t"], failed["y"], where='post', label="Failed FLSs")
    plt.step(mid_flight["t"], mid_flight["y"], where='post', label="Mid-flight FLSs")

    # Add a legend
    plt.legend()
    if Config.DEBUG:
        plt.show()
    else:
        plt.savefig(fig_dir)

    return {
        "dispatched": dispatched,
        "standby": standby,
        "illuminating": illuminating,
        "failed": failed,
        "mid_flight": mid_flight,
    }


def log_sum(obj, key, value):
    obj[key] += value


def log_max(obj, key, value):
    obj[key] = max(obj[key], value)


def log_min(obj, key, value):
    obj[key] = min(obj[key], value)


class Metrics:
    def __init__(self, history, results_directory, start_time):
        self.results_directory = results_directory
        self.history = history
        self.start_time = start_time
        self.dispatched_time = 0
        self.timeline = []
        self.general_metrics = {
            "00_gtl": None,
            "01_is_standby": [],
            "02_group_id": 0,
            "03_radio_range": 0,
            "05_standby_id": [],  # (time, id)
            "10_dispatch_time": -1,
            "12_arrival_time": -1,
            "13_dispatch_duration": -1,
            "14_time_to_recover": -1,
            "30_time_to_fail": -1,
            "31_replacement_start_time": -1,
            "32_replacement_arrival_time": -1,
            "33_replacement_duration": -1,
            "34_failed_fls_id": -1,
            "20_total_distance_traveled": 0
            # "A4_num_dropped_messages": 0,
        }
        self.network_metrics = {
            "21_bytes_sent": 0,
            "22_bytes_received": 0,
            "23_num_messages_sent": 0,
            "24_num_messages_received": 0,
        }
        self.sent_msg_hist = {}
        self.received_msg_hist = {}

    def log_received_msg(self, msg_type, length):
        log_msg_hist(self.received_msg_hist, msg_type, 'received', 'C')
        log_sum(self.network_metrics, "24_num_messages_received", 1)
        log_sum(self.network_metrics, "22_bytes_received", length)

    def log_sent_msg(self, msg_type, length):
        log_msg_hist(self.sent_msg_hist, msg_type, 'sent', 'B')
        log_sum(self.network_metrics, "23_num_messages_sent", 1)
        log_sum(self.network_metrics, "21_bytes_sent", length)

    def log_total_dist(self, dist):
        log_sum(self.general_metrics, "20_total_distance_traveled", dist)

    def get_final_report_(self, stop_time, dist):
        report = {
            "timeline": self.timeline,
            "25_response_stop_time": stop_time
        }
        report.update(self.network_metrics)
        report.update(self.sent_msg_hist)
        report.update(self.received_msg_hist)
        dist_traveled = {
            "26_dist_traveled": dist
        }
        report.update(dist_traveled)
        time_log = {
            "27_time_to_fail": self.general_metrics["30_time_to_fail"],
            "28_time_to_arrive": self.general_metrics["14_time_to_recover"]
        }
        report.update(time_log)
        return report

    def log_initial_metrics(self, gtl, is_standby, group_id, radio_range, standby_id,
                            timestamp, dispatch_duration, el):
        t = timestamp - self.start_time
        self.dispatched_time = time.time()
        self.general_metrics["00_gtl"] = gtl.tolist()
        self.general_metrics["02_group_id"] = group_id
        self.general_metrics["03_radio_range"] = radio_range
        self.general_metrics["10_dispatch_time"] = t
        self.general_metrics["12_arrival_time"] = t + dispatch_duration
        self.general_metrics["13_dispatch_duration"] = dispatch_duration
        self.log_standby_id(timestamp, standby_id)
        self.log_is_standby(timestamp, is_standby)
        self.timeline.append((t, TimelineEvents.DISPATCH, el.tolist()))
        # if is_standby:
        #     self.timeline.append((t + dispatch_duration, TimelineEvents.STANDBY, el.tolist()))
        # else:
        #     self.timeline.append((t + dispatch_duration, TimelineEvents.ILLUMINATE, el.tolist()))

    def log_arrival(self, timestamp, event, coord, dist):  # todo
        t = timestamp - self.start_time
        # self.general_metrics["05_standby_id"]
        self.general_metrics["14_time_to_recover"] = timestamp - self.dispatched_time
        self.timeline.append((t, event, coord.tolist(), dist))

    def log_standby_id(self, timestamp, standby_id):
        self.general_metrics["05_standby_id"].append((timestamp - self.start_time, standby_id))

    def log_is_standby(self, timestamp, is_standby):
        self.general_metrics["01_is_standby"].append((timestamp - self.start_time, is_standby))

    def log_failure_time(self, timestamp, is_standby, is_mid_flight):
        t = timestamp - self.start_time
        self.general_metrics["30_time_to_fail"] = timestamp - self.dispatched_time
        self.general_metrics["14_time_to_recover"] = -1
        if is_standby:
            self.timeline.append((t, TimelineEvents.STANDBY_FAIL, is_mid_flight))
        else:
            self.timeline.append((t, TimelineEvents.FAIL, is_mid_flight))

    def log_replacement(self, replacement_time, replacement_duration, failed_fls_id, failed_fls_gtl, is_mid_flight):
        t = replacement_time - self.start_time
        self.general_metrics["31_replacement_start_time"] = t
        self.general_metrics["32_replacement_arrival_time"] = t + replacement_duration
        self.general_metrics["33_replacement_duration"] = replacement_duration
        self.general_metrics["34_failed_fls_id"] = failed_fls_id
        self.timeline.append((t, TimelineEvents.REPLACE, is_mid_flight))
        # self.timeline.append((t + replacement_duration, TimelineEvents.ILLUMINATE_STANDBY, failed_fls_gtl.tolist()))


if __name__ == '__main__':
    mpl.use('macosx')

    # with open("../results/racecar/H2/racecar_D5_H2/bucket_face_G0_R90_T60_S6_PTrue.json") as f:
    #     data = json.load(f)
    #
    #     gen_point_metrics(data)

    with open("DIRECTORY/charts.json") as f:
        data = json.load(f)

        plt.step(data["dispatched"]["t"], data["dispatched"]["y"], where='post', label="Dispatched FLSs D1")
        # plt.step(data["standby"]["t"], data["standby"]["y"], where='post', label="Standby FLSs D1")
        plt.step(data["illuminating"]["t"], data["illuminating"]["y"], where='post', label="Illuminating FLSs D1")
        plt.step(data["failed"]["t"], data["failed"]["y"], where='post', label="Failed FLSs D1")
        plt.step(data["mid_flight"]["t"], data["mid_flight"]["y"], where='post', label="Mid-flight FLSs D1")
        plt.legend()
        plt.grid()

    with open("DIRECTORY/charts.json") as f:
        data = json.load(f)

        plt.step(data["dispatched"]["t"], data["dispatched"]["y"], where='post', label="Dispatched FLSs D3")
        # plt.step(data["standby"]["t"], data["standby"]["y"], where='post', label="Standby FLSs D3")
        plt.step(data["illuminating"]["t"], data["illuminating"]["y"], where='post', label="Illuminating FLSs D3")
        plt.step(data["failed"]["t"], data["failed"]["y"], where='post', label="Failed FLSs D3")
        plt.step(data["mid_flight"]["t"], data["mid_flight"]["y"], where='post', label="Mid-flight FLSs D3")
        plt.legend()
        plt.grid()
        # plt.yscale("log")
        plt.show()
