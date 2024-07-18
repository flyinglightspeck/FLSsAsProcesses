class Constants:

    # BROADCAST_ADDRESS = ("127.0.0.1", 5000)
    BROADCAST_PORT = 5000
    SERVER_PORT = 6000
    WORKER_ADDRESS = ("", 5000)

    RUNNING_ON_CLOUDLAB = False  # Set to True for CloudLab, False for localhost

    if RUNNING_ON_CLOUDLAB:
        SERVER_ADDRESS = ("10.0.1.1", 6000)  # cloudlab
        BROADCAST_ADDRESS = ("10.0.1.255", 5000)  # cloudlab
    else:
        SERVER_ADDRESS = ("localhost", 6000)  # localhost
        BROADCAST_ADDRESS = ("<broadcast>", 5000)  # localhost

    MULTICAST_GROUP_ADDRESS = ('224.3.29.25', 5000)
    MULTICAST_GROUP = '224.3.29.25'

    # BROADCAST_ADDRESS = ("<broadcast>", 5000)  # localhost
    # BROADCAST_ADDRESS = ("10.0.1.255", 5000)  # cloudlab
    #     SERVER_ADDRESS = ("10.0.1.1", 6000)  # cloudlab
    # SERVER_ADDRESS = ("localhost", 6000)  # localhost
