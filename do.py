#!/usr/bin/env python
## -*- mode: python -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys
import os
from os.path import join, abspath, realpath
import shutil
import tempfile
import subprocess
from subprocess import STDOUT
import platform
import time
import glob
import signal
import re
import socket
from multiprocessing import Process


## Change to the root directory of repository and add our tools/
## subdirectory to system wide search path for modules.
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(join('code-experiments', 'tools')))

from amalgamate import amalgamate
from cocoutils import make, run, python, check_output
from cocoutils import copy_file, expand_file, write_file
from cocoutils import executable_path
from cocoutils import git_version, git_revision

CORE_FILES = ['code-experiments/src/coco_random.c',
              'code-experiments/src/coco_suite.c',
              'code-experiments/src/coco_observer.c',
              'code-experiments/src/coco_archive.c'
             ]

MATLAB_FILES = ['cocoCall.m', 'cocoEvaluateFunction.m', 'cocoObserver.m',
                'cocoObserverFree.m', 'cocoProblemAddObserver.m',
                'cocoProblemFinalTargetHit.m', 'cocoProblemFree.m',
                'cocoProblemGetDimension.m', 'cocoProblemGetEvaluations.m',
                'cocoProblemGetId.m', 'cocoProblemGetInitialSolution.m',
                'cocoProblemGetLargestValuesOfInterest.m',
                'cocoProblemGetName.m', 'cocoProblemGetNumberOfObjectives.m',
                'cocoProblemGetSmallestValuesOfInterest.m',
                'cocoProblemIsValid.m', 'cocoProblemRemoveObserver.m',
                'cocoSetLogLevel.m', 'cocoSuite.m', 'cocoSuiteFree.m',
                'cocoSuiteGetNextProblem.m', 'cocoSuiteGetProblem.m']

_verbosity = False
# Do not suppress build messages unless specifically requested
_build_verbosity = True

################################################################################
## C
def build_c():
    """ Builds the C source code """
    global RELEASE
    amalgamate(CORE_FILES + ['code-experiments/src/coco_runtime_c.c'],
               'code-experiments/build/c/coco.c', RELEASE,
               {"COCO_VERSION": git_version(pep440=True)})
    expand_file('code-experiments/src/coco.h',
                'code-experiments/build/c/coco.h',
                {"COCO_VERSION": git_version(pep440=True)})
    copy_file('code-experiments/build/c/coco.c',
              'code-experiments/examples/bbob2009-c-cmaes/coco.c')
    expand_file('code-experiments/build/c/coco.h',
                'code-experiments/examples/bbob2009-c-cmaes/coco.h',
                {'COCO_VERSION': git_version(pep440=True)})
    write_file(git_revision(), "code-experiments/build/c/REVISION")
    write_file(git_version(), "code-experiments/build/c/VERSION")
    if 11 < 3:
        python('code-experiments/build/c', ['make.py', 'clean'], verbose=_build_verbosity)
        python('code-experiments/build/c', ['make.py', 'all'], verbose=_build_verbosity)
    else:
        make("code-experiments/build/c", "clean", verbose=_build_verbosity)
        make("code-experiments/build/c", "all", verbose=_build_verbosity)


def run_c():
    """ Builds and runs the example experiment in C """
    build_c()
    try:
        run('code-experiments/build/c', ['./example_experiment'], verbose=_verbosity)
    except subprocess.CalledProcessError:
        sys.exit(-1)


def test_c():
    """ Builds and runs unit tests, integration tests and an example experiment test in C """
    build_c()
    # Perform unit tests
    build_c_unit_tests()
    run_c_unit_tests()
    # Perform integration tests
    build_c_integration_tests()
    run_c_integration_tests()
    # Perform example experiment tests
    build_c_example_tests()
    run_c_example_tests()


def test_c_unit():
    """ Builds and runs unit tests in C """
    build_c()
    # Perform unit tests
    build_c_unit_tests()
    run_c_unit_tests()


def test_c_integration():
    """ Builds and runs integration tests in C """
    build_c()
    # Perform integration tests
    build_c_integration_tests()
    run_c_integration_tests()


def test_c_example():
    """ Builds and runs an example experiment test in C """
    build_c()
    # Perform example tests
    build_c_example_tests()
    run_c_example_tests()


def build_c_unit_tests():
    """ Builds unit tests in C """
    copy_file('code-experiments/build/c/coco.c', 'code-experiments/test/unit-test/coco.c')
    expand_file('code-experiments/src/coco.h', 'code-experiments/test/unit-test/coco.h',
                {'COCO_VERSION': git_version(pep440=True)})
    make("code-experiments/test/unit-test", "clean", verbose=_build_verbosity)
    make("code-experiments/test/unit-test", "all", verbose=_build_verbosity)


def run_c_unit_tests():
    """ Runs unit tests in C """
    try:
        run('code-experiments/test/unit-test', ['./unit_test'], verbose=_verbosity)
    except subprocess.CalledProcessError:
        sys.exit(-1)


def build_c_integration_tests():
    """ Builds integration tests in C """
    copy_file('code-experiments/build/c/coco.c',
              'code-experiments/test/integration-test/coco.c')
    expand_file('code-experiments/src/coco.h',
                'code-experiments/test/integration-test/coco.h',
                {'COCO_VERSION': git_version(pep440=True)})
    copy_file('code-experiments/src/bbob2009_testcases.txt', 'code-experiments/test/integration-test/bbob2009_testcases.txt')
    copy_file('code-experiments/src/bbob2009_testcases2.txt', 'code-experiments/test/integration-test/bbob2009_testcases2.txt')
    make("code-experiments/test/integration-test", "clean", verbose=_build_verbosity)
    make("code-experiments/test/integration-test", "all", verbose=_build_verbosity)


def run_c_integration_tests():
    """ Runs integration tests in C """
    try:
        run('code-experiments/test/integration-test',
            ['./test_coco', 'bbob2009_testcases.txt'], verbose=_verbosity)
        run('code-experiments/test/integration-test',
            ['./test_coco', 'bbob2009_testcases2.txt'], verbose=_verbosity)
        run('code-experiments/test/integration-test',
            ['./test_instance_extraction'], verbose=_verbosity)
        run('code-experiments/test/integration-test',
            ['./test_biobj'], verbose=_verbosity)
        run('code-experiments/test/integration-test',
            ['./test_bbob-constrained'], verbose=_verbosity)
        run('code-experiments/test/integration-test',
            ['./test_bbob-largescale'], verbose=_verbosity)
        run('code-experiments/test/integration-test',
            ['./test_bbob-mixint'], verbose=_verbosity)
    except subprocess.CalledProcessError:
        sys.exit(-1)


def build_c_example_tests():
    """ Builds an example experiment test in C """
    if os.path.exists('code-experiments/test/example-test'):
        shutil.rmtree('code-experiments/test/example-test')
        time.sleep(1)  # Needed to avoid permission errors for os.makedirs
    os.makedirs('code-experiments/test/example-test')
    copy_file('code-experiments/build/c/coco.c', 'code-experiments/test/example-test/coco.c')
    expand_file('code-experiments/src/coco.h', 'code-experiments/test/example-test/coco.h',
                {'COCO_VERSION': git_version(pep440=True)})
    copy_file('code-experiments/build/c/example_experiment.c',
              'code-experiments/test/example-test/example_experiment.c')
    copy_file('code-experiments/build/c/Makefile.in',
              'code-experiments/test/example-test/Makefile.in')
    copy_file('code-experiments/build/c/Makefile_win_gcc.in',
              'code-experiments/test/example-test/Makefile_win_gcc.in')
    make("code-experiments/test/example-test", "clean", verbose=_build_verbosity)
    make("code-experiments/test/example-test", "all", verbose=_build_verbosity)


