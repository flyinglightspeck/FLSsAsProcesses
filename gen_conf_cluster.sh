#!/bin/bash

source cloudlab_vars.sh

python3 gen_conf.py

for (( i=1; i<num_of_total_servers; i++ )); do
    server_addr=${USERNAME}@node-$i.${HOSTNAME}
    ssh -oStrictHostKeyChecking=no -f "${server_addr}" "cd ${REPO_NAME} && sudo python3 gen_conf.py" &
done

echo "Generate Config"