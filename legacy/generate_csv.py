#!/usr/bin/env python3

# creates CSV file containing build file types and paths
# (c) 2022 patchfox.io


import sys
import os
import string

from constants import *

import logging as LOG

LOG.basicConfig(
    format='[%(asctime)s] [%(funcName)s] [%(levelname)s] %(message)s',
    level=LOG.INFO,
    datefmt='%Y-%m-%d %H:%M:%S',
    encoding='utf-8'
)


def main(search_dir, output_filename):
    """ find build files and serialize them as CSV records
    """
    LOG.info(f'building CSV from path: {search_dir}')

    # validate arguments
    if not os.path.exists(search_dir):
        LOG.error(f'{search_dir} does not exist on filesystem')
        print_usage_str_and_exit_on_error()

    normalized_output_filename = normalize_output_filename(output_filename)

    csv_records = []
    excluded_dirs = set([
        'node_modules', # otherwise it'll include all installed node packages
        'site-packages', # otherwise it'll include all installed virtual env python packages
        '.ve', 'venv', # since packages can exist (and be erroneously included) in other dirs
        'generated-sources', # nested generated java files can have their own pom.xml files
        '.angular', # angular likes to cache its own package with its own package.json 
    ])
    for root, dirs, files, in os.walk(search_dir, topdown=True):
        dirs[:] = [d for d in dirs if d not in excluded_dirs]
        for file in files:
            LOG.debug(f'looking at {file}')
            if file in REVERSE_BUILD_TYPE_DICT.keys():
                # ty SO https://stackoverflow.com/a/3925147/2234770
                norm_root = os.path.normpath(root)
                project_name = os.path.basename(norm_root)
                build_type = REVERSE_BUILD_TYPE_DICT[file]
                build_file_path = os.path.join(root, file)
                record = f'{project_name},{build_type},{build_file_path}'
                LOG.debug(f'adding record: {record}')
                csv_records.append(record)

    if not csv_records:
        LOG.error('no build files found!')
        print_usage_str_and_exit_on_error()
    
    csv_records.sort()

    with open(normalized_output_filename, 'w') as f:
        f.writelines(record + '\n' for record in csv_records)

    # see you space cowboy...
    LOG.info('done!')


def normalize_output_filename(caller_supplied_name):
    """ ensures caller didn't supply a weird file handle. ensures resultant
    filename has ".csv" as an extension
    """
    output_filename = caller_supplied_name

    if output_filename[-4:] != ".csv":
        output_filename += ".csv"

    allowed = set(
        string.ascii_letters +
        string.digits +
        "_" +
        "-" +
        "."
    )

    if not set(output_filename) <= allowed:
        LOG.error(f'{output_filename} not suitable as a filename!')
        print_usage_str_and_exit_on_error()

    return output_filename


def print_banner():
    """ show some style...
    """
    banner = '''

 %@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%
 %@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%
 %@@@@@@@@@@@@@#+-:....:-+%@@@@%+=:....:-+#@@@@@@@@@@@@@%
 %@@@@@@@@@@%+.          -%@@*:             =%@@@@@@@@@@%
 %@@@@@@@@@#.     -+*++-=@@%:     -=+*+-.     *@@@@@@@@@%
 %@@@@@@@@%     +@@@@@@@@@@*=====%@@@@@@@*     #@@@@@@@@%
 %@@@@@@@@=    +@@%###%%%%%%%%%%%%%%###%@@*    -@@@@@@@@%
 %@@@@@@@@-    *@@%####%%%%%%%%%%%%#####@@#    -@@@@@@@@%
 %@@@@@@@@*    .#@@@%%@@@#*****@@@@@@%%@@%.    *@@@@@@@@%
 %@@@@@@@@@+     :+#%%#+:     #@@#+#%%#+-     +@@@@@@@@@%
 %@@@@@@@@@@#:              -%@@*           :#@@@@@@@@@@%
 %@@@@@@@@@@@@%+-.      .-+%@@@%-:      .-+%@@@@@@@@@@@@%
 %@@@@@@@@@@@@@@@@@%%%@@@@@@@@@@@@@@%%%@@@@@@@@@@@@@@@@@%
 %@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@%

   ____   _  _____ ____ _   _ _____ _____  __  ___ ___  
  |  _ \ / \|_   _/ ___| | | |  ___/ _ \ \/ / |_ _/ _ \ 
  | |_) / _ \ | || |   | |_| | |_ | | | \  /   | | | | |
  |  __/ ___ \| || |___|  _  |  _|| |_| /  \ _ | | |_| |
  |_| /_/   \_\_| \____|_| |_|_|   \___/_/\_(_)___\___/ 
                                                       
                              
'''

    print(banner)


def print_usage_str_and_exit_on_error():
    """ wrapper for print_usage_str() that also activates sys.exit(8)
    """
    print_usage_str()
    sys.exit(8)


def print_usage_str():
    """ prints help text to STDOUT
    """
    print(f'\n-=-------------------- HELP --------------------=-\n')

    name_str = f'\n{sys.argv[0]}'

    description_str = '\ncreates a CSV in the form of \n' + \
                      ' [PROJECT_NAME], [BUILD_TYPE], [BUILD_FILE_PATH]\n' + \
                      ' to be read by script "engage.py".'

    syntax_str = f'\n{name_str} [PATH_TO_PROJECT_REPOSITORIES] [OUTPUT_FILE_NAME]'

    usage_str = f'NAME: {name_str}' \
                f'\n\nDESCRIPTION: {description_str}' \
                f'\n\nUSAGE: {syntax_str}\n'

    print(usage_str)
    print(f'\n-=-------------------- **** --------------------=-\n')


if __name__ == '__main__':
    print_banner()
    if len(sys.argv) != 3:
        LOG.error('missing required arguments!')
        print_usage_str_and_exit_on_error()

    search_dir = sys.argv[1]
    output_filename = sys.argv[2]
    main(search_dir, output_filename)
