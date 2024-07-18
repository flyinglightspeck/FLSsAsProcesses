import time
import numpy as np
from multiprocessing import shared_memory

import velocity
from config import Config
from .metrics import MetricTypes
from .history import History


class WorkerContext:
    def __init__(self, fid, gtl, el, metrics, shm_name=None, is_standby=False, standby_id=None, sid=0, group_id=None,
                 radio_range=2000):
        self.fid = fid
        self.gtl = gtl
        self.el = el
        self.dispatcher = el
        self.swarm_id = self.fid if group_id is None else group_id
        self.neighbors = dict()
        self.fid_to_w = dict()
        self.radio_range = radio_range
        self.max_range = Config.MAX_RANGE
        self.shm_name = shm_name
        self.message_id = 0
        self.alpha = Config.DEAD_RECKONING_ANGLE / 180 * np.pi
        self.metrics = metrics
        self.is_standby = is_standby
        self.standby_id = standby_id
        self.sid = sid
        self.network_stop_time = 0
        self.handler_stop_time = 0
        self.vm = None
        self.dist_traveled = 0

    def set_el(self, el):
        self.el = el
        # if self.shm_name:
        #     shared_mem = shared_memory.SharedMemory(name=self.shm_name)
        #     shared_array = np.ndarray((5,), dtype=np.float64, buffer=shared_mem.buf)
        #     shared_array[:3] = self.el[:]
        #     shared_mem.close()

        # self.history.log(MetricTypes.LOCATION, self.el)

    def set_radio_range(self, radio_range):
        self.radio_range = radio_range

    def deploy(self):

        dist = np.linalg.norm(self.gtl - self.el)
        timestamp, dur, dest = self.move(self.gtl - self.el)

        # self.metrics.log_initial_metrics(self.gtl, self.is_standby, self.swarm_id, self.radio_range,
        #                                  self.standby_id, timestamp, dur, dest)
        self.metrics.log_initial_metrics(self.gtl, self.is_standby, self.swarm_id, self.radio_range,
                                         self.standby_id, timestamp, dur, dest)

        return dur, dest, dist
        # if self.shm_name:
        #     shared_mem = shared_memory.SharedMemory(name=self.shm_name)
        #     shared_array = np.ndarray((5,), dtype=np.float64, buffer=shared_mem.buf)
        #     shared_array[4] = 0
        #     shared_mem.close()

    def move(self, vector):
        erred_v = self.add_dead_reckoning_error(vector)
        dest = self.el + erred_v
        # self.history.log(MetricTypes.LOCATION, self.el)
        self.metrics.log_total_dist(np.linalg.norm(vector))
        vm = velocity.VelocityModel(self.el, dest)

        if self.vm is None:
            self.vm = vm

        vm.solve()
        dur = vm.total_time
        timestamp = vm.start_t

        if Config.BUSY_WAITING:
            fin_time = time.time() + dur
            while True:
                if time.time() >= fin_time:
                    break
        # else: #Need Asking
        #     time.sleep(dur)

        # self.set_el(dest)

        return timestamp, dur, dest

    def add_dead_reckoning_error(self, vector):
        if vector[0] or vector[1]:
            i = np.array([vector[1], -vector[0], 0])
        elif vector[2]:
            i = np.array([vector[2], 0, -vector[0]])
        else:
            return vector

        if self.alpha == 0:
            return vector

        j = np.cross(vector, i)
        norm_i = np.linalg.norm(i)
        norm_j = np.linalg.norm(j)
        norm_v = np.linalg.norm(vector)
        i = i / norm_i
        j = j / norm_j
        phi = np.random.uniform(0, 2 * np.pi)
        error = np.sin(phi) * i + np.cos(phi) * j
        r = np.linalg.norm(vector) * np.tan(self.alpha)

        erred_v = vector + np.random.uniform(0, r) * error
        return norm_v * erred_v / np.linalg.norm(erred_v)

    def update_neighbor(self, ctx):
        if ctx.fid:
            self.neighbors[ctx.fid] = ctx
            self.fid_to_w[ctx.fid] = ctx.w

    def increment_range(self):
        if self.radio_range < self.max_range:
            self.set_radio_range(self.radio_range + 1)
            # logger.critical(f"{self.fid} range incremented to {self.radio_range}")
            return True
        else:
            return False

    def reset_range(self):
        self.set_radio_range(Config.INITIAL_RANGE)

    def log_received_message(self, msg, length):
        meta = {"length": length}
        msg_type = msg.type
        # self.history.log(MetricTypes.RECEIVED_MASSAGES, msg, meta)
        self.metrics.log_received_msg(msg_type, length)

    def log_dropped_messages(self):
        pass
        # self.history.log_sum(MetricTypes.DROPPED_MESSAGES)
        # self.metrics.log_sum("A4_num_dropped_messages", 1)

    def log_sent_message(self, msg, length):
        meta = {"length": length}
        msg_type = msg.type
        # self.history.log(MetricTypes.SENT_MESSAGES, msg, meta)
        self.metrics.log_sent_msg(msg_type, length)
        self.message_id += 1

    def log_replacement(self, timestamp, dur, failed_fls_id, failed_fls_gtl, is_mid_flight):
        self.metrics.log_replacement(timestamp, dur, failed_fls_id, failed_fls_gtl, is_mid_flight)
        self.metrics.log_is_standby(timestamp, False)

    def __repr__(self):
        return f"{'standby' if self.is_standby else 'normal'} fid={self.fid} gid={self.swarm_id}"
