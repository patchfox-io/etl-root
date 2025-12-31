#! /bin/bash

base_input_dir=$1

source /home/snerd/venvs/p3/bin/activate

declare -a dirs
i=1
for d in ${base_input_dir}*/
do
    dirs[i++]="${d}"
done
echo "There are ${#dirs[@]} directories in the current path"

for((i=1;i<=${#dirs[@]};i++))
do
    echo "processing: ${dirs[i]}"
    python3 -m patchfox_etl.cli --recurse --git ${dirs[i]} --patchfox-get-api-baseurl http://localhost:1702 --patchfox-post-api-baseurl http://localhost:1711 
done