def run_c_example_tests():
    """ Runs an example experiment test in C """
    try:
        run('code-experiments/test/example-test', ['./example_experiment'],
            verbose=_verbosity)
    except subprocess.CalledProcessError:
        sys.exit(-1)


def leak_check():
    """ Performs a leak check in C """
    build_c()
    build_c_integration_tests()
    os.environ['CFLAGS'] = '-g -Os'
    valgrind_cmd = ['valgrind', '--error-exitcode=1', '--track-origins=yes',
                    '--leak-check=full', '--show-reachable=yes',
                    '--gen-suppressions=yes', '-s',
                    './test_bbob-largescale', 'leak_check']
    run('code-experiments/test/integration-test', valgrind_cmd, verbose=_verbosity)
    valgrind_cmd = ['valgrind', '--error-exitcode=1', '--track-origins=yes',
                    '--leak-check=full', '--show-reachable=yes',
                    '--gen-suppressions=yes', '-s',
                    './test_bbob-mixint', 'leak_check']
    run('code-experiments/test/integration-test', valgrind_cmd, verbose=_verbosity)
    valgrind_cmd = ['valgrind', '--error-exitcode=1', '--track-origins=yes',
                    '--leak-check=full', '--show-reachable=yes',
                    '--gen-suppressions=yes', '-s',
                    './test_coco', 'bbob2009_testcases.txt']
    run('code-experiments/test/integration-test', valgrind_cmd, verbose=_verbosity)
    valgrind_cmd = ['valgrind', '--error-exitcode=1', '--track-origins=yes',
                    '--leak-check=full', '--show-reachable=yes',
                    '--gen-suppressions=yes', '-s',
                    './test_biobj', 'leak_check']
    run('code-experiments/test/integration-test', valgrind_cmd, verbose=_verbosity)
    valgrind_cmd = ['valgrind', '--error-exitcode=1', '--track-origins=yes',
                    '--leak-check=full', '--show-reachable=yes',
                    '--gen-suppressions=yes', '-s',
                    './test_bbob-constrained', 'leak_check']
    run('code-experiments/test/integration-test', valgrind_cmd, verbose=_verbosity)


################################################################################
## Python 2
def install_error(e):
    exception_message = e.output.splitlines()
    formatted_message = ["|" + " " * 77 + "|"]
    for line in exception_message:
        while len(line) > 75:
            formatted_message.append("| " + line[:75] + " |")
            line = line[75:]
        formatted_message.append("| " + line.ljust(75) + " |")
    print("""
An exception occurred while trying to install packages.

A common reason for this error is insufficient access rights
to the installation directory. The original exception message
is as follows:

/----------------------------< EXCEPTION MESSAGE >----------------------------\\
{0}
\\-----------------------------------------------------------------------------/

To fix an access rights issue, you may try the following:

- Run the same command with "install-user" as additional argument.
  To get further help run do.py without a specific command.

- On *nix systems or MacOS, run the same command with a preceded "sudo ".

- Gain write access to the installation directory by changing
  access permissions or gaining administrative access.

""".format("\n".join(formatted_message)))
    return True

def install_postprocessing(package_install_option=[]):
    ''' Installs the COCO postprocessing as python module. '''
    global RELEASE
    expand_file(join('code-postprocessing', 'setup.py.in'),
                join('code-postprocessing', 'setup.py'),
                {'COCO_VERSION': git_version(pep440=True)})
    # copy_tree('code-postprocessing/latex-templates', 'code-postprocessing/cocopp/latex-templates')
    python('code-postprocessing', ['setup.py', 'install']
           + package_install_option, verbose=_verbosity,
           custom_exception_handler=install_error)

def uninstall_postprocessing():
    run('.', ['pip', 'uninstall', 'cocopp', '-y'], verbose=_verbosity)

def test_suites(args):
    """regression test on suites via Python"""
    if not args:
        args = ['2']
    test_python(  # this is a list of [folder, args] pairs
        [['code-experiments/test/regression-test',
          ['test_suites.py', arg]] for arg in args
        ] + [
            ['code-experiments/build/python',
             ['coco_test.py', 'bbob2009_testcases.txt', 'bbob2009_testcases2.txt']
            ]
        ])

def _prep_python():
    global RELEASE
    amalgamate(CORE_FILES + ['code-experiments/src/coco_runtime_c.c'],
               'code-experiments/build/python/cython/coco.c',
               RELEASE, {"COCO_VERSION": git_version(pep440=True)})
    expand_file('code-experiments/src/coco.h',
                'code-experiments/build/python/cython/coco.h',
                {'COCO_VERSION': git_version(pep440=True)})
    copy_file('code-experiments/src/bbob2009_testcases.txt',
              'code-experiments/build/python/bbob2009_testcases.txt')
    copy_file('code-experiments/src/bbob2009_testcases2.txt',
              'code-experiments/build/python/bbob2009_testcases2.txt')
    copy_file('code-experiments/build/python/README.md',
              'code-experiments/build/python/README.txt')
    expand_file('code-experiments/build/python/setup.py.in',
                'code-experiments/build/python/setup.py',
                {'COCO_VERSION': git_version(pep440=True)})  # hg_version()})
    # if 'darwin' in sys.platform:  # a hack to force cythoning
    #     run('code-experiments/build/python/cython', ['cython', 'interface.pyx'])


def build_python(package_install_option=[]):
    _prep_python()
    ## Force distutils to use Cython
    # os.environ['USE_CYTHON'] = 'true'
    # python('code-experiments/build/python', ['setup.py', 'sdist'])
    # python(join('code-experiments', 'build', 'python'),
    #        ['setup.py', 'install', '--user'])
    python(join('code-experiments', 'build', 'python'), ['setup.py', 'install']
           + package_install_option, custom_exception_handler=install_error)
    # os.environ.pop('USE_CYTHON')


def run_python(test=False, package_install_option=[]):
    """ Builds and installs the Python module `cocoex` and runs the
    `example_experiment.py` as a simple test case. If `test` is True,
    it runs, in addition, the tests in `coco_test.py`."""
    build_python(package_install_option=package_install_option)
    try:
        if test:
            python(os.path.join('code-experiments', 'build', 'python'), ['coco_test.py'])
        python(os.path.join('code-experiments', 'build', 'python'),
               ['example_experiment.py', 'bbob'])
    except subprocess.CalledProcessError:
        sys.exit(-1)


