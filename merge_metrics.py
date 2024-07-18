import sys
import os
import utils
from config import Config


experiment_name = None
if len(sys.argv) > 1:
    experiment_name = sys.argv[1]

if not experiment_name:
    print("pass the directory name as input arg")

results_directory = os.path.join(Config.RESULTS_PATH, Config.SHAPE, experiment_name)
shape_directory = os.path.join(Config.RESULTS_PATH, Config.SHAPE)

utils.create_csv_from_json(results_directory)
utils.combine_csvs(results_directory, shape_directory)
