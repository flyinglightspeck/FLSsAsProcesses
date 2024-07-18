from enum import Enum


class MessageTypes(Enum):
    STOP = 0
    DISCOVER = 1
    FAILURE_DETECTED = 9
    REPLICA_REQUEST = 10
    REPLICA_REQUEST_HUB = 13
    ASSIGN_STANDBY = 11
    STANDBY_FAILED = 14
    MOVE = 12
    ERROR = -1

    def get_cat(self):
        pass
