import random
import time

import threading

import numpy as np

from message import Message, MessageTypes
from config import Config
from utils.distribution import left_half_exponential
from worker.metrics import TimelineEvents
from .types import StateTypes
from worker.network import PrioritizedItem
from utils import write_json, logger


class StateMachine:

    def __init__(self, context, sock, metrics, event_queue, default_failure_timeout):
        self.state = None
        self.context = context
        self.metrics = metrics
        self.sock = sock
        self.timer_failure = None
        self.event_queue = event_queue
        self.is_neighbors_processed = False
        self.handled_failure = dict()
        self.move_thread = None
        self.is_mid_flight = False
        self.is_terminating = False
        self.is_arrived = False
        self.unhandled_move = None
        self.move_time = 0
        self.default_failure_timeout = default_failure_timeout

    def start(self):
        logger.debug(f"STARTED {self.context} {time.time()}")
        self.enter(StateTypes.SINGLE)
        # dur, dest, dist = self.context.deploy()

        # print(f"MOVE READY {time.time() - self.metrics.start_time} fid={self.context.fid}")
    #     self.move(dur, dest, TimelineEvents.STANDBY if self.context.is_standby else TimelineEvents.ILLUMINATE, dist)
    #     self.move_time = time.time()
    #
        if self.context.is_standby:
            # send the id of the new standby to group members
            self.broadcast(Message(MessageTypes.ASSIGN_STANDBY).to_swarm(self.context))

    def handle_stop(self, msg):
        if msg is not None and (msg.args is None or len(msg.args) == 0):
            # logger.info("MAKING JSON FILES1")
            stop_msg = Message(MessageTypes.STOP).to_all()
            self.broadcast(stop_msg)
            self.context.handler_stop_time = time.time()

        if self.move_thread is not None:
            self.move_thread.cancel()
            self.move_thread = None

        self.cancel_timers()

        stop_time = self.context.handler_stop_time - self.context.network_stop_time
        try:
            result = {"FLS": self.context.fid}
            write_json(self.context.fid, result, self.metrics.results_directory, False)
        except Exception as e:
            logger.error(f"FLS Log Failed: fid={self.context.fid} INFO:{e}")
            self.send_to_server(Message(MessageTypes.ERROR))

    # purpose: Transitions to a new state by leaving the current state, setting the new state,
    #           and initializing timers or state-specific actions if needed
    def enter(self, state):
        self.leave(self.state)
        self.state = state

        # if self.state == StateTypes.SINGLE:
        #     self.set_timer_to_fail(self.default_failure_timeout)


    # purpose: Creates a message, wraps it in a prioritized item, puts the item into
    #           the event queue, and returns the item
    def put_state_in_q(self, event, args=()):
        msg = Message(event, args=args).to_fls(self.context)
        item = PrioritizedItem(1, msg, False)
        self.event_queue.put(item)
        return item

    # purpose: manages the state transition
    def leave(self, state):
        pass

    # purpose: Handles different failure-related events (stop, failure detection, replica requests, standby assignment,
    #           standby failure, and move) by invoking the appropriate methods based on the message type
    def drive_failure_handling(self, msg):
        event = msg.type

        if event == MessageTypes.STOP:
            self.handle_stop(msg)
        # elif event == MessageTypes.FAILURE_DETECTED:
        #     self.fail(msg)
        # elif event == MessageTypes.REPLICA_REQUEST:
        #     self.handle_replica_request(msg)
        # elif event == MessageTypes.ASSIGN_STANDBY:
        #     self.assign_new_standby(msg)
        # elif event == MessageTypes.STANDBY_FAILED:
        #     self.handle_standby_failure(msg)
        # elif event == MessageTypes.MOVE:
        #     self.handle_move(msg)


# purpose: Gives drive_failure_handling the message to respond to
    def drive(self, msg):
        self.drive_failure_handling(msg)

    # purpose: Sends a message to all FLSs in the network and logs the message length
    def broadcast(self, msg):
        msg.from_fls(self.context)
        length = self.sock.broadcast(msg)
        self.context.log_sent_message(msg, length)

    # purpose: Sends a message to the central server and logs the message length
    def send_to_server(self, msg):
        msg.from_fls(self.context).to_server(self.context.sid)
        length = self.sock.broadcast(msg)
        self.context.log_sent_message(msg, length)

    # purpose: cancels any active timers
    def cancel_timers(self):
        if self.timer_failure is not None:
            self.timer_failure.cancel()
            self.timer_failure = None