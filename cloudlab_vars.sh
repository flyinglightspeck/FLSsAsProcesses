#!/bin/bash
idx=1

# Number of total number of nodes
num_of_total_servers=6

# Number of secondary nodes, should be 'num_of_total_servers - idx'
N=5

# Host name of cloudlab server
HOSTNAME="StandbyTest4.nova-PG0.utah.cloudlab.us"

# Username of cloudlab, this gives access to nodes
USERNAME="Nima_yaz"
REMOTE_HOME="/users/${USERNAME}"


REPO_NAME="StandbyTest"