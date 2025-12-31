# handlers for invoking terminal commands to generate depgraph and OSS data
# (c) 2022 patchfox.io


import os
import sys
import subprocess
import logging as LOG

NPM_DEPGRAPH_FILE_NAME = "npm_depgraph.txt"
MAVEN_DEPGRAPH_FILE_NAME = "maven_depgraph.txt"
GRADLE_DEPGRAPH_FILE_NAME = "gradle_depgraph.txt"
GIT_BLAME_FILE_NAME = "build_git_blame.txt"


def maven_handler(project_name, build_file_path, out_dir):
    """
    activates maven dependency:tree plugin and pipes output to appropriate
    tmp file
    """
    maven_output_filepath = \
        os.path.join(out_dir, project_name, MAVEN_DEPGRAPH_FILE_NAME)

    LOG.info(f'activating maven for {project_name} at {build_file_path}')
    LOG.info(f'will write results to: {maven_output_filepath}')
    args = [
        "mvn",
        "-f",
        build_file_path,
        "org.apache.maven.plugins:maven-dependency-plugin:3.4.0:tree",
        "-Dverbose=true",
        f'-DoutputFile={maven_output_filepath}'
    ]
    subprocess_runner(args)

    create_git_blame_file(project_name, build_file_path, out_dir)

    LOG.info(f'clearing maven cache')
    args = [
        "mvn",
        "-f",
        build_file_path,
        "dependency:purge-local-repository"
    ]
    subprocess_runner(args)


def gradle_handler(project_name, build_file_path, out_dir):
    """
    activates gradle dependencies plugin and pipes output to appropriate
    tmp file
    """
    build_file_dirname = os.path.dirname(build_file_path)
    output_subdir = os.path.join(out_dir, project_name)

    LOG.info(f'activating gradle for {project_name} at {build_file_path}')

    # check to see if there is a gradle wrapper file we should be using
    gradle_wrapper_filepath = os.path.join(build_file_dirname, "gradlew")
    cmd = gradle_wrapper_filepath \
        if os.path.exists(gradle_wrapper_filepath) \
        else "gradle"

    args = [
        cmd,
        "-b",
        build_file_path,
        "dependencies"
    ]

    r = subprocess_runner(args)
    depgraph_data = r.stdout.decode('utf-8')

    write_depgraph_data_to_file(depgraph_data, output_subdir, GRADLE_DEPGRAPH_FILE_NAME)

    create_git_blame_file(project_name, build_file_path, out_dir)

    LOG.info(f'clearing gradle cache')
    args = [
        cmd,
        "cleanBuildCache"
    ]
    subprocess_runner(args)


def npm_handler(project_name, build_file_path, out_dir):
    """
    activates gradle dependencies plugin and pipes output to appropriate
    tmp file
    """
    build_file_dir = os.path.dirname(build_file_path)
    old_dir = os.getcwd()
    os.chdir(build_file_dir)
    LOG.info(f"Installing npm dependencies for {project_name}")
    # npm doesn't have the ability to get the dependencies without installing
    args = [
        "npm",
        "install",
    ]
    _ = subprocess_runner(args)

    LOG.info(f"Collecting npm dependency graph for {project_name} at {build_file_path}")
    # now let's gather the dependencies
    args = [
        "npm",
        "ls",
        "--json",
        "--all",
    ]
    depgraph_data = subprocess_runner(args).stdout.decode('utf-8')
    os.chdir(old_dir)

    output_subdir = os.path.join(out_dir, project_name)
    write_depgraph_data_to_file(depgraph_data, output_subdir, NPM_DEPGRAPH_FILE_NAME)

    create_git_blame_file(project_name, build_file_path, out_dir)

    LOG.info(f'clearing npm cache')
    args = [
        "npm",
        "cache",
        "clean",
        "--force"
    ]
    subprocess_runner(args)


def write_depgraph_data_to_file(depgraph_data, dir_path, file_name):
    output_filepath = os.path.join(dir_path, file_name)
    LOG.info(f"writing results to {output_filepath}")
    os.makedirs(dir_path, exist_ok=True)
    with open(output_filepath, "w") as f:
        f.write(depgraph_data)