def run_sandbox_python(directory, script_filename=
                       os.path.join('code-experiments', 'build', 'python',
                                    'example_experiment.py')):
    """run a python script after building and installing `cocoex` in a new
    environment."""
    _prep_python()
    python('code-experiments/build/python',
           ['setup.py', 'check', '--metadata', '--strict'], verbose=_verbosity)
    ## Now install into a temporary location, run test and cleanup
    python_temp_home = tempfile.mkdtemp(prefix="coco")
    python_temp_lib = os.path.join(python_temp_home, "lib", "python")
    try:
        ## We setup a custom "homedir" here into which we install our
        ## coco extension and then use that temporary installation for
        ## the tests. Otherwise we would run the risk of contaminating
        ## the Python installation of the build/test machine.
        os.makedirs(python_temp_lib)
        os.environ['PYTHONPATH'] = python_temp_lib
        os.environ['USE_CYTHON'] = 'true'
        python('code-experiments/build/python',
               ['setup.py', 'install', '--home', python_temp_home],
               verbose=_verbosity, custom_exception_handler=install_error)
        python(directory, [script_filename])
        os.environ.pop('USE_CYTHON')
        os.environ.pop('PYTHONPATH')
    except subprocess.CalledProcessError:
        sys.exit(-1)
    finally:
        shutil.rmtree(python_temp_home)


def test_python(args=(['code-experiments/build/python', ['coco_test.py', 'None']],)):
    _prep_python()
    python('code-experiments/build/python',
           ['setup.py', 'check', '--metadata', '--strict'],
           verbose=_verbosity)
    ## Now install into a temporary location, run test and cleanup
    python_temp_home = tempfile.mkdtemp(prefix="coco")
    python_temp_lib = os.path.join(python_temp_home, "lib", "python")
    try:
        ## We setup a custom "homedir" here into which we install our
        ## coco extension and then use that temporary installation for
        ## the tests. Otherwise we would run the risk of contaminating
        ## the Python installation of the build/test machine.
        os.makedirs(python_temp_lib)
        os.environ['PYTHONPATH'] = python_temp_lib
        os.environ['USE_CYTHON'] = 'true'
        python('code-experiments/build/python',
               ['setup.py', 'install', '--home', python_temp_home],
               verbose=_verbosity, custom_exception_handler=install_error)
        for folder, more_args in args:
            python(folder, more_args, verbose=_verbosity)
        # python('code-experiments/build/python',
        #        ['coco_test.py', 'bbob2009_testcases.txt'], verbose=_verbosity)
        # python('code-experiments/build/python',
        #        ['coco_test.py', 'bbob2009_testcases2.txt'], verbose=_verbosity)
        os.environ.pop('USE_CYTHON')
        os.environ.pop('PYTHONPATH')
    except subprocess.CalledProcessError:
        sys.exit(-1)
    finally:
        shutil.rmtree(python_temp_home)


################################################################################
## Matlab
def build_matlab():
    """Builds MATLAB example in build/matlab/ but not the one in examples/."""

    global RELEASE
    amalgamate(CORE_FILES + ['code-experiments/src/coco_runtime_matlab.c'],
               'code-experiments/build/matlab/coco.c',
               RELEASE, {"COCO_VERSION": git_version(pep440=True)})
    expand_file('code-experiments/src/coco.h',
                'code-experiments/build/matlab/coco.h',
                {'COCO_VERSION': git_version(pep440=True)})
    write_file(git_revision(), "code-experiments/build/matlab/REVISION")
    write_file(git_version(), "code-experiments/build/matlab/VERSION")
    run('code-experiments/build/matlab',
        ['matlab', '-nodesktop', '-nosplash', '-r', 'setup, exit'],
        verbose=_verbosity)


def run_matlab():
    """ Builds and runs the example experiment in build/matlab/ in MATLAB """
    print('CLEAN\tmex files from code-experiments/build/matlab/')
    # remove the mex files for a clean compilation first
    for filename in glob.glob('code-experiments/build/matlab/*.mex*'):
        os.remove(filename)
    # amalgamate, copy, and build
    build_matlab()
    wait_for_compilation_to_finish('./code-experiments/build/matlab/cocoCall')
    # run after compilation finished
    run('code-experiments/build/matlab',
        ['matlab', '-nodesktop', '-nosplash', '-r', 'exampleexperiment, exit'],
        verbose=_verbosity)


def is_compiled(filenameprefix):
    """Returns true iff a file 'filenameprefix.mex*' exists."""

    # get all files with the given prefix
    files = glob.glob(filenameprefix + '.*')
    # return true iff one of the files contains 'mex'
    ret = False
    for f in files:
        if '.mex' in f:
            ret = True
    return ret


def wait_for_compilation_to_finish(filenameprefix):
    """Waits until filenameprefix.c is compiled into a mex file.

    Needed because under Windows, a MATLAB call is typically non-blocking
    and thus, the experiments would be started before the compilation is over.
    """

    print('Wait for compilation to finish', end='')
    while not is_compiled(filenameprefix):
        time.sleep(2)
        print('.', end='')
    print(' ')


def build_matlab_sms():
    """Builds the SMS-EMOA in MATLAB """
    global RELEASE
    destination_folder = 'code-experiments/examples/bbob-biobj-matlab-smsemoa'
    # amalgamate and copy files
    amalgamate(CORE_FILES + ['code-experiments/src/coco_runtime_matlab.c'],
               join(destination_folder, 'coco.c'), RELEASE,
               {"COCO_VERSION": git_version(pep440=True)})
    expand_file('code-experiments/src/coco.h', join(destination_folder, 'coco.h'),
                {'COCO_VERSION': git_version(pep440=True)})
    for f in MATLAB_FILES:
        copy_file(join('code-experiments/build/matlab/', f), join(destination_folder, f))
    write_file(git_revision(), join(destination_folder, "REVISION"))
    write_file(git_version(), join(destination_folder, "VERSION"))
    copy_file('code-experiments/build/matlab/cocoCall.c', join(destination_folder, 'cocoCall.c'))
    # compile
    run(destination_folder, ['matlab', '-nodesktop', '-nosplash', '-r', 'setup, exit'])


def run_matlab_sms():
    """ Builds and runs the SMS-EMOA in MATLAB """
    print('CLEAN\tmex files from code-experiments/examples/bbob-biobj-matlab-smsemoa/')
    # remove the mex files for a clean compilation first
    for filename in glob.glob('code-experiments/examples/bbob-biobj-matlab-smsemoa/*.mex*'):
        os.remove(filename)
    # amalgamate, copy, and build
    build_matlab_sms()
    wait_for_compilation_to_finish('./code-experiments/examples/bbob-biobj-matlab-smsemoa/paretofront')
    # run after compilation finished
    run('code-experiments/examples/bbob-biobj-matlab-smsemoa',
        ['matlab', '-nodesktop', '-nosplash', '-r', 'run_smsemoa_on_bbob_biobj, exit'],
        verbose=_verbosity)


################################################################################
## Octave
def build_octave():
    """Builds example in build/matlab/ with GNU Octave."""

    global RELEASE
    amalgamate(CORE_FILES + ['code-experiments/src/coco_runtime_c.c'],
               'code-experiments/build/matlab/coco.c', RELEASE,
               {"COCO_VERSION": git_version(pep440=True)})
    expand_file('code-experiments/src/coco.h', 'code-experiments/build/matlab/coco.h',
                {'COCO_VERSION': git_version(pep440=True)})
    write_file(git_revision(), "code-experiments/build/matlab/REVISION")
    write_file(git_version(), "code-experiments/build/matlab/VERSION")

    # make sure that under Windows, run_octave has been run at least once
    # before to provide the necessary octave_coco.bat file
    if 'win32' in sys.platform:
        run('code-experiments/build/matlab',
            ['octave_coco.bat', '--no-gui', 'setup.m'], verbose=_verbosity)
    else:
        run('code-experiments/build/matlab',
            ['octave', '--no-gui', 'setup.m'], verbose=_verbosity)


