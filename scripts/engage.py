#!/usr/bin/env python3

# ETL runner script to feed java dependency graph data into patchfox.io
# (c) 2022 patchfox.io
# https://youtu.be/jiyDUfdRL10?t=10s


import sys
import csv
import os
import tempfile
import shutil
import json
import requests
#import tzdata

from urllib.parse import urlparse, urljoin 
from subprocess import CalledProcessError
from time import time
from zoneinfo import ZoneInfo
from dateutil import parser
from datetime import datetime
from zoneinfo import ZoneInfo
from handlers import *
from constants import *

import logging as LOG

LOG.basicConfig(
    format='[%(asctime)s] [%(funcName)s] [%(levelname)s] %(message)s',
    level=LOG.INFO,
    datefmt='%Y-%m-%d %H:%M:%S',
    encoding='utf-8'
)

POST_DATA_ENDPOINT = '/api/v1/input/git'

GET_DATASOURCE_ENDPOINT = "/api/v1/datasource"


def send_data_payload(out_dir, domain, api_token, api_url):
    """
    """

    # expectation is "out_dir" points to /{sys_temp}/{timestamp}
    #   
    # we enumerate and expect 
    #   /{sys_temp}/{timestamp}/{DATASOURCE_NAME}/{COMMIT_HASH}/{[syft_sbom.json, metadata.json, build_git_blame.txt]}
    #
    # if there aren't three files in that subdir, then something went wrong with git. for now we'll skip these payloads
    for root, dirs, files in os.walk(out_dir):
        LOG.debug(f'root is: {root}')
        LOG.debug(f'dirs is: {dirs}')
        LOG.debug(f'files is: {files}')

        if len(files) == 0:
            continue

        expected_files = ["syft_sbom.json", "metadata.json", "build_git_blame.txt"]
        if sorted(files) != sorted(expected_files):
            LOG.warning(f'folder {root} had contents {files} but expected {expected_files}')
            LOG.info("not sending malformed event to PatchFox")
            continue

        metadata_filepath = os.path.join(root, "metadata.json")
        with open (metadata_filepath, "r") as f:
            metadata = json.loads(f.read())
            datasource_name = metadata["datasource"]
            commit_hash = metadata["commitHash"]
            commit_datetime = metadata["commitDatetime"]
            commit_branch = metadata["commitBranch"]
            packed_datasource_name = datasource_name + "::" + commit_branch
            data_type = metadata["dataType"]
            datasource_subpath = f'commitHash={commit_hash}&commitDatetime={commit_datetime}'
            event_datetime = metadata["eventDatetime"]
            datasource_purl = f'pkg:generic/{domain}/{packed_datasource_name}@{data_type}?{datasource_subpath}'
            LOG.info(f'datasource_purl is: {datasource_purl}')

        # bundle serialized results
        zipfile_name = f'patchfox_data_{domain}_{event_datetime}'
        zipfile_path = os.path.join(out_dir, zipfile_name)
        LOG.info(f'bundling results to {zipfile_path}.zip')
        shutil.make_archive(zipfile_path, 'zip', os.path.join(out_dir, datasource_name))

        files = { "eventFileData": open(zipfile_path + '.zip', 'rb') }
        data = {
            "datasourceEvent": datasource_purl,
        }

        headers = { 'Authorization': f'Bearer {api_token}' }
        parsed_api_url = urlparse(api_url)
        if parsed_api_url.scheme == 'http' and parsed_api_url.hostname.split('.')[-1:] == ['localhost']:
            LOG.info("removing api_token from header due to data-service being local")
            del headers['Authorization']

        LOG.info(f'sending event to PatchFox at: {api_url}')
        r = requests.post(api_url, files=files, params=data, headers=headers)

        if not r.ok:
            LOG.warning(f'response code was not ok: {r.status_code}')
            LOG.warning(f'response json was: {r.json()}')
            

