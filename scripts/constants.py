# keeping the code DRY
# (c) 2022 secpatch.io

from handlers import maven_handler, gradle_handler, npm_handler, create_git_blame_file


# dict keys
REPO_NAME_KEY = 'repo_name'
BUILD_FILE_NAME_KEY = 'build_file_name'
BUILD_FILE_PATH_KEY = 'build_file_path'
BUILD_FILE_HANDLER_KEY = 'build_file_handler'
BUILD_TYPE_KEY = "build_type"
DEPGRAPH_KEY = "depgraph"
OSS_REPORT_KEY = "oss_report"

MAVEN_KEY = 'maven'
GRADLE_KEY = 'gradle'
NPM_KEY = 'npm'
PYTHON_REQUIREMENTS_KEY = 'python_requirements'
PYTHON_PIPENV_KEY = 'python_pipenv'
PHP_COMPOSER_KEY = "php_composer"
DOTNET_DEPS_KEY = "dotnet_deps"
RUBY_GEM_KEY = "ruby_gem"
GO_MOD_KEY = "go_mod"

# expected build file names
MAVEN_BUILD_FILE = "pom.xml"
GRADLE_BUILD_FILE = "build.gradle"
NPM_BUILD_FILE = "package.json"
PYTHON_BUILD_FILE_REQUIREMENTS = "requirements.txt"
PYTHON_BUILD_FILE_PIPENV = "Pipfile"
PHP_COMPOSER_BUILD_FILE = "composer.json"
DOTNET_BUILD_FILE = "deps.json"
RUBY_BUILD_FILE = "Gemfile"
GO_BUILD_FILE = "go.mod"

# maps build system to package index name as identified in purl types
# https://github.com/package-url/purl-spec/blob/master/PURL-TYPES.rst
BUILD_TYPE_TO_PURL_TYPE = {
    MAVEN_KEY: MAVEN_KEY,
    GRADLE_KEY: "maven",
    NPM_KEY: NPM_KEY,
    PYTHON_REQUIREMENTS_KEY: "pypi",
    PYTHON_PIPENV_KEY: "pypi",
    PHP_COMPOSER_KEY: "composer",
    DOTNET_DEPS_KEY: "nuget",
    RUBY_GEM_KEY: "gem",
    GO_MOD_KEY: "golang",
}


# pairs build system name with everything needed to make the magic happen
BUILD_TYPE_DICT = {
    MAVEN_KEY: {
        BUILD_FILE_NAME_KEY: MAVEN_BUILD_FILE,
        BUILD_FILE_HANDLER_KEY: create_git_blame_file
    },
    GRADLE_KEY: {
        BUILD_FILE_NAME_KEY: GRADLE_BUILD_FILE,
        BUILD_FILE_HANDLER_KEY: create_git_blame_file
    },
    NPM_KEY: {
        BUILD_FILE_NAME_KEY: NPM_BUILD_FILE,
        BUILD_FILE_HANDLER_KEY: create_git_blame_file
    },
    PYTHON_REQUIREMENTS_KEY: {
        BUILD_FILE_NAME_KEY: PYTHON_BUILD_FILE_REQUIREMENTS,
        BUILD_FILE_HANDLER_KEY: create_git_blame_file
    },
    PYTHON_PIPENV_KEY: {
        BUILD_FILE_NAME_KEY: PYTHON_BUILD_FILE_PIPENV,
        BUILD_FILE_HANDLER_KEY: create_git_blame_file
    },
    PHP_COMPOSER_KEY: {
        BUILD_FILE_NAME_KEY: PHP_COMPOSER_BUILD_FILE,
        BUILD_FILE_HANDLER_KEY: create_git_blame_file
    },
    DOTNET_DEPS_KEY: {
        BUILD_FILE_NAME_KEY: DOTNET_BUILD_FILE,
        BUILD_FILE_HANDLER_KEY: create_git_blame_file
    },
    RUBY_GEM_KEY: {
        BUILD_FILE_NAME_KEY: RUBY_BUILD_FILE,
        BUILD_FILE_HANDLER_KEY: create_git_blame_file
    },     
    GO_MOD_KEY: {
        BUILD_FILE_NAME_KEY: GO_BUILD_FILE,
        BUILD_FILE_HANDLER_KEY: create_git_blame_file
    }   
}

# used by `generate_csv` to pair build files with the appropriate
# build system name. generated dynamically by reversing BUILD_TYPE_DICT


REVERSE_BUILD_TYPE_DICT = {v[BUILD_FILE_NAME_KEY]: k for (k, v) in BUILD_TYPE_DICT.items()}