#!/bin/bash

bash gen_conf_cluster.sh
sleep 10

for i in {0..0}
do
#   for j in {0..1}
#   do
#     echo "$i" "$j"
   bash start_cluster.sh "$i"
#   done
done