def run_octave():
    # remove the mex files for a clean compilation first
    print('CLEAN\tmex files from code-experiments/build/matlab/')
    for filename in glob.glob('code-experiments/build/matlab/*.mex*'):
        os.remove(filename)

    # Copy octave-coco.bat to the Octave folder under Windows to allow
    # calling Octave from command line without messing up the system.
    # Note that 'win32' stands for both Windows 32-bit and 64-bit.
    if 'win32' in sys.platform:
        print('SEARCH\tfor Octave folder from C:\\ (can take some time)')
        lookfor = 'octave.bat'
        for root, dirs, files in os.walk('C:\\'):
            if lookfor in files:
                break
        copy_file('code-experiments/build/matlab/octave_coco.bat.in', join(root, 'octave_coco.bat'))

    # amalgamate, copy, and build
    build_octave()
    if 'win32' in sys.platform:
        run('code-experiments/build/matlab',
            ['octave_coco.bat', '--no-gui', 'exampleexperiment.m'], verbose=_verbosity)
    else:
        run('code-experiments/build/matlab',
            ['octave', '--no-gui', 'exampleexperiment.m'], verbose=_verbosity)


def test_octave():
    """ Builds and runs the test in Octave, which is equal to the example experiment """
    build_octave()
    try:
        if 'win32' in sys.platform:
            run('code-experiments/build/matlab',
                ['octave_coco.bat', '--no-gui', 'exampleexperiment.m'],
                verbose=_verbosity)
        else:
            run('code-experiments/build/matlab',
                ['octave', '--no-gui', 'exampleexperiment.m'], verbose=_verbosity)
    except subprocess.CalledProcessError:
        sys.exit(-1)


def build_octave_sms():
    """Builds the SMS-EMOA in Octave """
    global RELEASE
    destination_folder = 'code-experiments/examples/bbob-biobj-matlab-smsemoa'
    # amalgamate and copy files
    amalgamate(CORE_FILES + ['code-experiments/src/coco_runtime_c.c'],
               join(destination_folder, 'coco.c'), RELEASE,
               {"COCO_VERSION": git_version(pep440=True)})
    expand_file('code-experiments/src/coco.h', join(destination_folder, 'coco.h'),
                {'COCO_VERSION': git_version(pep440=True)})
    for f in MATLAB_FILES:
        copy_file(join('code-experiments/build/matlab/', f), join(destination_folder, f))
    write_file(git_revision(), join(destination_folder, "REVISION"))
    write_file(git_version(), join(destination_folder, "VERSION"))
    copy_file('code-experiments/build/matlab/cocoCall.c', join(destination_folder, 'cocoCall.c'))
    # compile
    if 'win32' in sys.platform:
        run(destination_folder, ['octave_coco.bat', '--no-gui', 'setup.m'])
    else:
        run(destination_folder, ['octave', '--no-gui', 'setup.m'])


def run_octave_sms():
    """ Builds and runs the SMS-EMOA in Octave

        Note: does not work yet with all Windows/Octave versions.
    """

    print('CLEAN\tmex files from code-experiments/examples/bbob-biobj-matlab-smsemoa/')
    destination_folder = 'code-experiments/examples/bbob-biobj-matlab-smsemoa'
    # remove the mex files for a clean compilation first
    for filename in glob.glob(join(destination_folder, '*.mex*')):
        os.remove(filename)
    # amalgamate, copy, and build
    build_octave_sms()
    wait_for_compilation_to_finish(join(destination_folder, 'paretofront'))
    # run after compilation finished
    if 'win32' in sys.platform:
        run(destination_folder,
            ['octave_coco.bat', '-nogui', 'run_smsemoa_on_bbob_biobj.m'],
            verbose=_verbosity)
    else:
        run(destination_folder,
            ['octave', '-nogui', 'run_smsemoa_on_bbob_biobj.m'],
            verbose=_verbosity)