def get_data_payload(repos_csv, api_token, api_url, datasource):
    """ 
    """
    # parse and validate caller supplied csv
    build_files_dict = get_build_files_dict(repos_csv)

    # do this after in case parsing 'projects_csv' fails
    time_str = str(int(time()))
    out_top_dir = os.path.join(tempfile.gettempdir(), time_str)

    os.mkdir(out_top_dir)
    LOG.info(f'using tmp directory {out_top_dir}')

    # see if the datasource is known to PF. if it isn't we need to seed the pipeline with historical data
    headers = { 'Authorization': f'Bearer {api_token}' }
    parsed_api_url = urlparse(api_url)
    if parsed_api_url.scheme == 'http' and parsed_api_url.hostname.split('.')[-1:] == ['localhost']:
        LOG.info("removing api_token from header due to data-service being local")
        del headers['Authorization']
        
    r_json = requests.get(api_url, headers=headers).json()
    LOG.info(f'response from data service is: {r_json}')
    with_history = \
        False if \
            [
                e['packedName'] 
                for e 
                in r_json['data']['datasources']
                if e['packedName'] == datasource
            ] \
        else True

    # get depgraph and OSS data for every project in build_files_dict
    for build_type, repos in build_files_dict.items():
        for repo_dict in repos:
            repo_name = repo_dict[REPO_NAME_KEY]
            build_file_path = repo_dict[BUILD_FILE_PATH_KEY]

            data_type = BUILD_TYPE_TO_PURL_TYPE[build_type];

            # presently this is hard wired to only generate git annotated build files
            build_handler = BUILD_TYPE_DICT[build_type][BUILD_FILE_HANDLER_KEY]
            hashes_and_datetimes = get_hashes_and_datetimes(build_file_path, with_history)

            for hash_and_datetime in hashes_and_datetimes:
                out_dir = os.path.join(out_top_dir, repo_name, hash_and_datetime[0])
                os.makedirs(out_dir)
                LOG.info(f'out_dir is: {out_dir}')

                try:
                    branch = build_handler(repo_name, build_file_path, out_dir, hash_and_datetime[0])
                    metadata = {
                        "datasource": repo_name,
                        "dataType": data_type,
                        "commitHash": hash_and_datetime[0],
                        "commitDatetime": hash_and_datetime[1].isoformat(),
                        "commitBranch": branch,
                        "eventDatetime": datetime.now(ZoneInfo("Zulu")).replace(microsecond=0).isoformat()
                    }
                    
                    metadata_out = os.path.join(out_dir, "metadata.json")
                    LOG.info(f'writing {metadata} to {metadata_out}')
                    with open(metadata_out, "w") as f: 
                        f.write(json.dumps(metadata))

                except Exception as e:
                    LOG.error(f'something went wrong! {e}')
                    if type(e) == CalledProcessError:
                        LOG.error(f'** PROCESS OUTPUT IS AS FOLLOWS **')
                        LOG.error(f'\n\n{e.stderr}\n')

                try:
                    syft_handler(repo_name, build_file_path, out_dir)
                except Exception as e:
                    LOG.error(f'something went wrong! {e}')
                    if type(e) == CalledProcessError:
                        LOG.error(f'** PROCESS OUTPUT IS AS FOLLOWS **')
                        LOG.error(f'\n\n{e.stderr}\n')

    # see you space cowboy...
    LOG.info('done!')
    return out_top_dir


def get_hashes_and_datetimes(build_file_path, with_history):
    build_file_dirname = os.path.dirname(build_file_path)
    
    args = [
        "/usr/bin/git",
        "-C",
        build_file_dirname,
        "log",
        "-1",
        '--pretty=format:"%H|%ci"',
         build_file_path
    ]

    # remove "-1" argument limiting scope of result from git to only the latest record 
    if with_history:
        del(args[4])
    
    r = subprocess_runner(args)
    history = r.stdout.decode("utf-8")
     
    # converts string comprosed of '\n' delimited set of records that look like this this:
    #     d6c957ac9f8c342b0bfd3e7cbc9b142b5402654e|2022-12-23 14:55:18 -0700
    # into a list of records that look like this:
    #     [
    #       'd6c957ac9f8c342b0bfd3e7cbc9b142b5402654e', 
    #       datetime.datetime(2022, 12, 23, 21, 55, 18, tzinfo=zoneinfo.ZoneInfo(key='Zulu'))
    #     ]
    # 
    # note that we're ensuring all datetime is converted to Zulu time REGARDLESS of local system time. 
    # 
    # start from the middle and work your way out 
    hashes_and_datetimes = list(
        # (4) convert the datetime obj time zone to zulu (UTC) time
        map(lambda e: [e[0], e[1].astimezone(ZoneInfo("Zulu"))], map(
                # (3) parse the datetime str into a python datetime obj. the list splice is because of an errant '"'   
                # chars at the begining of the hash and  the end of the datetime str
                lambda e: [e[0][1:], parser.parse(e[1][:-1])], map(
                    # (2) split each record into a list of two elements, hash and datetime str
                    lambda e: e.split("|"), map(
                        # (1) convert the '\n' delimited string into a list of records
                        lambda e: e, history.splitlines()
                    )
                )
            )
        )
    )
    
    LOG.debug(hashes_and_datetimes)
    return hashes_and_datetimes


