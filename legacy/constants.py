# keeping the code DRY
# (c) 2022 secpatch.io

from handlers import maven_handler, gradle_handler, npm_handler


# dict keys
PROJECT_NAME_KEY = 'project_name'
BUILD_FILE_NAME_KEY = 'build_file_name'
BUILD_FILE_PATH_KEY = 'build_file_path'
BUILD_FILE_HANDLER_KEY = 'build_file_handler'
BUILD_TYPE_KEY = "build_type"
DEPGRAPH_KEY = "depgraph"
OSS_REPORT_KEY = "oss_report"
MAVEN_KEY = 'maven'
GRADLE_KEY = 'gradle'
NPM_KEY = 'npm'

# expected build file names
MAVEN_BUILD_FILE = "pom.xml"
GRADLE_BUILD_FILE = "build.gradle"
NPM_BUILD_FILE = "package.json"

# pairs build system name with everything needed to make the magic happen
BUILD_TYPE_DICT = {
        MAVEN_KEY: {
            BUILD_FILE_NAME_KEY: MAVEN_BUILD_FILE,
            BUILD_FILE_HANDLER_KEY: maven_handler
        },
        GRADLE_KEY: {
            BUILD_FILE_NAME_KEY: GRADLE_BUILD_FILE,
            BUILD_FILE_HANDLER_KEY: gradle_handler
        },
        NPM_KEY: {
            BUILD_FILE_NAME_KEY: NPM_BUILD_FILE,
            BUILD_FILE_HANDLER_KEY: npm_handler
        }
}

# used by `generate_csv` to pair build files with the appropriate
# build system name
REVERSE_BUILD_TYPE_DICT = {
    MAVEN_BUILD_FILE: MAVEN_KEY,
    GRADLE_BUILD_FILE: GRADLE_KEY,
    NPM_BUILD_FILE: NPM_KEY,
}