def create_git_blame_file(repo_name, build_file_path, out_dir, hash=""):
    """
    Processes the results of `git blame` and writes them to a known file
    """
    build_file_dirname = os.path.dirname(build_file_path)

    git_blame_output_file_path = \
        os.path.join(out_dir, GIT_BLAME_FILE_NAME)

    git_dir_file_path = os.path.join(build_file_dirname, ".git")

    if (hash):
        LOG.info(f'checking out commit {hash}')
        args = [
            "git",
            "-C",
            build_file_dirname,
            "checkout",
            hash
        ]
        r = subprocess_runner(args)


    LOG.info(f'pulling git blame for {repo_name} at {git_dir_file_path}')
    LOG.info(f'will write results to: {git_blame_output_file_path}')
    args = [
        "git",
        "-C",
        build_file_dirname, 
        "blame",
        build_file_path
    ]
    r = subprocess_runner(args)
    git_blame = r.stdout.decode("utf-8")

    with open(git_blame_output_file_path, 'w') as f:
        f.writelines(git_blame)

    # don't leave things in a detatched head state 
    args = [
        "git",
        "-C",
        os.path.dirname(build_file_path),
        "checkout",
        "-"
    ]
    LOG.info("returing repo to latest commit")
    subprocess_runner(args)
    
    # get branch name
    LOG.info(f'build_file_dirname is: {build_file_dirname}')
    args = [
        "git",
        "-C",
        build_file_dirname,
        "branch",
        "--show-current"
    ]
    r = subprocess_runner(args)
    branch = r.stdout.decode("utf-8").rstrip()   
    LOG.info(f'branch is: {branch}')
    return branch


def dependency_check_handler(project_name, build_file_path, out_dir):
    """ activates OWASP Dependency Check and pipes output to appropriate
    tmp file
    """
    build_file_dirname = os.path.dirname(build_file_path)
    output_subdir = os.path.join(out_dir, project_name)
    LOG.info(
        f'activating OWASP dependency check for '
        f'{project_name} at {build_file_dirname}'
    )
    output_filepath = \
        os.path.join(output_subdir, "dependency_check_report.json")

    LOG.info(f'will write results to: {output_filepath}')
    LOG.info(f'this might take a minute...')

    args = [
        "dependency-check",
        "--scan",
        build_file_dirname,
        "--format JSON",
        f'--project {project_name}',
        f'--out {output_subdir}',
        '--nvdApiKey 46dc335e-8da1-4e20-8f47-e5a5c8d603c9'
    ]

    # using shell=True because invoking a shell script doesn't seem to work w/o it.
    # converting the args list to a str because the docs recommend it when shell=True
    # https://docs.python.org/3/library/subprocess.html#subprocess.Popen
    args_str = ' '.join(args)
    subprocess_runner(args_str, shell_flag=True)


def syft_handler(project_name, build_file_path, out_dir):
    """ activates syft and pipes output to appropriate tmp file 
    """
    build_file_dirname = os.path.dirname(build_file_path)
    #output_subdir = os.path.join(out_dir, project_name)

    if not os.path.isdir(out_dir):
        os.mkdir(out_dir)

    LOG.info(
        f'activating Syft check for '
        f'{project_name} at {build_file_dirname}'
    )
    output_filepath = \
        os.path.join(out_dir, "syft_sbom.json")

    LOG.info(f'will write results to: {output_filepath}')

    args = [
        "/usr/local/bin/syft",
        "-o",
        "json",
        build_file_dirname,
    ]

    args_str = ' '.join(args)
    LOG.info(f'args_str is: {args_str}')
    r = subprocess_runner(args_str, shell_flag=True)
    syft_out = r.stdout.decode("utf-8")

    with open(output_filepath, 'w') as f:
        f.writelines(syft_out)


def grype_handler(project_name, build_file_path, out_dir):
    """ given the syft sbom file, activates grype to produce an oss report 
    """
    build_file_dirname = os.path.dirname(build_file_path)
    output_subdir = os.path.join(out_dir, project_name)
    LOG.info(
        f'activating Syft check for '
        f'{project_name} at {build_file_dirname}'
    )
    sbom_filepath = \
        os.path.join(output_subdir, "syft_sbom.json")
    
    output_filepath = \
        os.path.join(output_subdir, "grype_oss.json")

    LOG.info(f'will write results to: {output_filepath}')

    args = [
        "grype",
        "-o",
        "json",
        "sbom:" + sbom_filepath,
    ]

    args_str = ' '.join(args)
    r = subprocess_runner(args_str, shell_flag=True)
    grype_out = r.stdout.decode("utf-8")

    with open(output_filepath, 'w') as f:
        f.writelines(grype_out)


def subprocess_runner(args, shell_flag=False):
    """ target for handlers to pipe arguments to execute analysis tasks in a
    DRY manner
    """
    r = subprocess.run(
        args,
        check=True,
        capture_output=True,
        shell=shell_flag
    )
    return r
