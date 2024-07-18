#!/bin/bash

nohup bash run_all_cluster.sh > my.log 2>&1 &
echo $! > save_pid.txt