################################################################################
## Java
def build_java():
    """ Builds the example experiment in Java """
    global RELEASE
    amalgamate(CORE_FILES + ['code-experiments/src/coco_runtime_c.c'],
               'code-experiments/build/java/coco.c', RELEASE,
               {"COCO_VERSION": git_version(pep440=True)})
    expand_file('code-experiments/src/coco.h', 'code-experiments/build/java/coco.h',
                {'COCO_VERSION': git_version(pep440=True)})
    write_file(git_revision(), "code-experiments/build/java/REVISION")
    write_file(git_version(), "code-experiments/build/java/VERSION")

    javacpath = executable_path('javac')
    javahpath = executable_path('javah')
    if javacpath and javahpath:
        run('code-experiments/build/java', ['javac', '-classpath', '.', 'CocoJNI.java'], verbose=_verbosity)
        run('code-experiments/build/java', ['javah', '-classpath', '.', 'CocoJNI'], verbose=_verbosity)
    elif javacpath:
        run('code-experiments/build/java', ['javac', '-h', '.', 'CocoJNI.java'], verbose=_verbosity)
    else:
        raise RuntimeError('Can not find javac path!')


    # Finds the path to the headers jni.h and jni_md.h (platform-dependent)
    # and compiles the CocoJNI library (compiler-dependent). So far, only
    # the following cases are covered:

    # 1. Windows with Cygwin (both 64-bit)
    # Note that 'win32' stands for both Windows 32-bit and 64-bit.
    # Since platform 'cygwin' does not work as expected, we need to look for it in the PATH.
    if ('win32' in sys.platform) and ('cygwin' in os.environ['PATH']):
        jdkpath = check_output(['where', 'javac'], stderr=STDOUT,
                               env=os.environ, universal_newlines=True)
        jdkpath1 = jdkpath.split("bin")[0] + 'include'
        jdkpath2 = jdkpath1 + '\\win32'

        if '64' in platform.machine():
            run('code-experiments/build/java', ['x86_64-w64-mingw32-gcc', '-I', jdkpath1, '-I',
                                                jdkpath2, '-shared', '-o', 'CocoJNI.dll',
                                                'CocoJNI.c', '-lwsock32'],
                verbose=_verbosity)

            # 2. Windows with Cygwin (both 32-bit)
        elif '32' in platform.machine() or 'x86' in platform.machine():
            run('code-experiments/build/java', ['i686-w64-mingw32-gcc', '-Wl,--kill-at', '-I',
                                                jdkpath1, '-I', jdkpath2, '-shared', '-o',
                                                'CocoJNI.dll', 'CocoJNI.c', '-lwsock32'],
                verbose=_verbosity)

    # 3. Windows without Cygwin
    elif ('win32' in sys.platform) and ('cygwin' not in os.environ['PATH']):
        jdkpath = check_output(['where', 'javac'], stderr=STDOUT,
                               env=os.environ, universal_newlines=True)
        jdkpath1 = jdkpath.split("bin")[0] + 'include'
        jdkpath2 = jdkpath1 + '\\win32'
        run('code-experiments/build/java',
            ['gcc', '-Wl,--kill-at', '-I', jdkpath1, '-I', jdkpath2,
             '-shared', '-o', 'CocoJNI.dll', 'CocoJNI.c', '-lwsock32'],
            verbose=_verbosity)

    # 4. Linux
    elif 'linux' in sys.platform:
        # bad bad bad...
        #jdkpath = check_output(['locate', 'jni.h'], stderr=STDOUT,
        #                       env=os.environ, universal_newlines=True)
        #jdkpath1 = jdkpath.split("jni.h")[0]
        # better
        javapath = executable_path('java')
        if not javapath:
            raise RuntimeError('Can not find Java executable')
        jdkhome = abspath(join(javapath, os.pardir, os.pardir))
        if os.path.basename(jdkhome) == 'jre':
            jdkhome = join(jdkhome, os.pardir)
        jdkpath1 = join(jdkhome, 'include')
        jdkpath2 = jdkpath1 + '/linux'
        run('code-experiments/build/java',
            ['gcc', '-I', jdkpath1, '-I', jdkpath2, '-c', 'CocoJNI.c'],
            verbose=_verbosity)
        run('code-experiments/build/java',
            ['gcc', '-I', jdkpath1, '-I', jdkpath2, '-o',
             'libCocoJNI.so', '-fPIC', '-shared', 'CocoJNI.c'],
            verbose=_verbosity)

    # 5. Mac
    elif 'darwin' in sys.platform:
        jdkversion = check_output(['javac', '-version'], stderr=STDOUT,
                                  env=os.environ, universal_newlines=True)
        jdkversion = jdkversion.split()[1]
        jdkpath = '/System/Library/Frameworks/JavaVM.framework/Headers'
        jdkpath1 = ('/Library/Java/JavaVirtualMachines/jdk' +
                    jdkversion + '.jdk/Contents/Home/include')
        jdkpath2 = jdkpath1 + '/darwin'
        run('code-experiments/build/java',
            ['gcc', '-I', jdkpath, '-I', jdkpath1, '-I', jdkpath2, '-c', 'CocoJNI.c'],
            verbose=_verbosity)
        run('code-experiments/build/java',
            ['gcc', '-dynamiclib', '-o', 'libCocoJNI.jnilib', 'CocoJNI.o'],
            verbose=_verbosity)

    run('code-experiments/build/java', ['javac', '-classpath', '.', 'Problem.java'], verbose=_verbosity)
    run('code-experiments/build/java', ['javac', '-classpath', '.', 'Benchmark.java'], verbose=_verbosity)
    run('code-experiments/build/java', ['javac', '-classpath', '.', 'Observer.java'], verbose=_verbosity)
    run('code-experiments/build/java', ['javac', '-classpath', '.', 'Suite.java'], verbose=_verbosity)
    run('code-experiments/build/java', ['javac', '-classpath', '.', 'ExampleExperiment.java'], verbose=_verbosity)


def run_java():
    """ Builds and runs the example experiment in Java """
    build_java()
    try:
        run('code-experiments/build/java',
            ['java', '-classpath', '.', '-Djava.library.path=.', 'ExampleExperiment'],
            verbose=_verbosity)
    except subprocess.CalledProcessError:
        sys.exit(-1)


def test_java():
    """ Builds and runs the test in Java, which is equal to the example experiment """
    build_java()
    try:
        run('code-experiments/build/java',
            ['java', '-classpath', '.', '-Djava.library.path=.', 'ExampleExperiment'],
            verbose=_verbosity)
    except subprocess.CalledProcessError:
        sys.exit(-1)


################################################################################
## External evaluation using socket communication
socket_server_host = '127.0.0.1'  # Local host
socket_server_port_c = 7251
socket_server_port_python = 7252
socket_server_ports = [socket_server_port_c, socket_server_port_python]
rw_evaluator_top_trumps = 'EVALUATE_RW_TOP_TRUMPS'
rw_evaluator_mario_gan = 'EVALUATE_RW_MARIO_GAN'
rw_evaluators = [rw_evaluator_top_trumps, rw_evaluator_mario_gan]


def _set_external_evaluator(evaluate_string, new_value):
    """Set the external evaluator value in all the files required for compiling external
    evaluators (C source files and make files)"""
    def replace_in_file(file_name):
        """Performs the replacement for the given file_name"""
        find_strings = ['{}{}{}'.format(prepend, evaluate_string, append) for prepend, append in
                        zip(['#define ', ''], [' \\d+', ' = \\d+'])]
        replace_strings = ['{}{}{}'.format(prepend, evaluate_string, append) for prepend, append in
                           zip(['#define ', ''], [' {}'.format(new_value),
                                                  ' = {}'.format(new_value)])]
        with open(file_name) as f:
            s = f.read()
            for find_string, replace_string in zip(find_strings, replace_strings):
                found = re.findall(find_string, s)
                if _build_verbosity and len(found) > 0 and replace_string not in found:
                    print('REPLACE {} with {} in {}'.format(found, replace_string, file_name))
                s = re.sub(find_string, replace_string, s)
        with open(file_name, 'w') as f:
            f.write(s)

    replace_in_file(os.path.join('code-experiments', 'rw-problems', 'socket_server.c'))
    replace_in_file(os.path.join('code-experiments', 'rw-problems', 'Makefile.in'))
    replace_in_file(os.path.join('code-experiments', 'rw-problems', 'Makefile_win_gcc.in'))
    replace_in_file(os.path.join('code-experiments', 'rw-problems', 'socket_server.py'))


def _download_external_evaluator(name, url_name, force_download=False):
    """Downloads the data of the external evaluator with the given name if it is not present yet.
    If force_download, the download will happen regardless of the previous existence of the data
    in the same destination folder"""
    import urllib.request
    import zipfile
    data_exists = os.path.isdir(os.path.join('code-experiments', 'rw-problems', name))
    if not data_exists or force_download:
        if data_exists:
            shutil.rmtree(os.path.join('code-experiments', 'rw-problems', name))
        print('DOWNLOAD data for {} (can take a while)'.format(name))
        file_name, _ = urllib.request.urlretrieve(url_name)
        zip_file = zipfile.ZipFile(file_name, 'r')
        zip_file.extractall(os.path.join('code-experiments', 'rw-problems'))
        # Make sure the folder is named as expected
        os.rename(os.path.join('code-experiments', 'rw-problems', zip_file.filelist[0].filename),
                  os.path.join('code-experiments', 'rw-problems', name))
        for root, dirs, files in os.walk(os.path.join('code-experiments', 'rw-problems', name),
                                         topdown=False):
            for name in files:
                # Change file permission so it can be deleted
                os.chmod(join(root, name), 0o777)
        print('DOWNLOAD completed')


def _build_socket_server_c():
    """Build the socket server for external evaluation in C"""
    make(os.path.join('code-experiments', 'rw-problems'), 'clean', verbose=_build_verbosity)
    make(os.path.join('code-experiments', 'rw-problems'), 'all', verbose=_build_verbosity)


