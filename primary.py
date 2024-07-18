import math
import queue
import socket
import random
import threading
import sys
import time
import os
from abc import ABC, abstractmethod
import numpy as np
import psutil

from dispatcher import Dispatcher
from test_config import TestConfig
from config import Config
from constants import Constants
from message import Message, MessageTypes
import worker
import utils
from utils import logger
from utils.file import read_cliques_xlsx, get_group_mapping, read_point_info_from_cliques_xlsx, get_time_range
from utils.com_socket import send_msg
from utils.generate_circle_coord import generate_circle_coordinates
from utils.sanity_metrics import *
from utils.report import *
from random import choice

from worker.metrics import point_to_id

CONFIG = TestConfig if TestConfig.ENABLED else Config


def join_config_properties(conf, props):
    return "_".join(
        f"{k[1] if isinstance(k, tuple) else k}{int(getattr(conf, k[0] if isinstance(k, tuple) else k)) if isinstance(getattr(conf, k[0] if isinstance(k, tuple) else k), float) else getattr(conf, k[0] if isinstance(k, tuple) else k)}"
        for k in
        props)


class DispatchPolicy(ABC):
    @abstractmethod
    def assign(self, **kwargs):
        pass


# class PoDPolicy(DispatchPolicy):
#     def assign(self, **kwargs):
#         ds = kwargs["dispatchers"]
#
#         if len(ds) == 1:
#             return ds[0]
#         elif len(ds) == 2:
#             if ds[0].q.qsize() < ds[1].q.qsize():
#                 return ds[0]
#             return ds[1]
#
#         rand_ds = random.sample(ds, 2)
#         if rand_ds[0].q.qsize() < rand_ds[1].q.qsize():
#             return rand_ds[0]
#         return rand_ds[1]


# class RRPolicy(DispatchPolicy):
#     def assign(self, **kwargs):
#         ds = kwargs["dispatchers"]
#         pid = kwargs["fid"]
#
#         return ds[pid % len(ds)]


# class RandomPolicy(DispatchPolicy):
#     def assign(self, **kwargs):
#         ds = kwargs["dispatchers"]
#
#         random.seed()
#
#         return ds[random.randint(0, len(ds) - 1)]


class ShortestDistancePolicy(DispatchPolicy):
    def assign(self, **kwargs):
        ds = kwargs["dispatchers"]
        coord = kwargs["gtl"]

        dispatcher_coords = np.stack([d.coord for d in ds])
        return ds[np.argmin(np.linalg.norm(dispatcher_coords - coord, axis=1))]


# class HybridSDPoDPolicy(DispatchPolicy):
#     sd = ShortestDistancePolicy()
#     pod = PoDPolicy()
#
#     def assign(self, **kwargs):
#         closest_d = HybridSDPoDPolicy.sd.assign(**kwargs)
#         if closest_d.q.qsize():
#             return HybridSDPoDPolicy.pod.assign(**kwargs)
#         return closest_d


