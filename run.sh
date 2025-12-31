#!/bin/sh

organization=$1
datasource=$2
datapath=$3
api_token=$4
post_api_base_url=$5
get_api_base_url=$6

bearer_token=$(python3 ./scripts/auth.py "${post_api_base_url}" "${api_token}")
python3 ./scripts/generate_csv.py "${datapath}" "${datasource}.csv" 
python3 ./scripts/engage.py "${datasource}.csv" "${organization}" "${bearer_token}" "${post_api_base_url}" "${get_api_base_url}" "${datasource}"
