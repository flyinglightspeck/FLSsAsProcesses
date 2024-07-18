#!/bin/bash
for i in {0..0}
do
   cp "./experiments/config$i.py" config.py
   sleep 1
   python server.py
done