def delete_working_temp_dir(out_top_dir):
    # this should NEVER be an issue but double check things are kosher before
    # we remove anything from the client filesystem
    if not out_top_dir.startswith(tempfile.gettempdir()):
        LOG.error(f'{out_top_dir} not located in system temp folder '
                  f'{tempfile.gettempdir()}')
        LOG.error(f'NOT REMOVING FILES LOCATED OUTSIDE SYSTEM TMP FOLDER!')
        LOG.error(f'** EXITING ON ERROR **')
        sys.exit(8)
    else:
        LOG.info(f'cleaning up temp files at: {out_top_dir}')
        shutil.rmtree(out_top_dir)


def get_build_files_dict(repos_csv):
    """ translates the caller supplied build filename into a validated set of 
    build file paths 
    """
    LOG.info(f'parsing CSV file: {repos_csv}')
    
    # set up a container to be populated with contents of caller supplied 
    # CSV file 
    build_file_dict = {}
    for build_type in BUILD_TYPE_DICT.keys():
        build_file_dict[build_type] = []

    # ensure CSV file actually exists 
    if not os.path.isfile(repos_csv):
        LOG.error(f'file {repos_csv} not found')
        print_usage_str_and_exit_on_error()

    # parse CSV 
    with open(repos_csv, newline='') as f:
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
                repo_name = row[0]
                build_type = row[1].lower()
                build_file_path = row[2]
                build_filename = os.path.basename(build_file_path)
                
                # make sure the build file looks right for the build system 
                # the caller specified 
                expected_filename = \
                    BUILD_TYPE_DICT[build_type][BUILD_FILE_NAME_KEY]

                if build_filename.lower() != expected_filename.lower():

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
                    f'[project_name]: {repo_name}  '
                    f'[build_type]: {build_type}  '
                    f'[build_file_path]: {build_file_path}'
                )
                build_file_dict[build_type].append({
                    REPO_NAME_KEY: repo_name,
                    BUILD_FILE_PATH_KEY: build_file_path
                })
                
        # if we fall into this it's because the caller supplied an empty file.
        # we have to do it this way because python is a butt and doesn't have 
        # a has_next() method for iterators because, you know,  iT's mOre 
        # pYTHoNiC tHiS wAy  
        if rows == 0:
            LOG.error(f'{repos_csv} is empty')
            log_malformed_csv_and_exit_on_error()
        else:
            LOG.info(f'{repos_csv} successfully parsed!')
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

    syntax_str = f'\n{name_str} [REPOS_CSV] [ORGANIZATION] [API_TOKEN] [API_BASE_URL]' 
    usage_str = f'NAME: {name_str}' \
                f'\n\nDESCRIPTION: {description_str}' \
                f'\n\nUSAGE: {syntax_str}\n' 
    
    print(usage_str)
    print(f'\n-=-------------------- **** --------------------=-\n')


def validate_api_url(api_url):
    parsed_api_url = urlparse(api_url)
    valid = True
    if parsed_api_url.hostname.split('.')[-1:] == ['localhost']:
        LOG.info(f'allowing {api_url} because host is local')
        return valid
    elif parsed_api_url.scheme != 'https':
        valid = False
        LOG.warning(f'rejecting {api_url} because scheme must be https')
    elif parsed_api_url.hostname.split('.')[-2:] != ['patchfox', 'io']:
        valid = False
        LOG.warning(f'rejecting {api_url} because events must be sent to PatchFox servers only')

    return valid


if __name__ == '__main__':
    print_banner()
    if len(sys.argv) < 6:
        LOG.error('missing required arguments!')
        print_usage_str_and_exit_on_error()

    repos_csv = sys.argv[1]
    organization = sys.argv[2]
    api_token = sys.argv[3]
    
    post_api_base_url = sys.argv[4]
    get_api_base_url = sys.argv[5]
    post_data_url = urljoin(post_api_base_url, POST_DATA_ENDPOINT)
    get_metadata_url = urljoin(get_api_base_url, GET_DATASOURCE_ENDPOINT)
    if not validate_api_url(post_api_base_url) \
            or not validate_api_url(get_api_base_url) \
            or not validate_api_url(post_data_url) \
            or not validate_api_url(get_metadata_url):
        LOG.error(f'argument {post_api_base_url} or {get_api_base_url} invalid or produces invalid argument - exiting')
        exit(8)

    datasource = sys.argv[6]

    # datapayload is serialized to disk at path "out_dir"
    out_dir = get_data_payload(repos_csv, api_token, get_metadata_url, datasource)
    
    # parse contents of "out_dir" and send event to PatchFox
    send_data_payload(out_dir, organization, api_token, post_data_url)

    # clean up after ourselves 
    delete_working_temp_dir(out_dir)