def _run_socket_server_c(port):
    """Run the socket server for external evaluation in C"""
    if port is None:
        port = socket_server_port_c
    command = '{} {} silent'.format(
        os.path.join('code-experiments', 'rw-problems', 'socket_server'),
        port)
    if 'win32' not in sys.platform:
        command = './' + command
    p = Process(target=subprocess.Popen, args=(command,), kwargs=dict(shell=True))
    p.start()


def _run_socket_server_python(port):
    """Run the socket server for external evaluation in Python"""
    if port is None:
        port = socket_server_port_python
    command = 'python {} {} silent'.format(
        os.path.join('code-experiments', 'rw-problems', 'socket_server.py'),
        port)
    p = Process(target=subprocess.Popen, args=(command,), kwargs=dict(shell=True))
    p.start()


def build_toy_socket_server_c():
    """Build the socket server with the toy socket evaluator in C"""
    # Make sure only toy socket is the only evaluator that is built (set the values of all
    # rw_evaluators to zero)
    for rw_evaluator in rw_evaluators:
        _set_external_evaluator(rw_evaluator, 0)
    _build_socket_server_c()


def build_toy_socket_server_python():
    """Prepare the socket server with the toy socket evaluator in Python"""
    # Make sure only toy socket is the only evaluator that is built (set the values of all
    # rw_evaluators to zero)
    for rw_evaluator in rw_evaluators:
        _set_external_evaluator(rw_evaluator, 0)


def _build_rw_top_trumps_lib():
    """Build the top trumps library with the top trumps evaluator (in C)"""
    try:
        # Build the library
        rw_library = 'rw_top_trumps'
        make(os.path.join('code-experiments', 'rw-problems', 'top_trumps'), 'clean',
             verbose=_build_verbosity)
        make(os.path.join('code-experiments', 'rw-problems', 'top_trumps'), 'all',
             verbose=_build_verbosity)
        if 'win32' in sys.platform:
            rw_library += '.dll'
            # Copy the library so that the socket server finds it
            copy_file(os.path.join('code-experiments', 'rw-problems', 'top_trumps', rw_library),
                      os.path.join('code-experiments', 'rw-problems', rw_library))
        else:
            rw_library = 'lib' + rw_library + '.so'
            # Create a symlink to the library to be used at run-time
            library_src = os.path.abspath(os.path.join('code-experiments', 'rw-problems',
                                                       'top_trumps', rw_library))
            # Copy the library so that the socket server finds it
            copy_file(library_src, os.path.join('code-experiments', 'rw-problems', rw_library))
            if 'darwin' in sys.platform:
                library_des = '/usr/local/lib/' + rw_library
                if os.path.lexists(library_des):
                    os.remove(library_des)
                os.symlink(library_src, library_des)
    except PermissionError as e:
        print('Encountered a permission error, the rw-top-trumps library is probably used by the'
              'server. Stop the socket server and try again. \nError: {}'.format(e))
        sys.exit(-1)
    except subprocess.CalledProcessError:
        sys.exit(-1)


def build_rw_top_trumps_server(force_download=False, exclusive_evaluator=True):
    """Download and build the socket server with the top trumps evaluator (in C)"""
    # Download the data
    url_name = 'https://github.com/ttusar/top-trumps/archive/master.zip'
    _download_external_evaluator('top_trumps', url_name, force_download=force_download)
    # Build the library
    _build_rw_top_trumps_lib()
    if exclusive_evaluator:
        # Build the socket server that uses only the rw_top_trumps evaluator
        for rw_evaluator in rw_evaluators:
            if rw_evaluator == rw_evaluator_top_trumps:
                _set_external_evaluator(rw_evaluator, 1)
            else:
                _set_external_evaluator(rw_evaluator, 0)
    _build_socket_server_c()


def build_rw_mario_gan_server(force_download=False, exclusive_evaluator=True):
    """Download data and prepare the socket server to use the mario gan evaluator in Python"""
    # Download the data
    url_name = 'https://github.com/TheHedgeify/mario-gan/archive/master.zip'
    _download_external_evaluator('mario_gan', url_name, force_download=force_download)
    if exclusive_evaluator:
        # Set the socket server to use only the rw_gan_mario evaluator
        for rw_evaluator in rw_evaluators:
            if rw_evaluator == rw_evaluator_mario_gan:
                _set_external_evaluator(rw_evaluator, 1)
            else:
                _set_external_evaluator(rw_evaluator, 0)


def build_socket_servers(force_download=False):
    """Build the socket server with all available evaluators in C and Python"""
    # Set the socket server to use all evaluators
    for rw_evaluator in rw_evaluators:
        _set_external_evaluator(rw_evaluator, 1)
    build_rw_top_trumps_server(force_download=force_download, exclusive_evaluator=False)
    build_rw_mario_gan_server(force_download=force_download, exclusive_evaluator=False)


def run_toy_socket_server_c(port):
    """Build and run the socket server with the toy socket evaluator in C"""
    build_toy_socket_server_c()
    _run_socket_server_c(port)


def run_toy_socket_server_python(port):
    """Build and run the socket server with the toy socket evaluator in Python"""
    build_toy_socket_server_python()
    _run_socket_server_python(port)


def run_rw_top_trumps_server(port, force_download=False):
    """Build and run the socket server with the top trumps evaluator (in C)"""
    build_rw_top_trumps_server(force_download=force_download, exclusive_evaluator=True)
    _run_socket_server_c(port)


def run_rw_mario_gan_server(port, force_download=False):
    """Prepare and run the socket server with the mario gan evaluator (in Python)"""
    build_rw_mario_gan_server(force_download=force_download, exclusive_evaluator=True)
    _run_socket_server_python(port)


def run_socket_servers(force_download=False):
    """Run socket servers in C and Python"""
    build_socket_servers(force_download=force_download)
    _run_socket_server_c(socket_server_port_c)
    _run_socket_server_python(socket_server_port_python)


