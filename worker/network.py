from dataclasses import dataclass, field
from typing import Any
import threading
import numpy as np
from config import Config
import message
from utils import logger
import time


class NetworkThread(threading.Thread):
    def __init__(self, event_queue, context, sock, state_machine):
        super(NetworkThread, self).__init__()
        self.event_queue = event_queue
        self.context = context
        self.sock = sock
        self.latest_message_id = dict()
        self._stop_event = threading.Event()
        self.state_machine = state_machine

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()

    def run(self):
        # stop_flag = False
        while not self.stopped():
            # if self.sock.is_ready():
            logger.debug(f"Sock: {self.sock}")
            msg, length = self.sock.receive()
            # self.context.log_received_message(msg.type, length)
            if self.is_message_valid(msg):
                self.context.log_received_message(msg, length)
                self.latest_message_id[msg.fid] = msg.id
                self.event_queue.put(NetworkThread.prioritize_message(msg))
                if msg is not None and msg.type == message.MessageTypes.STOP:
                    logger.debug(f"END NETWORK {self.context}")
                    self.context.network_stop_time = time.time()
                    break
                # if msg is not None and msg.type == message.MessageTypes.STOP or stop_flag:
                #     stop_flag = True
                #     logger.debug(f"NETWORK {self.context}")
                #     if not self.state_machine.check_mid_flight():
                #         # print(f"network_stopped_{self.context.fid}")
                #         logger.debug(f"END NETWORK {self.context}")
                #         break

    def is_message_valid(self, msg):
        if msg is None:
            self.context.log_dropped_messages()
            return False
        if msg.type == message.MessageTypes.STOP:
            return True
        if Config.DROP_PROB_RECEIVER:
            if np.random.random() <= Config.DROP_PROB_RECEIVER:
                self.context.log_dropped_messages()
                return False
        if msg.fid == self.context.fid:
            return False
        if msg.dest_fid != self.context.fid and msg.dest_fid != '*':
            return False
        if msg.dest_swarm_id != self.context.swarm_id and msg.dest_swarm_id != '*':
            return False
        if msg.fid in self.latest_message_id and msg.id < self.latest_message_id[msg.fid]:
            print("__msg_out_of_order__")
            return False
        if msg.type == message.MessageTypes.DISCOVER:
            dist = np.linalg.norm(msg.el - self.context.el)
            if dist > msg.range:
                return False
        return True

    @staticmethod
    def prioritize_message(msg):
        return PrioritizedItem(1, msg, False)


@dataclass(order=True)
class PrioritizedItem:
    priority: int
    event: Any = field(compare=False)
    stale: bool = field(compare=False)
