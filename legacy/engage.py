#!/usr/bin/env python3

# ETL runner script to feed java dependency graph data into patchfox.io
# (c) 2022 patchfox.io
# https://youtu.be/jiyDUfdRL10?t=10s


import sys
import csv
import os
import tempfile
import shutil

from subprocess import CalledProcessError
from time import time
from handlers import *
from constants import *

import logging as LOG

LOG.basicConfig(
    format='[%(asctime)s] [%(funcName)s] [%(levelname)s] %(message)s',
    level=LOG.INFO,
    datefmt='%Y-%m-%d %H:%M:%S',
    encoding='utf-8'
)


def main(projects_csv, org_name):
    """ runs the thing 
    """

    # parse and validate caller supplied csv
    build_files_dict = get_build_files_dict(projects_csv)

    # do this after in case parsing 'projects_csv' fails
    time_str = str(int(time()))
    out_top_dir = os.path.join(tempfile.gettempdir(), time_str)
    out_org_sub_dir = os.path.join(out_top_dir, org_name)
    # depgraph_out_dir = os.path.join(out_org_sub_dir, 'depgraphs')
    # reports_out_dir = os.path.join(out_org_sub_dir, 'reports')
    os.mkdir(out_top_dir)
    os.mkdir(out_org_sub_dir)
    LOG.info(f'using tmp directory {out_top_dir}')

    # get depgraph and OSS data for every project in build_files_dict
    for build_type, projects in build_files_dict.items():
        build_handler = BUILD_TYPE_DICT[build_type][BUILD_FILE_HANDLER_KEY]
        for project_dict in projects:
            project_name = project_dict[PROJECT_NAME_KEY]
            build_file_path = project_dict[BUILD_FILE_PATH_KEY]

            # try:
            #     build_handler(project_name, build_file_path, out_org_sub_dir)
            # except Exception as e:
            #     LOG.error(f'something went wrong! {e}')
            #     if type(e) == CalledProcessError:
            #         LOG.error(f'** PROCESS OUTPUT IS AS FOLLOWS **')
            #         LOG.error(f'\n\n{e.output.decode()}\n')

            try:
                dependency_check_handler(project_name, build_file_path, out_org_sub_dir)
            except Exception as e:
                LOG.error(f'something went wrong! {e}')
                if type(e) == CalledProcessError:
                    LOG.error(f'** PROCESS OUTPUT IS AS FOLLOWS **')
                    LOG.error(f'\n\n{e.output.decode()}\n')

            try:
                syft_handler(project_name, build_file_path, out_org_sub_dir)
                grype_handler(project_name, build_file_path, out_org_sub_dir)
            except Exception as e:
                LOG.error(f'something went wrong! {e}')
                if type(e) == CalledProcessError:
                    LOG.error(f'** PROCESS OUTPUT IS AS FOLLOWS **')
                    LOG.error(f'\n\n{e.output.decode()}\n')
                # try:
                #     # remove the sub directory for this project so we don't sent malformed data to wintermute
                #     rm_dir = os.path.join(out_org_sub_dir, project_name)
                #     LOG.info(f'removing directory {rm_dir}')
                #     #shutil.rmtree(rm_dir)
                # except FileNotFoundError as fe:
                #     LOG.info(f'directory {rm_dir} not found and thus not removed')

    # bundle serialized results
    zipfile_name = f'{org_name}_patchfox_raw_bundle_{time_str}'
    #zipfile_filepath = os.path.join(out_top_dir, zipfile_name)
    LOG.info(f'bundling results to {zipfile_name}')
    shutil.make_archive(zipfile_name, 'zip', out_top_dir)
    # send results to patchfox for analysis
    #LOG.warning(f'*** TODO - SEND TO PATCHFOX ***')

    # clean up
    # this should NEVER be an issue but double check things are kosher before
    # we remove anything from the client filesystem
    if not out_top_dir.startswith(tempfile.gettempdir()):
        LOG.error(f'{out_top_dir} not located in system temp folder '
                  f'{tempfile.gettempdir()}')
        LOG.error(f'NOT REMOVING FILES LOCATED OUTSIDE SYSTEM TMP FOLDER!')
        LOG.error(f'** EXITING ON ERROR **')
        sys.exit(8)
    else:
        #LOG.warning(f'*** TODO - REACTIVATE CLEANUP CODE ***')
        LOG.info(f'cleaning up temp files at: {out_top_dir}')
        shutil.rmtree(out_top_dir)

    # see you space cowboy...
    LOG.info('done!')


