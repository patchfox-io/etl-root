import logging
import sys

import click
from dateutil import parser
from github import Auth, Commit, Github, GithubException

from .api import PatchfoxApi
from .etl import process_repo, purl_to_cache_key
from .repo import GitRepo, GithubRepo, GitlabRepo
from .syft import Syft


@click.command()
@click.option("--debug", is_flag=True)
@click.option("--patchfox-organization", envvar="PATCHFOX_ORGANIZATION")
@click.option("--patchfox-api-token", envvar="PATCHFOX_API_TOKEN")
@click.option("--patchfox-get-api-baseurl", envvar="PATCHFOX_GET_API_BASEURL")
@click.option("--patchfox-post-api-baseurl", envvar="PATCHFOX_POST_API_BASEURL")
@click.option("--github-api-token")
@click.option("--git-clone-path")
@click.option("--recurse/--no-recurse", default=False)
@click.option("--syft", "path_to_syft", default="/usr/local/bin/syft")
@click.argument("orgs", nargs=-1)
def bulk(github_api_token, git_clone_path, recurse, path_to_syft, orgs, debug, **kwargs):
    logging.basicConfig(
        format="[%(asctime)s] [%(funcName)s] [%(levelname)s] %(message)s",
        level=logging.DEBUG if debug else logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
        encoding="utf-8",
        stream=sys.stdout
    )

    patchfox_kwargs = {k: v for (k, v) in kwargs.items() if k.startswith("patchfox_")}

    Syft.PATH_TO_SYFT = path_to_syft

    github = Github(auth=Auth.Token(github_api_token))

    repos = {}
    for org in orgs:
        if "/" in org:
            (org, _, repo) = org.partition("/")
        else:
            repo = None

        if org not in repos:
            repos[org] = []

        if repo:
            repos[org].append(repo)

    pfapi = PatchfoxApi(patchfox_datasource=None, **patchfox_kwargs)

    for org in repos:
        github_org = github.get_organization(org)
        for github_repo in github_org.get_repos(type="public"):
            if github_repo.archived:
                continue
            if repos[org] and github_repo.name not in repos[org]:
                continue
            
            try:
                github_repo.get_license()
            except GithubException as e:
                if e.status != 404:
                    print(f"Error processing {github_repo.name} ({github_repo.url}): {e.message}")
                    continue
            
            print(f"Processing {github_repo.name} ({github_repo.url})")
        
            if (github_repo.size == 0):
                continue

            latest_cache = {}
            pfapi.datasource = github_repo.name

            with GitRepo.clone_from(github_repo.clone_url, clone_into=git_clone_path, head=github_repo.default_branch) as repo:
                # if repo._old_head is not None:
                #     if repo._old_head.hexsha == repo.HEAD.hexsha:
                #         print("No updates for repo, skipping")
                #         continue

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
    bulk(auto_envvar_prefix="PATCHFOX")