def _stop_socket_server(port):
    """Stop the socket server running on the given port"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Create socket
        try:
            s.connect((socket_server_host, port))  # Connect to the server
        except socket.error:
            print('No socket server found on port {}'.format(port))
            return
        s.send('SHUTDOWN'.encode())  # Send request for shutdown
        s.close()
        print('Stopped socket sever on port {}'.format(port))
    except (socket.error, Exception) as e:
        print('Error stopping socket server on port {}: {}'.format(port, e))
        sys.exit(-1)


def stop_socket_servers(port):
    """Stop the socket servers running on the known ports (in case no port is given) or the given
    port"""
    ports = [int(port)] if port else socket_server_ports
    for p in ports:
        _stop_socket_server(p)
    # Reset the changes in the files regarding available external evaluators
    for rw_evaluator in rw_evaluators:
        _set_external_evaluator(rw_evaluator, 0)


def _get_socket_port(suite_name, start_port, current_batch):
    """Returns the used port based on the given parameters
    The same function is used in rw_example_experiment.py. If this one changes, the other has to
    change too.
    """
    port_py_inc = 200
    if ('toy-socket' in suite_name) or ('rw-top-trumps' in suite_name):
        return start_port + current_batch
    elif 'rw-mario-gan' in suite_name:
        return start_port + port_py_inc + current_batch
    else:
        raise ValueError('Suite {} not supported'.format(suite_name))


def test_socket(package_install_option=[], args=[]):
    """Test the given suite that uses sockets for evaluation ('toy-socket' by default).

    First run the socket server, then the real-world example experiment in Python and finally stop
    the socket server.
    """
    # These defaults should match those from rw_example_experiment.py
    suite_name = 'toy-socket'
    current_batch = 1
    port = start_port = 7000
    try:
        # Parse the arguments
        for arg in args:
            if arg[:11] == 'start_port=':
                start_port = arg[5:]
            elif arg[:6] == 'batch=':
                current_batch = bool(arg[6:])
            elif arg[:6] == 'suite=':
                suite_name = bool(arg[6:])
        # Get the right port for this suite
        port = _get_socket_port(suite_name, start_port, current_batch)
        # Build and run the right socket server for this suite
        if 'toy-socket' in suite_name:
            run_toy_socket_server_c(port=port)
        elif 'rw-top-trumps' in suite_name:
            run_rw_top_trumps_server(port=port)
        elif 'rw-mario-gan' in suite_name:
            run_rw_mario_gan_server(port=port)
        else:
            raise ValueError('Suite {} not supported'.format(suite_name))
        # Build Python and run the real-world example experiment with the given arguments
        build_python(package_install_option=package_install_option)
        python(os.path.join('code-experiments', 'build', 'python'),
               ['rw_example_experiment.py'] + args)
    finally:
        # Stop the socket servers
        stop_socket_servers(port=port)


################################################################################
## Post processing
def test_postprocessing(all_tests=False, package_install_option=[]):
    install_postprocessing(package_install_option=package_install_option)
    try:
        if all_tests:
            # run example experiment to have a recent data set to postprocess:
            build_python(package_install_option=package_install_option)
            python('code-experiments/build/python/', ['-c', '''
from __future__ import print_function
try:
    import example_experiment as ee
except Exception as e:
    print(e)
ee.SOLVER = ee.random_search  # which is default anyway
for ee.suite_name, ee.observer_options['result_folder'] in [
        ["bbob-biobj", "RS-bi"],  # use a short path for Jenkins
        ["bbob", "RS-bb"],
        ["bbob-constrained", "RS-co"],
        ["bbob-largescale", "RS-la"],
        ["bbob-mixint", "RS-mi"],
        ["bbob-biobj-mixint", "RS-bi-mi"]
    ]:
    print("  suite %s" % ee.suite_name, end=' ')  # these prints are swallowed
    if ee.suite_name in ee.cocoex.known_suite_names:
        print("testing into folder %s" % ee.observer_options['result_folder'])
        ee.main()
    else:
        print("is not known")
                '''], verbose=_verbosity)
            # now run all tests
            python('code-postprocessing/cocopp',
                   ['test.py', 'all', sys.executable], verbose=_verbosity)
        else:
            python('code-postprocessing/cocopp', ['test.py', sys.executable],
                   verbose=_verbosity)
        
        # also run the doctests in aRTAplots/generate_aRTA_plot.py:
        python('code-postprocessing/aRTAplots', ['generate_aRTA_plot.py'], verbose=_verbosity)
    except subprocess.CalledProcessError:
        sys.exit(-1)
    finally:
        # always remove folder of previously run experiments:
        for s in ['bi', 'bb', 'co', 'la', 'mi', 'bi-mi']:
            shutil.rmtree('code-experiments/build/python/exdata/RS-' + s,
                          ignore_errors=True)

def verify_postprocessing(package_install_option=[]):
    install_postprocessing(package_install_option=package_install_option)
    # This is not affected by the _verbosity value. Verbose should always be True.
    python('code-postprocessing/cocopp', ['preparehtml.py', '-v'], verbose=True)


################################################################################
## Pre-processing
def install_preprocessing(package_install_option=[]):
    global RELEASE
    expand_file(join('code-preprocessing/archive-update', 'setup.py.in'),
                join('code-preprocessing/archive-update', 'setup.py'),
                {'COCO_VERSION': git_version(pep440=True)})
    build_python(package_install_option=package_install_option)
    amalgamate(CORE_FILES + ['code-experiments/src/coco_runtime_c.c'],
               'code-preprocessing/archive-update/interface/coco.c', RELEASE,
               {"COCO_VERSION": git_version(pep440=True)})
    expand_file('code-experiments/src/coco.h', 'code-preprocessing/archive-update/interface/coco.h',
                {'COCO_VERSION': git_version(pep440=True)})
    python('code-preprocessing/archive-update',
           ['setup.py', 'install'] + package_install_option,
           verbose=_verbosity, custom_exception_handler=install_error)


def test_preprocessing(package_install_option=[]):
    install_preprocessing(package_install_option=package_install_option)
    python('code-preprocessing/archive-update', ['-m', 'pytest'], verbose=_verbosity)
    python('code-preprocessing/log-reconstruction', ['-m', 'pytest'], verbose=_verbosity)

################################################################################
## Global
def build(package_install_option=[]):
    builders = [
        build_c,
        # build_matlab,
        build_python(package_install_option=package_install_option),
        build_java,
    ]
    for builder in builders:
        try:
            builder()
        except:
            failed = str(builder)
            print("============")
            print('   ERROR: %s failed, call "./do.py %s" individually'
                  % (failed, failed[failed.find('build_'):].split()[0]) +
                  ' for a more detailed error report')
            print("============")


def run_all(package_install_option=[]):
    run_c()
    run_java()
    run_python(package_install_option=package_install_option)


def test():
    test_c()
    test_java()
    test_python()


def verbose(args):
    """Calls main(args) in verbose mode for additional output"""
    global _verbosity
    _verbosity = True
    main(args)
    _verbosity = False

def quiet(args):
    """Calls main(args) in quiet mode for less output during c builds"""
    global _build_verbosity
    _build_verbosity = False
    main(args)
    _build_verbosity = True

def silent(args):
    """calls `main(args)` with redirected output to keep the console clean"""
    # redirect stdout and call main
    filename = '_check_output'
    raised = None
    stdout = sys.stdout

    with open(filename, 'w') as out:
        sys.stdout = out
        try:
            main(args)
        except BaseException as raised:
            pass
    sys.stdout = stdout

    # check whether an error occured
    error = False
    for line in open(filename, 'r').readlines():
        if line.startswith('ERR') or not line[0] in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            error = True
            break
    if error:
        for line in open(filename, 'r').readlines():
            print(line, end="")
    if raised:
        raise raised


def help():
    print("""COCO framework bootstrap tool. Version %s

Usage: do.py <command> <arguments>

If you want to get going as quickly as possible do once

   python do.py run-<your-language>

and

    python do.py install-postprocessing

and you are all set.