class PrimaryNode:
    def __init__(self, N, name):
        self.N = N  # number of secondary servers
        self.name = name
        self.sock = None
        self.failure_handler_socket = None
        self.client_sockets = []
        self.result_name = None
        self.dir_experiment = None
        self.dir_meta = None
        self.dir_figure = None
        self.start_time = 0
        self.end_time = 0
        self.dispatchers_coords = []
        self.dispatchers = []
        self.groups = []
        self.radio_ranges = []
        self.group_members = {}
        self.group_standby_id = {}
        self.group_standby_coord = {}
        self.group_radio_range = {}
        self.pid = 0
        self.dispatch_policy = eval(Config.DISPATCHER_ASSIGN_POLICY + "Policy()")
        self.num_handled_failures = 0
        self.num_initial_illum_flss = 0
        self.num_initial_standbys = 0
        self.num_replaced_flss = 0
        self.num_replaced_standbys = 0
        self.stop_flag = False
        self.stop_thread = None
        self.center = []
        self.init_num = 0
        self.single_indexes = []
        self.cpu_util = []
        self.deployed_num = 0

    def _create_server_socket(self):
        # Experimental artifact to gather theoretical stats for scientific publications.
        self.sock = socket.socket()

    def _bind_server_socket(self):
        logger.info(f"Binding primary node to {Constants.SERVER_ADDRESS}")

        while True:
            try:
                self.sock.bind(Constants.SERVER_ADDRESS)
            except OSError:
                time.sleep(10)
                continue
            break

    def _listen_to_secondary_nodes(self):
        logger.info("Waiting for secondary nodes to connect")

        self.sock.listen(N)
        for i in range(N):
            client, address = self.sock.accept()
            logger.debug(address)
            self.client_sockets.append(client)

    def _setup_results_directory(self):
        if len(CONFIG.FILE_NAME_KEYS):
            result_config = join_config_properties(CONFIG, CONFIG.FILE_NAME_KEYS)
        else:
            result_config = self.name
        self.result_name = f"{Config.SHAPE}_{result_config}"

        if len(CONFIG.DIR_KEYS):
            group_config = join_config_properties(CONFIG, CONFIG.DIR_KEYS)
        else:
            group_config = ""

        self.dir_experiment = os.path.join(Config.RESULTS_PATH, Config.SHAPE, group_config)
        self.dir_meta = os.path.join(self.dir_experiment, self.result_name)
        self.dir_figure = os.path.join(self.dir_experiment, 'figures')

        if not os.path.exists(self.dir_meta):
            os.makedirs(os.path.join(self.dir_meta, 'json'), exist_ok=True)
        if not os.path.exists(self.dir_figure):
            os.makedirs(self.dir_figure, exist_ok=True)

    def delete_previous_json_files(self, path):
        try:
            # Iterate over all files in the folder
            for root, dirs, files in os.walk(path):
                for file in files:
                    path = os.path.join(root, file)
                    # Delete the file
                    os.remove(path)
            logger.info("All files under the folder have been deleted.")
        except Exception as e:
            logger.error(f"Error occurred: {e}")

    def _define_dispatcher_coords(self):
        l = 98
        w = 49

        if Config.SANITY_TEST == 3 and Config.DISPATCHERS == 3:
            self.dispatchers_coords = np.array([[1, 1, 0], [6, 6, 0], [11, 11, 0]])

        elif Config.DISPATCHERS == 1:
            if Config.SANITY_TEST > 0:
                self.dispatchers_coords = np.array([self.center])
            else:
                self.dispatchers_coords = np.array([[l / 2, w / 2, 0]])
        elif Config.DISPATCHERS == 3:
            if Config.SHAPE == "skateboard":
                self.dispatchers_coords = np.array([[8.5, 22, 0], [19, 50.6, 0], [29, 76, 0]])
            else:
                self.dispatchers_coords = np.array([[l / 2, w / 2, 0], [l, w, 0], [0, 0, 0]])
        elif Config.DISPATCHERS == 4:
            if Config.SHAPE == "skateboard":
                self.dispatchers_coords = np.array([[8.5, 22, 0], [8.5, 76, 0], [29, 22, 0], [29, 76, 0]])
            else:
                self.dispatchers_coords = np.array([[l / 4, w / 4, 0], [l * 3 / 4, w / 4, 0], [l / 4, w * 3 / 4, 0], [l * 3 / 4, w * 3 / 4, 0]])
        elif Config.DISPATCHERS == 5:
            self.dispatchers_coords = np.array([[l / 2, w / 2, 0], [l, 0, 0], [0, w, 0], [l, w, 0], [0, 0, 0]])

    def _initialize_dispatchers(self):
        logger.info(f"Initializing {Config.DISPATCHERS} dispatchers")

        for coord in self.dispatchers_coords:

            if Config.PRIORITIZE_ILLUMINATING_FLS:
                q = queue.PriorityQueue()
            else:
                q = queue.Queue()
            d = Dispatcher(q, Config.DISPATCH_RATE, coord)
            self.dispatchers.append(d)

    def _start_dispatchers(self):
        logger.info(f"Starting {Config.DISPATCHERS} dispatchers")

        for d in self.dispatchers:
            d.start()

    def _send_msg_to_all_nodes(self, msg):
        for nid in range(len(self.client_sockets)):
            try:
                self._send_msg_to_node(nid, msg)
            except Exception as e:
                self._send_msg_to_node(nid, msg)
                logger.info("Connection Reset, Retry")

    def _send_msg_to_node(self, nid, msg):
        send_msg(self.client_sockets[nid], msg)
        logger.debug(f"SENDING TO {nid}: {msg}")

    def _receive_msg_from_node(self, nid):
        return self.client_sockets[nid].recv(1024)

    def _start_secondary_nodes(self):
        logger.info(f"Starting {N} secondary nodes")
        self.start_time = time.time()
        self._send_msg_to_all_nodes((self.start_time, self.dir_meta))

    def _read_groups(self):
        if Config.SANITY_TEST == 0:
            # self.groups, self.radio_ranges = read_cliques_xlsx(
            #     os.path.join(self.dir_experiment, f'{Config.INPUT}.xlsx'))

            # change input directory
            self.groups, self.radio_ranges = read_cliques_xlsx(
                f'./assets/pointcloud/{Config.INPUT}.xlsx')
        elif Config.SANITY_TEST == 1:
            height = min([2, math.sqrt(Config.SANITY_TEST_CONFIG[1][1])])
            radius = math.sqrt(Config.SANITY_TEST_CONFIG[1][1] ** 2 - height ** 2)
            self.center = [radius + 1, radius + 1, 0]
            self.groups = generate_circle_coordinates(self.center, radius, height, Config.SANITY_TEST_CONFIG[0][1])
            self.radio_ranges = [Config.MAX_RANGE] * len(self.groups)

        elif Config.SANITY_TEST >= 2:
            height = Config.STANDBY_TEST_CONFIG[1][1]
            radius = Config.STANDBY_TEST_CONFIG[0][1]
            self.center = [radius + 1, radius + 1, 0]
            self.groups = generate_circle_coordinates(self.center, radius, height, Config.G)
            self.radio_ranges = [Config.MAX_RANGE] * len(self.groups)

        if Config.DEBUG and Config.SANITY_TEST == 0:
            self.groups = self.groups[:8]
            self.radio_ranges = self.radio_ranges[:8]

        for group in self.groups:
            for coord in group:
                self.init_num += 1

        single_members = []
        single_indexes = []
        max_dist_singles = 0
        for k in range(len(self.groups)):
            if self.groups[k].shape[0] == 1:
                if len(single_indexes):
                    max_dist_n = np.max(np.linalg.norm(np.stack(single_members) - self.groups[k][0], axis=1))
                    max_dist_singles = max(max_dist_singles, max_dist_n)
                single_members.append(self.groups[k][0])
                single_indexes.append(k)

        if Config.CEDED_POLICY == 0:
            # remove single nodes from groups
            for k in reversed(single_indexes):
                self.groups.pop(k)
                self.radio_ranges.pop(k)

            # add single nodes as one group to the groups
            if len(single_members):
                self.groups.append(np.stack(single_members))
                self.radio_ranges.append(max_dist_singles)

        elif Config.CEDED_POLICY == 2:
            self.single_indexes = single_indexes

        elif Config.CEDED_POLICY == 3:
            for k in reversed(single_indexes):
                self.groups.pop(k)
                self.radio_ranges.pop(k)

            centers = []
            for group in self.groups:
                centers.append([sum(coord) / len(coord) for coord in zip(*group)])

            for coord in single_members:

                closest_index = 0
                closest_distance = float('inf')

                for i, center in enumerate(centers[1:], 1):
                    distance = distance_between(coord, center)
                    if distance < closest_distance:
                        closest_distance = distance
                        closest_index = i
                self.groups[closest_index] = np.append(self.groups[closest_index], coord, axis=0)
        logger.info(f"Read Group")


    def _assign_dispatcher(self, properties):
        return self.dispatch_policy.assign(dispatchers=self.dispatchers, **properties)

    def _deploy_fls(self, properties, deploy_at_destination=False, initial_fls=False):

        # Check if the FLS deployed has a duplicated ID:
        if properties["fid"] != (self.deployed_num + 1):
            logger.error("<============= FLS Deployed with duplicated ID ==============>")
            exit(1)

        nid = properties["fid"] % self.N
        dispatcher = self._assign_dispatcher(properties)
        if deploy_at_destination:
            properties["el"] = properties["gtl"]

        if properties["el"] is None:
            properties["el"] = dispatcher.coord

        try:
            if "is_standby" not in properties:
                fls_type = 0
            elif properties["is_standby"]:
                fls_type = 1
            else:
                logger.info("UNIDENTIFIED FLS")
                fls_type = 1
        except Exception as e:
            print(e)
            fls_type = 1

        properties["gtl"] = properties["gtl"]

        timestamp = time.time()
        try:
            dispatcher.q.put((fls_type, timestamp, lambda: self._send_msg_to_node(nid, properties)))

        except Exception as e:
            logger.info("Connection reset by peer")
            dispatcher.q.put((fls_type, timestamp, lambda: self._send_msg_to_node(nid, properties)))

        dispatcher.num_dispatched += 1
        self.deployed_num += 1

    def _dispatch_initial_formation(self):
        logger.info("Assigning FLSs to dispatchers")

        for i in range(len(self.groups)):
            group = self.groups[i]
            group_id = self.pid + 1
            self.group_radio_range[group_id] = self.radio_ranges[i]
            self.group_standby_coord[group_id] = None
            self.group_standby_id[group_id] = None

            if Config.G:
                member_count = group.shape[0]
                sum_x = np.sum(group[:, 0])
                sum_y = np.sum(group[:, 1])
                sum_z = np.sum(group[:, 2])
                stand_by_coord = np.array([
                    float(round(sum_x / member_count)),
                    float(round(sum_y / member_count)),
                    float(round(sum_z / member_count))
                ])
                self.group_standby_coord[group_id] = stand_by_coord
                self.group_standby_id[group_id] = group_id + len(group)

            # deploy group members
            for member_coord in group:
                self.pid += 1
                fls = {
                    "fid": self.pid,
                    "el": None, "gtl": member_coord,
                    "radio_range": self.group_radio_range[group_id],
                    "group_id": group_id,
                }

                # If is doing stnadby sanity test, deploy the FLS directly to points on ring
                self._deploy_fls(fls, Config.SANITY_TEST == 2)
                self.num_initial_illum_flss += 1

            # Do not dispatch standby FLSs for cedded FLS Group
            if Config.CEDED_POLICY == 2 and i in self.single_indexes:
                continue

            # deploy standby
            if Config.G:
                self.pid += 1
                fls = {
                    "fid": self.pid,
                    "el": None, "gtl": self.group_standby_coord[group_id],
                    "radio_range": self.group_radio_range[group_id],
                    "is_standby": True, "group_id": group_id,
                }
                self._deploy_fls(fls, Config.SANITY_TEST == 4)
                self.num_initial_standbys += 1

        logger.info(f"Assigned {self.pid} FLSs to dispatchers")

    def _stop_dispatchers(self):
        logger.info("Stopping dispatchers")

        delay_list = []

        for d in self.dispatchers:
            d.stop()
        for d in self.dispatchers:
            d.join()
        return delay_list

    def _stop_secondary_nodes(self):
        logger.info("Stopping secondary nodes")
        self._send_msg_to_all_nodes(False)
        client_threads = []
        for nid in range(len(self.client_sockets)):
            t = threading.Thread(target=self._receive_msg_from_node, args=(nid,))
            t.start()
            client_threads.append(t)
        for t in client_threads:
            t.join()

    def _get_metrics(self):
        return [
            ["Metric", "Value"],
            ["Initial illuminating FLSs", self.num_initial_illum_flss],
        ]

    def simple_get_metrics(self, directory):
        # Define the JSON directory
        json_dir = os.path.join(directory, 'json')

        # Initialize the sum
        sum_numbers = 0

        # Check if the directory exists
        if os.path.exists(json_dir):
            # Iterate through JSON files in the directory
            filenames = os.listdir(json_dir)
            filenames.sort()

            for filename in filenames:
                if filename.endswith('.json'):
                    with open(os.path.join(json_dir, filename)) as f:
                        try:
                            data = json.load(f)
                            # Assuming each JSON file has a key called "nima" where the value is stored
                            sum_numbers += data.get('FLS', 0)
                        except json.decoder.JSONDecodeError:
                            print(f"Error reading {filename}")

        # Return the metrics list with the summed value
        return [
            ["Metric", "Value"],
            ["Sum Numbers in Jsons", sum_numbers],
        ]

    def gen_group_map(self):
        if Config.SANITY_TEST == 0:
            group_map, group_id = get_group_mapping(f'./assets/pointcloud/{Config.INPUT}.xlsx')
        else:
            group_map = dict()
            for group in self.groups:
                for coord in group:
                    group_map[point_to_id(coord)] = 0
            group_id = [0]
        return group_map, group_id

    def write_sanity_results(self):
        sanity_result = [['', 'Stander Result', 'Experiment Result']]

        if Config.SANITY_TEST == 1:
            experiment_result = read_sanity_metrics(self.dir_meta, [round(Config.SANITY_TEST_CONFIG[2][1]),
                                                                    round(Config.SANITY_TEST_CONFIG[2][2], 5)])

            stander_mttr = time_to_arrive(Config.MAX_SPEED, Config.ACCELERATION, Config.DECELERATION,
                                          Config.SANITY_TEST_CONFIG[1][1] * Config.DISPLAY_CELL_SIZE)
        else:
            experiment_result = read_sanity_metrics(self.dir_meta, [round(Config.STANDBY_TEST_CONFIG[3][1]),
                                                                    round(Config.STANDBY_TEST_CONFIG[3][2], 5)])
            stander_mttr = time_to_arrive(Config.MAX_SPEED, Config.ACCELERATION, Config.DECELERATION,
                                          Config.STANDBY_TEST_CONFIG[0][1] * Config.DISPLAY_CELL_SIZE)

        num_illuminate = 0
        num_midflight = 0

        if Config.SANITY_TEST == 1:
            checkRange = range(round(Config.SANITY_TEST_CONFIG[2][1]), round(Config.SANITY_TEST_CONFIG[2][2], 5))
        else:
            checkRange = range(round(Config.STANDBY_TEST_CONFIG[3][1]), round(Config.STANDBY_TEST_CONFIG[3][2], 5))
        for t in checkRange:

            if Config.SANITY_TEST == 1:
                cur_midflight = num_mid_flight(Config.SANITY_TEST_CONFIG[0][1], experiment_result[4],
                                               experiment_result[3])
                num_midflight += cur_midflight
                num_illuminate += num_illuminating(Config.SANITY_TEST_CONFIG[0][1], cur_midflight)
            else:
                cur_midflight = 1 if t % Config.STANDBY_TEST_CONFIG[2][1] >= experiment_result[4] else 0
                num_midflight += cur_midflight
                num_illuminate += num_illuminating(Config.G, cur_midflight)

        if Config.SANITY_TEST == 1:
            num_midflight /= len(
                range(round(Config.SANITY_TEST_CONFIG[2][1]), round(Config.SANITY_TEST_CONFIG[2][2], 5)))
            num_illuminate /= len(
                range(round(Config.SANITY_TEST_CONFIG[2][1]), round(Config.SANITY_TEST_CONFIG[2][2], 5)))
        else:
            num_midflight /= len(
                range(round(Config.STANDBY_TEST_CONFIG[3][1]), round(Config.STANDBY_TEST_CONFIG[3][2], 5)))
            num_illuminate /= len(
                range(round(Config.STANDBY_TEST_CONFIG[3][1]), round(Config.STANDBY_TEST_CONFIG[3][2], 5)))

        if Config.SANITY_TEST == 1:
            num_failed = num_of_failed(Config.SANITY_TEST_CONFIG[2][2], experiment_result[3],
                                       Config.SANITY_TEST_CONFIG[0][1])
        else:
            num_failed = Config.DURATION / Config.STANDBY_TEST_CONFIG[2][1]

        sanity_result.append(['Total Failed', num_failed, experiment_result[0]])
        sanity_result.append(['Avg mid_flight', num_midflight, experiment_result[1]])
        sanity_result.append(['Avg_illuminate', num_illuminate, experiment_result[2]])

        if Config.SANITY_TEST <= 1:
            theo_MTTF = Config.FAILURE_TIMEOUT / 2
        else:
            theo_MTTF = Config.DURATION / 2
        sanity_result.append(['MTTF', theo_MTTF, experiment_result[3]])
        sanity_result.append(['MTTR', stander_mttr, experiment_result[4]])
        utils.write_csv(self.dir_meta, sanity_result, 'sanity_check')

    def _write_results(self):
        logger.info("Writing results")
        # utils.write_csv(self.dir_meta, self._get_dispatched_num(), 'dispatcher')
        utils.write_csv(self.dir_meta, self._get_metrics(), 'metrics')

        utils.write_csv(self.dir_meta, self.simple_get_metrics(self.dir_meta), 'Example_Metrics')

        # group_map, group_id = self.gen_group_map()

        # utils.create_csv_from_json(Config, self.init_num, self.dir_meta,
        #                            os.path.join(self.dir_figure, f'{self.result_name}.jpg'), group_map)
        if Config.RESET_AFTER_INITIAL_DEPLOY:
            if Config.SANITY_TEST == 1:
                total_point_num = Config.SANITY_TEST_CONFIG[0][1]
                group_num = 0

            elif Config.SANITY_TEST == 2:
                total_point_num = 0
                group_num = 0

            elif Config.SANITY_TEST == 3:
                total_point_num = Config.G
                group_num = 1
            elif Config.DEBUG:
                total_point_num = len(self.groups) * len(self.groups[0])
            else:
                total_point_num = 0
                for group in self.groups:
                    total_point_num += len(group)
                # # IMPORTANT !!!!!
                # if Config.SHAPE == "dragon":
                #     total_point_num = 760
                # elif Config.SHAPE == "skateboard":
                #     total_point_num = 1727
                # elif Config.SHAPE == "hat":
                #     total_point_num = 1562
                # elif CONFIG.SHAPE == ""
                # total_point_num, group_num = read_point_info_from_cliques_xlsx(
                #     os.path.join(self.dir_experiment, f'{Config.INPUT}.xlsx'))

                if Config.G == 0:
                    group_num = 0
            # reset after all initial illumination FLSs and initial Standby FLSs were dispatched
            # initial_fls_num = total_point_num + group_num

            # reset after all initial illumination FLSs were dispatched
            initial_fls_num = total_point_num
        else:
            initial_fls_num = 0

        initial_fls_num = float(initial_fls_num)

        # time_range = utils.create_csv_from_json_no_group(Config, self.init_num, self.dir_meta, initial_fls_num,
        #                                                  os.path.join(self.dir_figure, f'{self.result_name}.jpg'))

        # draw_last_frame(self.dir_meta, self.result_name, time_range[1])
        utils.write_configs(self.dir_meta, self.start_time)
        utils.combine_csvs(self.dir_meta, self.dir_experiment, "reli_" + self.result_name)

        if Config.SANITY_TEST > 0:
            self.write_sanity_results()
        # write_final_report(self.dir_meta, self.dir_meta, self.result_name, len(group_id), time_range)

    def _write_cpu_data(self, filename):
        with open(filename, 'w') as file:
            for data in self.cpu_util:
                file.write(f"{data[0]},{data[1]}\n")

    def stop_experiment(self):
        self._stop_dispatchers()

        logger.info(f"Stopping the experiment, experiment time={time.time() - self.start_time}")

        stop_send_time = time.time()
        self._stop_secondary_nodes()
        logger.info(f"Time for All process stop={time.time() - stop_send_time}")

        self.stop_flag = True
        self._write_results()

        if not os.path.exists(f"{self.dir_meta}/cpu_util/"):
            os.makedirs(f"{self.dir_meta}/cpu_util/", exist_ok=True)
        self._write_cpu_data(self.dir_meta + "/cpu_util/0_cpu_util.txt")

    def start_experiment(self):

        self._setup_results_directory()
        self.delete_previous_json_files(self.dir_meta)
        self._create_server_socket()
        self._bind_server_socket()
        self._listen_to_secondary_nodes()
        self._read_groups()
        self._define_dispatcher_coords()
        self._start_secondary_nodes()
        self._initialize_dispatchers()
        self._dispatch_initial_formation()
        # self._create_failure_handler_socket()
        self._start_dispatchers()
        self.stop_thread.start()

    def start_termination_timer(self):
        self.stop_thread = threading.Timer(Config.DURATION, self.stop_experiment)



if __name__ == '__main__':
    N = 1
    name = str(int(time.time()))
    if len(sys.argv) > 1:
        N = int(sys.argv[1])
        name = sys.argv[2]

    primary_node = PrimaryNode(N, name)
    primary_node.start_termination_timer()
    primary_node.start_experiment()

    # rewrite_reports()
