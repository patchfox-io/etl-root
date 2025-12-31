import logging
import os
from typing import List

import click
from dateutil import parser
from packageurl import PackageURL

from .api import PatchfoxApi
from .etl import process_repo, purl_to_cache_key
from .repo import GitRepo, GithubRepo, GitlabRepo
from .syft import Syft


@click.command()
@click.option("--patchfox-organization", envvar="PATCHFOX_ORGANIZATION")
@click.option("--patchfox-datasource", envvar="PATCHFOX_DATASOURCE")
@click.option("--patchfox-api-token", envvar="PATCHFOX_API_TOKEN")
@click.option("--patchfox-get-api-baseurl", envvar="PATCHFOX_GET_API_BASEURL")
@click.option("--patchfox-post-api-baseurl", envvar="PATCHFOX_POST_API_BASEURL")
@click.option("--git", "repo_type", flag_value="git", default=True)
@click.option("--github", "repo_type", flag_value="github")
@click.option("--github-api-token")
@click.option("--gitlab", "repo_type", flag_value="gitlab")
@click.option("--gitlab-api-token")
@click.option("--gitlab-api-baseurl")
@click.option("--recurse/--no-recurse", default=False)
@click.option("--syft", "path_to_syft", default="/usr/local/bin/syft")
@click.argument("datapaths", nargs=-1)
def etl(repo_type, datapaths, recurse, path_to_syft, **kwargs):
    patchfox_kwargs = {k: v for (k, v) in kwargs.items() if k.startswith("patchfox_")}
    repo_kwargs = {k: v for (k, v) in kwargs.items() if k.startswith(f"{repo_type}_")}

    pfapi = PatchfoxApi(**patchfox_kwargs)
    Syft.PATH_TO_SYFT = path_to_syft

    repo_class = {
        "git": GitRepo,
        "github": GithubRepo,
        "gitlab": GitlabRepo
    }.get(repo_type)

    repos: List[GitRepo] = []
    for datapath in datapaths:
        if repo_type == "git" and os.path.isdir(datapath) and not os.path.exists(os.path.join(datapath, ".git")):
            # Assume every directory in each datapath is a git working dir
            for subdir in os.listdir(datapath):
                p = os.path.join(datapath, subdir)
                if not (os.path.isdir(p) and os.path.exists(os.path.join(p, ".git"))):
                    continue
                repos.append(os.path.join(datapath, subdir))
        else:
            repos.append(datapath)

    for repo_dir in repos:
        latest_cache = {}
        with repo_class(repo_dir, **repo_kwargs) as repo:
            for (package_url, etl_bundle) in process_repo(repo, pfapi.organization, recurse):
                latest = None

                cache_key = purl_to_cache_key(package_url)

                if cache_key not in latest_cache:
                    print(f"Need to update cache for {cache_key}")
                    latest = latest_cache[cache_key] = pfapi.get_latest_event(package_url)
                    if latest is None:
                        print("No events found for datasource, doing full history import")

                latest = latest_cache[cache_key]
                
                if latest:
                    latest_dt = parser.parse(latest["commitDatetime"])
                    if package_url.qualifiers["commithash"] == latest["commitHash"]:
                        print(f"Done processing at {package_url.qualifiers['commithash']}")
                        break
                    if latest_dt > etl_bundle.commitDatetime:
                        print(f"Skipping {package_url.qualifiers['commithash']}")
                        continue
                print(f"Sending commit {package_url.qualifiers['commithash']} to PatchFox")

                pfapi.send_event(etl_bundle, package_url)


if __name__ == "__main__":
    logging.basicConfig(
        format='[%(asctime)s] [%(funcName)s] [%(levelname)s] %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S',
        encoding='utf-8'
    )
    
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
    etl(auto_envvar_prefix="PATCHFOX")