Available commands for users:

  build-c                 - Build C module
  build-java              - Build Java module
  build-matlab            - Build Matlab module
  build-matlab-sms        - Build SMS-EMOA example in Matlab
  build-octave            - Build Matlab module in Octave
  build-python            - Build Python modules (see NOTE below)
  install-postprocessing  - Install postprocessing (see NOTE below)

  run-c                   - Build and run example experiment in C
  run-java                - Build and run example experiment in Java
  run-matlab              - Build and run example experiment in MATLAB
  run-matlab-sms          - Build and run SMS-EMOA on bbob-biobj suite in
                            MATLAB
  run-octave              - Build and run example experiment in Octave
  run-python              - Build and install COCO module and then run the
                            example experiment in Python. The optional
                            parameter "and-test" also runs the tests of
                            `coco_test.py` (see NOTE below)
                            
  build-toy-socket-server-c      - Build the toy socket server in C
  build-toy-socket-server-python - Build the toy socket server in Python
  build-rw-top-trumps-server     - Build the rw_top_trumps server (will download data if not yet present) 
  build-rw-mario-gan-server      - Build the rw_mario_gan server (will download data if not yet present) 
  build-socket-servers           - Build all the available servers (will download data if not yet present) 

  run-toy-socket-server-c        - Build and run the toy socket server in C
  run-toy-socket-server-python   - Build and run the toy socket server in Python
  run-rw-top-trumps-server       - Build and run the rw_top_trumps server (will download data if not yet present) 
  run-rw-mario-gan-server        - Build and run the rw_mario_gan server (will download data if not yet present)  
  run-socket-servers             - Build and run all socket servers (will download data if not yet present) 
  stop-socket-servers            - Stop all running socket servers

Available commands for developers:

  build                   - Build C, Java and Python modules (see NOTE below)
  run                     - Run example experiments in C, Java and Python (see
                            NOTE below)
  silent cmd ...          - Calls "do.py cmd ..." and remains silent if no
                            error occurs
  verbose cmd ...         - Calls "do.py cmd ..." and shows more output
  test                    - Test C, Java and Python modules (see NOTE below)

  run-sandbox-python      - Run a Python script with installed COCO module
                            Takes a single argument(name of Python script file)

  test-c                  - Build and run unit tests, integration tests
                            and an example experiment test in C
  test-c-unit             - Build and run unit tests in C
  test-c-integration      - Build and run integration tests in C
  test-c-example          - Build and run an example experiment test in C
  test-java               - Build and run a test in Java
  test-python             - Build and run minimal test of Python module
  test-octave             - Build and run example experiment in Octave
  test-postprocessing     - Runs some of the post-processing tests (see NOTE
                            below)
  test-postprocessing-all - Runs all of the post-processing tests [needs access
                            to the internet] (see NOTE below)
  test-suites             - Runs regression test on all benchmark suites
  verify-postprocessing   - Checks if the generated html is up-to-date (see
                            NOTE below)
  leak-check              - Check for memory leaks in C
  
  install-preprocessing   - Install preprocessing (user-locally) (see NOTE
                            below)
  test-preprocessing      - Runs preprocessing tests [needs access to the
                            internet] (see NOTE below)
                            
  test-toy-socket         - Tests the toy-socket suite (server in C and experiment in Python)
  
NOTE: These commands install Python packages to the global site packages by
      by default. This behavior can be modified by providing one of the
      following arguments.
  
       install-user       - Installs under the user directory
       install-home=<dir> - Installs under the specified home directory

To build a release version which does not include debugging information in the
amalgamations set the environment variable COCO_RELEASE to 'true'.
""" % git_version(pep440=True))


def main(args):
    if len(args) < 1:
        help()
        sys.exit(0)
    cmd = args[0].replace('_', '-').lower()
    also_test_python = False
    package_install_option = []
    port = None
    force_rw_download = False  # Whether to force download of the data of the real-world problems
    for arg in args[1:]:
        if arg == 'and-test':
            also_test_python = True
        elif arg in ('install-user', '--user'):
            package_install_option = ['--user']
        elif arg[:13] == 'install-home=':
            package_install_option = ['--home=' + arg[13:]]
        elif arg[:5] == 'port=':
            port = arg[5:]
        elif arg[:18] == 'force-rw-download=':
            force_rw_download = bool(arg[18:])
    if cmd == 'build': build(package_install_option=package_install_option)
    elif cmd == 'run': run_all(package_install_option=package_install_option)
    elif cmd == 'test': test()
    elif cmd == 'build-c': build_c()
    elif cmd == 'build-java': build_java()
    elif cmd == 'build-matlab': build_matlab()
    elif cmd == 'build-matlab-sms': build_matlab_sms()
    elif cmd == 'build-octave': build_octave()
    elif cmd == 'build-octave-sms': build_octave_sms()
    elif cmd == 'build-python': build_python(package_install_option=package_install_option)
    elif cmd == 'install-postprocessing': install_postprocessing(package_install_option=package_install_option)
    elif cmd == 'run-c': run_c()
    elif cmd == 'run-java': run_java()
    elif cmd == 'run-matlab': run_matlab()
    elif cmd == 'run-matlab-sms': run_matlab_sms()
    elif cmd == 'run-octave': run_octave()
    elif cmd == 'run-octave-sms': run_octave_sms()
    elif cmd == 'run-python': run_python(also_test_python, package_install_option=package_install_option)
    elif cmd == 'quiet': quiet(args[1:])
    elif cmd == 'silent': silent(args[1:])
    elif cmd == 'verbose': verbose(args[1:])
    elif cmd == 'test-c': test_c()
    elif cmd == 'test-c-unit': test_c_unit()
    elif cmd == 'test-c-integration': test_c_integration()
    elif cmd == 'test-c-example': test_c_example()
    elif cmd == 'test-java': test_java()
    elif cmd == 'test-python': test_python()
    elif cmd == 'test-octave': test_octave()
    elif cmd == 'test-postprocessing': test_postprocessing(all_tests=False, package_install_option=package_install_option)
    elif cmd == 'test-postprocessing-all': test_postprocessing(all_tests=True, package_install_option=package_install_option)
    elif cmd == 'test-suites': test_suites(args[1:])
    elif cmd == 'verify-postprocessing': verify_postprocessing(package_install_option=package_install_option)
    elif cmd == 'leak-check': leak_check()
    elif cmd == 'install-preprocessing': install_preprocessing(package_install_option=package_install_option)
    elif cmd == 'test-preprocessing': test_preprocessing(package_install_option=package_install_option)
    elif cmd == 'build-toy-socket-server-c': build_toy_socket_server_c()
    elif cmd == 'build-toy-socket-server-python': build_toy_socket_server_python()
    elif cmd == 'build-rw-top-trumps-server': build_rw_top_trumps_server(force_download=force_rw_download)
    elif cmd == 'build-rw-mario-gan-server': build_rw_mario_gan_server(force_download=force_rw_download)
    elif cmd == 'build-socket-servers': build_socket_servers(force_download=force_rw_download)
    elif cmd == 'run-toy-socket-server-c': run_toy_socket_server_c(port=port)
    elif cmd == 'run-toy-socket-server-python': run_toy_socket_server_python(port=port)
    elif cmd == 'run-rw-top-trumps-server': run_rw_top_trumps_server(port=port, force_download=force_rw_download)
    elif cmd == 'run-rw-mario-gan-server': run_rw_mario_gan_server(port=port, force_download=force_rw_download)
    elif cmd == 'run-socket-servers': run_socket_servers(force_download=force_rw_download)
    elif cmd == 'stop-socket-servers': stop_socket_servers(port=port)
    elif cmd == 'test-socket': test_socket(package_install_option=package_install_option, args=args[1:])
    else: help()


if __name__ == '__main__':
    RELEASE = os.getenv('COCO_RELEASE', 'false') == 'true'
    main(sys.argv[1:])
