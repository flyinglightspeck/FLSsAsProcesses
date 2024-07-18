import itertools
import os
import sys

def_general_conf = {
    "INITIAL_RANGE": "2000",
    "MAX_RANGE": "2000",
    "DROP_PROB_SENDER": "0",
    "DROP_PROB_RECEIVER": "0",
    "DEAD_RECKONING_ANGLE": "0",
    "FAILURE_TIMEOUT": "60 * 2",
    "FAILURE_MODEL": "1",  # 0 for random, 1 for exponential
    "FAILURE_PROB": "0",
    "ACCELERATION": "1",
    "DECELERATION": "1",
    "MAX_SPEED": "3",
    "DISPLAY_CELL_SIZE": "0.05",
    "BUSY_WAITING": "False",
    "DURATION": "60 * 30",
    "G": "3",
    "SHAPE": "'chess'",
    "RESULTS_PATH": "'/proj/nova-PG0/Nima/results/'",
    "DEBUG": "True",
    "FILE_NAME_KEYS": "[('DISPATCHERS', 'D'), ('DISPATCH_RATE', 'R'), ('FAILURE_TIMEOUT', 'T'), ('MAX_SPEED', 'S'),"
    "('PRIORITIZE_ILLUMINATING_FLS', 'P')]",
    # "('NAME', 'N')]",
    #                   "('DISPATCHER_ASSIGN_POLICY', 'P')]",
    # "]",
    "DIR_KEYS": "['G']",
    "SERVER_TIMEOUT": "120",
    "PROCESS_JOIN_TIMEOUT": "120",
    "DISPATCHERS": "1",
    "DISPATCH_RATE": "'inf'",
    "MULTICAST": "False",
    "INPUT": "'chess_Kmeans20'",
    "RESET_AFTER_INITIAL_DEPLOY": "True",  # flag that if reset all metrics after intial FLSs are all deployed
    "SANITY_TEST": "0",  # 0 for not test, 1 for normal test with hub and no standby, 2 for standby test with no hub
    "SANITY_TEST_CONFIG": "[('NUMBER_OF_FLS', 10), ('DIST_TO_POINT', 10), ('CHECK_TIME_RANGE', 60 * 0.5, 60 * 1)]",
    "STANDBY_TEST_CONFIG": "[('RADIUS', 10), ('DEPLOY_DIST', 10), ('FAILURE_TIMEOUT_GAP', 10), ('CHECK_TIME_RANGE', 60 * 0.5, 60 * 1)]",
    "DISPATCHER_ASSIGN_POLICY": "'ShortestDistance'",
    "PRIORITIZE_ILLUMINATING_FLS": "True",
    "CEDED_POLICY": "1",
    "NAME": "'kmeans'"

}

general_props = [
    {
        "keys": ["G", "INPUT", "SHAPE"],
        "values": [
            # {"G": "0", "INPUT": "'bucket_face_G3'", "SHAPE": "'bucket_face'"},
            {"G": "0", "INPUT": "'chess_G3'", "SHAPE": "'chess'"},
            # {"G": "20", "INPUT": "'bucket_face_G20'", "SHAPE": "'bucket_face'"},
        ]
    },
    {
        "keys": ["DISPATCHERS"],
        "values": ["1"],
        # "values": ["1", "3"]
    },
    {
        "keys": ["FAILURE_TIMEOUT"],
        # "values": ["30", "60", "120", "300"]
        "values": ["60"]
        # "values": ["1", "3", "6", "30", "60", "120", "600"]
    },
    {
        "keys": ["MAX_SPEED", "ACCELERATION", "DECELERATION"],
        "values": [
            # {"MAX_SPEED": "0.3", "ACCELERATION": "0.3", "DECELERATION": "0.3"},
            {"MAX_SPEED": "6.11", "ACCELERATION": "6.11", "DECELERATION": "6.11"},
            # {"MAX_SPEED": "30", "ACCELERATION": "30", "DECELERATION": "30"},
            # {"MAX_SPEED": "66.67", "ACCELERATION": "66.67", "DECELERATION": "66.67"},
        ]
    },
    {
        "keys": ["DURATION"],
        "values": ["60 * .5"]
    },
    {
        "keys": ["PRIORITIZE_ILLUMINATING_FLS"],
        "values": ["True"]
    },
    {
        "keys": ["DISPATCHER_ASSIGN_POLICY"],
        # "values": ["'ShortestDistance'", "'PoD'", "'RR'", "'Random'"]
        "values": ["'ShortestDistance'"]
    },
    {
        "keys": ["DISPATCH_RATE"],
        "values": ["90"]
    },
]

if __name__ == '__main__':
    if not os.path.exists('experiments'):
        os.makedirs('experiments', exist_ok=True)

    file_name = "config"
    class_name = "Config"
    props = general_props
    def_conf = def_general_conf
    # if len(sys.argv) > 1:
    #     file_name = "test_config"
    #     class_name = "TestConfig"
    #     props = test_props
    #     def_conf = def_test_conf

    props_values = [p["values"] for p in props]
    print(props_values)
    combinations = list(itertools.product(*props_values))
    print(len(combinations))

    for j in range(len(combinations)):
        c = combinations[j]
        conf = def_conf.copy()
        for i in range(len(c)):
            for k in props[i]["keys"]:
                if isinstance(c[i], dict):
                    conf[k] = c[i][k]
                else:
                    conf[k] = c[i]
        with open(f'experiments/{file_name}{j}.py', 'w') as f:
            f.write(f'class {class_name}:\n')
            for key, val in conf.items():
                f.write(f'    {key} = {val}\n')