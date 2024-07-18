#!/bin/bash

source cloudlab_Vars.sh

idx=0

# Should be your own github token
GITHUB_TOKEN="your token HERE"

# Fork our repository and replace this with your own
GITHUB_REPO="your repo link HERE"

now=$(date +%d_%b_%H_%M_%S)

# This can be used to delete the .ssh key
#    ssh -oStrictHostKeyChecking=no ${server_addr} "rm ${REMOTE_HOME}/.ssh/id_rsa"


# Parameters to control actions
setup_nodes=false
kill_processes=false
update_repo=false
copy_key=false
delete_repo=false
run_nohup=false

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --setup)
            setup_nodes=true
            ;;
        --kill)
            kill_processes=true
            ;;
        --update)
            update_repo=true
            ;;
        --copy-key)
            copy_key=true
            ;;
        --delete-repo)
          delete_repo=true
          ;;
        --run-nohup)
            run_nohup=true
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
    shift
done

if [ "$copy_key" = true ]; then
    i=0
    server_addr=${USERNAME}@node-$i.${HOSTNAME}
    scp -oStrictHostKeyChecking=no ~/.ssh/id_rsa ${server_addr}:${REMOTE_HOME}/.ssh/
fi

for (( i=0; i<num_of_total_servers; i++ )); do
    server_addr=${USERNAME}@node-$i.${HOSTNAME}

    if [ "$setup_nodes" = true ]; then
        # This is only used to clone and setup for the first time
        ssh -oStrictHostKeyChecking=no ${server_addr} "git clone ${GITHUB_REPO} && cd ${REPO_NAME} && mkdir log && bash setup.sh" &
    fi

    if [ "$delete_repo" = true ]; then
        # This is only used to delete the repository
        ssh -oStrictHostKeyChecking=no ${server_addr} "rm -rf ${REPO_NAME}" &
    fi

    if [ "$kill_processes" = true ]; then
        # This is for killing all the running processes
        ssh -oStrictHostKeyChecking=no ${server_addr} "sudo pkill python3" &
    fi

    if [ "$update_repo" = true ]; then
        # This can be used to pull updates from the repository
        ssh -oStrictHostKeyChecking=no ${server_addr} "cd ${REPO_NAME} && git pull" &
#        ssh -oStrictHostKeyChecking=no ${server_addr} "cd ${REPO_NAME} && git fetch --all && git reset --hard origin/main" &
#        ssh -oStrictHostKeyChecking=no ${server_addr} "cd ${REPO_NAME} && git checkout main" &
    fi
done

# Run nohup script on the primary node
if [ "$run_nohup" = true ]; then
    server_addr=${USERNAME}@node-0.${HOSTNAME}
    ssh -oStrictHostKeyChecking=no ${server_addr} "cd StandbyTest && bash nohup_run.sh"
fi


# Wait for all background processes to finish
wait