def get_build_files_dict(projects_csv):
    """ translates the caller supplied build filename into a validated set of 
    build file paths 
    """
    LOG.info(f'parsing CSV file: {projects_csv}')
    
    # set up a container to be populated with contents of caller supplied 
    # CSV file 
    build_file_dict = {}
    for build_type in BUILD_TYPE_DICT.keys():
        build_file_dict[build_type] = []

    # ensure CSV file actually exists 
    if not os.path.isfile(projects_csv):
        LOG.error(f'file {projects_csv} not found')
        print_usage_str_and_exit_on_error()

    # parse CSV 
    with open(projects_csv, newline='') as f:
        # reader is an iterator 
        reader = csv.reader(f)
        rows = 0
        for row in reader:
            rows += 1
            # validate record size 
            if len(row) != 3:
                log_malformed_csv_and_exit_on_error()
            # validate specified build type is recognized
            elif row[1].lower() not in BUILD_TYPE_DICT.keys():
                LOG.error(f'{row[1]} not a recognized build type')
                log_malformed_csv_and_exit_on_error()
            # validate specified file exists on file system
            elif not os.path.isfile(row[2]):
                LOG.error(f'file {row[2]} not found')
                log_malformed_csv_and_exit_on_error()
            # add record to container 
            else:
                project_name = row[0]
                build_type = row[1].lower()
                build_file_path = row[2]
                build_filename = os.path.basename(build_file_path)
                
                # make sure the build file looks right for the build system 
                # the caller specified 
                expected_filename = \
                    BUILD_TYPE_DICT[build_type][BUILD_FILE_NAME_KEY]

                if build_filename.lower() != expected_filename:

                    LOG.error(
                        f'{build_filename} not recognized as valid for '
                        f'build type: {build_type}. '
                        f'Expected "{expected_filename}"'
                    )
                    log_malformed_csv_and_exit_on_error()

                # things look good so add the record to the build_file_dict
                # we'll return to the caller 
                LOG.debug(
                    f'adding record for processing --> '
                    f'[project_name]: {project_name}  '
                    f'[build_type]: {build_type}  '
                    f'[build_file_path]: {build_file_path}'
                )
                build_file_dict[build_type].append({
                    PROJECT_NAME_KEY: project_name,
                    BUILD_FILE_PATH_KEY: build_file_path
                })
                
        # if we fall into this it's because the caller supplied an empty file.
        # we have to do it this way because python is a butt and doesn't have 
        # a has_next() method for iterators because, you know,  iT's mOre 
        # pYTHoNiC tHiS wAy  
        if rows == 0:
            LOG.error(f'{projects_csv} is empty')
            log_malformed_csv_and_exit_on_error()
        else:
            LOG.info(f'{projects_csv} successfully parsed!')
            return build_file_dict


def print_banner():
    """ show some style...
    """
    banner = """
                        ..                    ...                                               
                 .,coxkO0OOxdl;.        .;ldkOO0OOxoc,.                                         
              .;d0NWMMMMMMMMMMXc.    .ckXWMMMMMMMMMMMN0d;.                                      
            .;ONMMMMMMWNNNWWMXc.  .lkKWMMMMMMWNNNWMMMMMMNO:.                                    
           .oNMMMMWXxc;''',co;   'kWMMMMMW0d:,''';cxXWMMMMNo.                                   
          .oNMMMMNd'             ;dxxxxxdc.         'dNMMMMNo.                                  
          ;KMMMMNo.  .',,'..                 .',,'.  .oNMMMMK;                                  
          cNMMMMK;  .,cccc:;;;;;;;;;;;;;;;;;;:cccc,.  ,KMMMMNc                                  
          cXMMMMX:   '::c:,.................',:c::'   :XMMMMXc                                  
          .OMMMMWO,   ....    .',,',,,.       ....   ,OWMMMMO.                                  
           ;0WMMMMKd,.     .'lONNNNNNKc   ...     .,oKWMMMW0;                                   
            ,kWMMMMMN0kdodxOXWMMMMW0x:.  .xK0xdodk0NMMMMMWk,                                    
             .:kNMMMMMMMMMMMMMMMW0l.    ,kWMMMMMMMMMMMMNk:.                                     
               .,lx0XWWMMMMWNKko;.     .:kKNWWMMMWWX0xl,.                                       
                   ..,::c::;'.            .';:cc::,.. 
                   

██████╗  █████╗ ████████╗ ██████╗██╗  ██╗███████╗ ██████╗ ██╗  ██╗   ██╗ ██████╗ 
██╔══██╗██╔══██╗╚══██╔══╝██╔════╝██║  ██║██╔════╝██╔═══██╗╚██╗██╔╝   ██║██╔═══██╗
██████╔╝███████║   ██║   ██║     ███████║█████╗  ██║   ██║ ╚███╔╝    ██║██║   ██║
██╔═══╝ ██╔══██║   ██║   ██║     ██╔══██║██╔══╝  ██║   ██║ ██╔██╗    ██║██║   ██║
██║     ██║  ██║   ██║   ╚██████╗██║  ██║██║     ╚██████╔╝██╔╝ ██╗██╗██║╚██████╔╝
╚═╝     ╚═╝  ╚═╝   ╚═╝    ╚═════╝╚═╝  ╚═╝╚═╝      ╚═════╝ ╚═╝  ╚═╝╚═╝╚═╝ ╚═════╝ 
                                                                                 

                                                                                           
    """

    print(banner)


def log_malformed_csv_and_exit_on_error():
    """ common exit handler for CSV validation
    """
    malformed_csv_str = 'CSV file is malformed! ' \
                        'CSV row format is: ' \
                        '[PROJECT_NAME], [BUILD_TYPE], [BUILD_FILE_PATH]'

    LOG.error(malformed_csv_str)
    sys.exit(8)


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

    description_str = '\nparses csv file containing list of maven and/or\n' + \
                      ' gradle project locations, activates the build\n' + \
                      ' system to produce dependency graphs for the\n' + \
                      ' projects, captures git blame data for the build file,\n' + \
                      ' captures sbom and oss data for the project,\n' + \
                      ' and sends it to patchfox for analysis.'

    syntax_str = f'\n{name_str} [PROJECTS_CSV] [ORG_NAME] [SECPATCH_API_KEY]'

    usage_str = f'NAME: {name_str}' \
                f'\n\nDESCRIPTION: {description_str}' \
                f'\n\nUSAGE: {syntax_str}\n' 
    
    print(usage_str)
    print(f'\n-=-------------------- **** --------------------=-\n')


if __name__ == '__main__':
    print_banner()
    # TODO API key -- this should be != 4
    if len(sys.argv) != 3:
        LOG.error('missing required arguments!')
        print_usage_str_and_exit_on_error()

    projects_csv = sys.argv[1]
    org_name = sys.argv[2]
    main(projects_csv, org_name)
