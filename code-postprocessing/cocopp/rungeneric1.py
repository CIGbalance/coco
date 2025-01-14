#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Module for post-processing the data of one algorithm.

Calls the function main with arguments from the command line. Executes
the postprocessing on the given files and folders arguments, using the
:file:`.info` files found recursively.

Synopsis:
    ``python -m cocopp.rungeneric1 [OPTIONS] FOLDER``

Help:
    ``python -m cocopp.rungeneric1 --help``

"""

from __future__ import absolute_import
from __future__ import print_function

import os, sys
from pdb import set_trace
import matplotlib

import warnings, getopt, numpy as np

from . import genericsettings, testbedsettings, ppfig, pptable, pprldistr, ppfigdim, pplogloss, findfiles
from .pproc import DataSetList, store_reference_values, dictAlgByDim
from .ppfig import Usage
from .toolsdivers import print_done, prepend_to_file, strip_pathname1, str_to_latex, get_version_label, replace_in_file
from . import ppconverrorbars
from .compall import pprldmany, ppfigs

import matplotlib.pyplot as plt

__all__ = ['main']


def usage():
    print(main.__doc__)

def main(argv=None):
    r"""Post-processing COCO data of a single algorithm.

    Provided with some data, this routine outputs figure and TeX files
    in a folder needed for the compilation of the provided LaTeX templates
    for one algorithm (``*article.tex`` or ``*1*.tex``).
    The used template file needs to be edited so that the commands
    ``\bbobdatapath`` and ``\algfolder`` point to the output folder created
    by this routine.

    These output files will contain performance tables, performance
    scaling figures and empirical cumulative distribution figures. On
    subsequent executions, new files will be added to the output folder,
    overwriting existing older files in the process.

    Keyword arguments:

    *argv* -- list of strings containing options and arguments. If not
    given, sys.argv is accessed.

    *argv* should list either names of :file:`info` files or folders
    containing :file:`info` files. argv can also contain post-processed
    :file:`pickle` files generated by this routine. Furthermore, *argv*
    can begin with, in any order, facultative option flags listed below.

        -h, --help
            displays this message.
        -v, --verbose
            verbose mode, prints out all operations.
        -p, --pickle
            generates pickle post processed data files.
        -o OUTPUTDIR, --output-dir=OUTPUTDIR
            changes the default output directory (:file:`ppdata`) to
            :file:`OUTPUTDIR`.
        --crafting-effort=VALUE
            sets the crafting effort to VALUE (float). Otherwise the
            default value of 0. will be used.
        --noise-free, --noisy
            processes only part of the data.
        --settings=SETTINGS
            changes the style of the output figures and tables. At the
            moment the only differences are  in the colors of the output
            figures. SETTINGS can be either "grayscale" or "color".
            The default setting is "color".
        --tab-only, --fig-only, --rld-only, --los-only
            these options can be used to output respectively the TeX
            tables, convergence and aRTs graphs figures, run length
            distribution figures, aRT loss ratio figures only. A
            combination of any two of these options results in no
            output.
        --conv
            if this option is chosen, additionally convergence plots
            for each function and algorithm are generated.
        --no-rld-single-fcts
            do not generate runlength distribution figures for each
            single function.
        --expensive
            runlength-based f-target values and fixed display limits,
            useful with comparatively small budgets.
        --no-svg
            do not generate the svg figures which are used in html files
        --runlength-based
            runlength-based f-target values, such that the
            "level of difficulty" is similar for all functions. 

    Exceptions raised:

    *Usage* -- Gives back a usage message.

    Examples:

    * Calling the rungeneric1.py interface from the command line::

        $ python -m cocopp.rungeneric1 -v experiment1

      will post-process the folder experiment1 and all its containing
      data, base on the .info files found in the folder. The result will
      appear in the default output folder. The -v option adds verbosity. ::

        $ python -m cocopp.rungeneric1 -o exp2 experiment2/*.info

      This will execute the post-processing on the info files found in
      :file:`experiment2`. The result will be located in the alternative
      location :file:`exp2`.

    * Loading this package and calling the main from the command line
      (requires that the path to this package is in python search path)::

        $ python -m cocopp.rungeneric1 -h

      This will print out this help message.

    * From the python interpreter (requires that the path to this
      package is in python search path; most simply achieved by running
      `python do.py install-postprocessing`)::

        >> import cocopp
        >> cocopp.rungeneric1.main('-o outputfolder folder1'.split())

      This will execute the post-processing on the index files found in
      :file:`folder1`. The ``-o`` option changes the output folder from
      the default to :file:`outputfolder`.

    """

    if argv is None:
        argv = sys.argv[1:]
        # The zero-th input argument which is the name of the calling script is
        # disregarded.

    if 1 < 3:
        opts, args = getopt.getopt(argv, genericsettings.shortoptlist, genericsettings.longoptlist)
        if 11 < 3:
            try:
                opts, args = getopt.getopt(argv, genericsettings.shortoptlist, genericsettings.longoptlist)
            except getopt.error as msg:
                raise Usage(msg)

        if not (args) and not '--help' in argv and not '-h' in argv:
            print('not enough input arguments given')
            print('cave: the following options also need an argument:')
            print([o for o in genericsettings.longoptlist if o[-1] == '='])
            print('options given:')
            print(opts)
            print('try --help for help')
            sys.exit()

        # Process options
        outputdir = genericsettings.outputdir
        prepare_RLDistr = genericsettings.isRLDistr
        prepare_figures = genericsettings.isFig
        prepare_tables = genericsettings.isTab
        prepare_log_loss = genericsettings.isLogLoss

        for o, a in opts:
            if o in ("-v", "--verbose"):
                genericsettings.verbose = True
            elif o in ("-h", "--help"):
                usage()
                sys.exit()
            elif o in ("-p", "--pickle"):
                genericsettings.isPickled = True
            elif o in ("-o", "--output-dir"):
                outputdir = a
            elif o == "--noisy":
                genericsettings.isNoisy = True
            elif o == "--noise-free":
                genericsettings.isNoiseFree = True
            # The next 4 are for testing purpose
            elif o == "--tab-only":
                prepare_figures = False
                prepare_RLDistr = False
                prepare_log_loss = False
            elif o == "--fig-only":
                prepare_tables = False
                prepare_RLDistr = False
                prepare_log_loss = False
            elif o == "--rld-only":
                prepare_tables = False
                prepare_figures = False
                prepare_log_loss = False
            elif o == "--los-only":
                prepare_tables = False
                prepare_figures = False
                prepare_RLDistr = False
            elif o == "--crafting-effort":
                try:
                    genericsettings.inputCrE = float(a)
                except ValueError:
                    raise Usage('Expect a valid float for flag crafting-effort.')
            elif o == "--settings":
                genericsettings.inputsettings = a
            elif o == "--conv":
                genericsettings.isConv = True
            elif o == "--no-rld-single-fcts":
                genericsettings.isRldOnSingleFcts = False
            elif o == "--runlength-based":
                genericsettings.runlength_based_targets = True
            elif o == "--expensive":
                genericsettings.isExpensive = True  # comprises runlength-based
            elif o == "--no-svg":
                genericsettings.generate_svg_files = False
            elif o == "--sca-only":
                warnings.warn("option --sca-only will have no effect with rungeneric1.py")
            else:
                assert False, "unhandled option"

        # from cocopp import bbob2010 as inset # input settings
        from . import genericsettings as inset  # input settings
        if genericsettings.inputsettings == "color":
            from . import genericsettings as inset  # input settings
        elif genericsettings.inputsettings == "grayscale":
            warnings.warn("grayscalesettings disregarded")
        elif genericsettings.inputsettings == "black-white":
            warnings.warn("black-white bwsettings disregarded")
        else:
            txt = ('Settings: %s is not an appropriate ' % genericsettings.inputsettings
                   + 'argument for input flag "--settings".')
            raise Usage(txt)
        
        if 11 < 3:
            from . import config  # input settings
            config.config()
            import imp
            # import testbedsettings as testbedsettings # input settings
            try:
                fp, pathname, description = imp.find_module("testbedsettings")
                testbedsettings1 = imp.load_module("testbedsettings", fp, pathname, description)
            finally:
                fp.close()

        if (not genericsettings.verbose):
            warnings.simplefilter('module')
            # warnings.simplefilter('ignore')            

        # Gets directory name if outputdir is a archive file.
        algfolder = findfiles.get_output_directory_sub_folder(args[0])
        algoutputdir = os.path.join(outputdir, algfolder)
        
        print("\nPost-processing (1)")

        filelist = list()
        for i in args:
            i = i.strip()
            if os.path.isdir(i):
                filelist.extend(findfiles.main(i))
            elif os.path.isfile(i):
                filelist.append(i)
            else:
                txt = 'Input file or folder %s could not be found.' % i
                print(txt)
                raise Usage(txt)
        dsList = DataSetList(filelist)
        
        if not dsList:
            raise Usage("Nothing to do: post-processing stopped. For more information check the messages above.")

        print("  Will generate output data in folder %s" % algoutputdir)
        print("    this might take several minutes.")
        
        if genericsettings.isNoisy and not genericsettings.isNoiseFree:
            dsList = dsList.dictByNoise().get('nzall', DataSetList())
        if genericsettings.isNoiseFree and not genericsettings.isNoisy:
            dsList = dsList.dictByNoise().get('noiselessall', DataSetList())

        store_reference_values(dsList)

        # compute maxfuneval values
        dict_max_fun_evals = {}
        for ds in dsList:
            dict_max_fun_evals[ds.dim] = np.max((dict_max_fun_evals.setdefault(ds.dim, 0), float(np.max(ds.maxevals))))
        
        from . import config
        config.config_target_values_setting(genericsettings.isExpensive,
                                            genericsettings.runlength_based_targets)
        config.config(dsList[0].testbed_name)
        if genericsettings.verbose:
            for i in dsList:                
                # check whether current set of instances correspond to correct
                # setting of a BBOB workshop and issue a warning otherwise:            
                curr_instances = (dict((j, i.instancenumbers.count(j)) for j in set(i.instancenumbers)))
                correct = False
                for instance_set_of_interest in inset.instancesOfInterest:
                    if curr_instances == instance_set_of_interest:
                        correct = True
                if not correct:
                    warnings.warn('The data of %s do not list ' % i +
                                  'the correct instances ' +
                                  'of function F%d.' % i.funcId)

        dictAlg = dsList.dictByAlg()

        if len(dictAlg) > 1:
            warnings.warn('Data with multiple algId %s ' % str(dictAlg.keys()) +
                          'will be processed together.')
            # TODO: in this case, all is well as long as for a given problem
            # (given dimension and function) there is a single instance of
            # DataSet associated. If there are more than one, the first one only
            # will be considered... which is probably not what one would expect.

        if prepare_figures or prepare_tables or prepare_RLDistr or prepare_log_loss:
            if not os.path.exists(outputdir):
                os.makedirs(outputdir)
                if genericsettings.verbose:
                    print('Folder %s was created.' % (outputdir))
            if not os.path.exists(algoutputdir):
                os.makedirs(algoutputdir)
                if genericsettings.verbose:
                    print('Folder %s was created.' % (algoutputdir))

        latex_commands_file = os.path.join(outputdir, 'cocopp_commands.tex')

        if genericsettings.isPickled:
            dsList.pickle()

        dictFunc = dsList.dictByFunc()
        if dictFunc[list(dictFunc.keys())[0]][0].algId not in ("", "ALG"):
            algorithm_string = " for Algorithm %s" % dictFunc[list(dictFunc.keys())[0]][0].algId
        else:
            algorithm_string = ""
        page_title = 'Results%s on the <TT>%s</TT> Benchmark Suite' % \
                     (algorithm_string, dictFunc[list(dictFunc.keys())[0]][0].get_suite())
        ppfig.save_single_functions_html(os.path.join(algoutputdir, genericsettings.single_algorithm_file_name),
                                         page_title,
                                         htmlPage=ppfig.HtmlPage.ONE,
                                         function_groups=dsList.getFuncGroups())

        values_of_interest = testbedsettings.current_testbed.ppfigdim_target_values
        if prepare_figures:
            print("Scaling figures...")
            # aRT/dim vs dim.
            plt.rc("axes", **inset.rcaxeslarger)
            plt.rc("xtick", **inset.rcticklarger)
            plt.rc("ytick", **inset.rcticklarger)
            plt.rc("font", **inset.rcfontlarger)
            plt.rc("legend", **inset.rclegendlarger)
            plt.rc('pdf', fonttype = 42)

            ppfigdim.main(dsList, values_of_interest, algoutputdir)

            plt.rcdefaults()
            print_done()

        plt.rc("axes", **inset.rcaxes)
        plt.rc("xtick", **inset.rctick)
        plt.rc("ytick", **inset.rctick)
        plt.rc("font", **inset.rcfont)
        plt.rc("legend", **inset.rclegend)
        plt.rc('pdf', fonttype = 42)

        if genericsettings.isConv:
            print("Generating convergence plots...")
            ppconverrorbars.main(dictAlg,
                                 algoutputdir,
                                 genericsettings.single_algorithm_file_name)
            print_done()

        if prepare_tables:
            print("Generating LaTeX tables...")
            dictNoise = dsList.dictByNoise()
            dict_dim_list = dictAlgByDim(dictAlg)
            dims = sorted(dict_dim_list)

            ppfig.save_single_functions_html(
                os.path.join(algoutputdir, 'pptable'),
                dimensions=dims,
                htmlPage=ppfig.HtmlPage.PPTABLE,
                parentFileName=genericsettings.single_algorithm_file_name)
            replace_in_file(os.path.join(algoutputdir, 'pptable.html'), '??COCOVERSION??',
                            '<br />Data produced with COCO %s' % (get_version_label(None)))

            for noise, sliceNoise in dictNoise.items():
                pptable.main(sliceNoise, dims, algoutputdir, latex_commands_file)
            print_done()

        if prepare_RLDistr:
            print("ECDF graphs...")
            dictNoise = dsList.dictByNoise()
            if len(dictNoise) > 1:
                warnings.warn('Data for functions from both the noisy and '
                              'non-noisy testbeds have been found. Their '
                              'results will be mixed in the "all functions" '
                              'ECDF figures.')
            dictDim = dsList.dictByDim()
            for dim in testbedsettings.current_testbed.rldDimsOfInterest:
                try:
                    sliceDim = dictDim[dim]
                except KeyError:
                    continue

                dictNoise = sliceDim.dictByNoise()

                # If there is only one noise type then we don't need the all graphs.
                if len(dictNoise) > 1:
                    pprldistr.main(sliceDim, True, algoutputdir, 'all')
                    
                for noise, sliceNoise in dictNoise.items():
                    pprldistr.main(sliceNoise, True, algoutputdir, '%s' % noise)

                dictFG = sliceDim.dictByFuncGroup()
                for fGroup, sliceFuncGroup in sorted(dictFG.items()):
                    pprldistr.main(sliceFuncGroup, True,
                                   algoutputdir,
                                   '%s' % fGroup)

                pprldistr.fmax = None  # Resetting the max final value
                pprldistr.evalfmax = None  # Resetting the max #fevalsfactor
            print_done()

            if genericsettings.isRldOnSingleFcts: # copy-paste from above, here for each function instead of function groups
                # ECDFs for each function
                print("ECDF graphs per function...")
                pprldmany.all_single_functions(dictAlg, 
                                               True,
                                               None,
                                               algoutputdir,
                                               genericsettings.single_algorithm_file_name,
                                               settings=inset)
                print_done()
            
        if prepare_log_loss:
            print("aRT loss ratio figures and tables...")
            for ng, sliceNoise in dsList.dictByNoise().items():
                if ng == 'noiselessall':
                    testbed = 'noiseless'
                elif ng == 'nzall':
                    testbed = 'noisy'
                txt = ("Please input crafting effort value "
                       + "for %s testbed:\n  CrE = " % testbed)
                CrE = genericsettings.inputCrE
                while CrE is None:
                    try:
                        CrE = float(raw_input(txt))
                    except (SyntaxError, NameError, ValueError):
                        print("Float value required.")
                dictDim = sliceNoise.dictByDim()
                for d in testbedsettings.current_testbed.rldDimsOfInterest:
                    try:
                        sliceDim = dictDim[d]
                    except KeyError:
                        continue
                    info = '%s' % ng
                    pplogloss.main(sliceDim, CrE, True, algoutputdir, info)
                    pplogloss.generateTable(sliceDim, CrE, algoutputdir, info)
                    for fGroup, sliceFuncGroup in sliceDim.dictByFuncGroup().items():
                        info = '%s' % fGroup
                        pplogloss.main(sliceFuncGroup, CrE, True,
                                       algoutputdir, info)
            print_done()

        prepend_to_file(latex_commands_file,
                        ['\\providecommand{\\bbobloglosstablecaption}[1]{',
                         pplogloss.table_caption(), '}'])
        prepend_to_file(latex_commands_file,
                        ['\\providecommand{\\bbobloglossfigurecaption}[1]{',
                         pplogloss.figure_caption(), '}'])
        prepend_to_file(latex_commands_file,
                        ['\\providecommand{\\bbobpprldistrlegend}[1]{',
                         pprldistr.caption_single(),  # depends on the config setting, should depend on maxfevals
                         '}'])
        # html_file = os.path.join(outputdir, 'pprldistr.html') # remove this line???
        prepend_to_file(latex_commands_file,
                        ['\\providecommand{\\bbobppfigdimlegend}[1]{',
                         ppfigdim.scaling_figure_caption(),
                         '}'])
        prepend_to_file(latex_commands_file,
                        ['\\providecommand{\\bbobpptablecaption}[1]{',
                         pptable.get_table_caption(),
                         '}'])
        prepend_to_file(latex_commands_file,
                        ['\\providecommand{\\bbobecdfcaptionsinglefcts}[2]{',
                         ppfigs.get_ecdfs_single_fcts_caption(),
                         '}'])
        prepend_to_file(latex_commands_file,
                        ['\\providecommand{\\bbobecdfcaptionallgroups}[1]{',
                         ppfigs.get_ecdfs_all_groups_caption(),
                         '}'])
        prepend_to_file(latex_commands_file,
                        ['\\providecommand{\\algfolder}{' + algfolder + '/}'])
        prepend_to_file(latex_commands_file,
                        ['\\providecommand{\\algname}{' + 
                         (str_to_latex(strip_pathname1(args[0])) if len(args) == 1 else str_to_latex(dsList[0].algId)) + '{}}'])
        print("Output data written to folder %s" %
              os.path.join(os.getcwd(), algoutputdir))

        plt.rcdefaults()

        return dsList.dictByAlg()
