import re


class BuildFile:
    LANGUAGE: str
    FILENAME: str | re.Pattern | None = None
    PURL: str

    @classmethod
    def get_build_file(cls, filename):
        for subcls in cls.__subclasses__():
            if isinstance(subcls.FILENAME, re.Pattern):
                if subcls.FILENAME.match(filename):
                    return subcls
                continue
            if subcls.FILENAME == filename:
                return subcls
            
        return None


class DotnetBuildFile(BuildFile):
    LANGUAGE = "dotnet"
    FILENAME = "deps.json"
    PURL = "nuget"
    
    
class DotnetBuildFileWithLock(BuildFile):
    LANGUAGE = "dotnet"
    FILENAME = "packages.json.lock"
    PURL = "nuget"


class GoBuildFile(BuildFile):
    LANGUAGE = "golang"
    FILENAME = "go.mod"
    PURL = "golang"


class GradleBuildFile(BuildFile):
    LANGUAGE = "java"
    FILENAME = "build.gradle"
    PURL = "maven"


class GradleBuildFileWithLock(BuildFile):
    LANGUAGE = "java"
    FILENAME = "gradle.lockfile"
    PURL = "maven"


class MavenBuildFile(BuildFile):
    LANGUAGE = "java"
    FILENAME = "pom.xml"
    PURL = "maven"


class NpmBuildFile(BuildFile):
    LANGUAGE = "javascript"
    FILENAME = "package.json"
    PURL = "npm"


class NpmBuildFileWithLock(BuildFile):
    LANGUAGE = "javascript"
    FILENAME = "package.json.lock"
    PURL = "npm"


class NpmBuildFileWithLock2(BuildFile):
    LANGUAGE = "javascript"
    FILENAME = "package-lock.json"
    PURL = "npm"


class PhpComposerBuildFile(BuildFile):
    LANGUAGE = "php"
    FILENAME = "composer.json"
    PURL = "composer"


class PhpComposerBuildFileWithLock(BuildFile):
    LANGUAGE = "php"
    FILENAME = "composer.lock"
    PURL = "composer"


class PythonRequirementsBuildFile(BuildFile):
    LANGUAGE = "python"
    FILENAME = re.compile(r"^(.*)requirements(.*)\.txt$")
    PURL = "pypi"


class PythonSetupPyBuildFile(BuildFile):
    LANGUAGE = "python"
    FILENAME = "setup.py"
    PURL = "pypi"


class PythonPipenvBuildFile(BuildFile):
    LANGUAGE = "python"
    FILENAME = "Pipfile"
    PURL = "pypi"


class PythonPipenvBuildFileWithLock(BuildFile):
    LANGUAGE = "python"
    FILENAME = "Pipfile.lock"
    PURL = "pypi"


class PythonPoetryBuildFileWithLock(BuildFile):
    LANGUAGE = "python"
    FILENAME = "poetry.lock"
    PURL = "pypi"


class RubyBuildFile(BuildFile):
    LANGUAGE = "ruby"
    FILENAME = "Gemfile"
    PURL = "gem"


class RubyBuildFileWithLock(BuildFile):
    LANGUAGE = "ruby"
    FILENAME = "Gemfile.lock"
    PURL = "gem"


class RubyGemspecBuildFile(BuildFile):
    LANGUAGE = "ruby"
    FILENAME = re.compile(r"^(.*)\.gemspec$")
    PURL = "gem"


# class RustBuildFile(BuildFile):
#     LANGUAGE = "rust"
#     FILENAME = "Cargo.lock"
#     PURL = "cargo"