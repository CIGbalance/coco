#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Raw post-processing routines.

This module implements class :py:class:`DataSet`, unit element in the
post-processing and class :py:class:`DataSetList`, sequence of instances
of :py:class:`DataSet`.

Futhermore it implements methods for dealing with a third data structure
which is a dictionary of :py:class:`DataSetList` which is handy when
dealing with :py:class:`DataSetList` instances from multiple algorithms
for comparisons.

"""

# TODO: dictAlg should become the class DictALg that is a dictionary of DataSetLists with
# usecase DictAlg(algdict).by_dim() etc  

from __future__ import absolute_import, print_function

import sys
import os
import ast
import re
import pickle, gzip  # gzip is for future functionality: we probably never want to pickle without gzip anymore
import warnings
import json
import hashlib
import functools
import collections
from pdb import set_trace
from six import string_types, advance_iterator
import numpy, numpy as np
import matplotlib.pyplot as plt
from collections import OrderedDict
from . import genericsettings, findfiles, toolsstats, toolsdivers
from . import testbedsettings, dataformatsettings
from .readalign import split, align_data, HMultiReader, VMultiReader, openfile
from .readalign import HArrayMultiReader, VArrayMultiReader, alignArrayData
from .ppfig import consecutiveNumbers, Usage

do_assertion = genericsettings.force_assertions # expensive assertions
targets_displayed_for_info = [10, 1., 1e-1, 1e-3, 1e-5, 1e-8]  # only to display info in DataSetList.info
maximal_evaluations_only_to_last_target = False  # was true in release 13.03, leads naturally to better results


def _DataSet_complement_data(self, step=10**0.2, final_target=1e-8):
    """insert a line for each target value.

    To be resolved: old data sets don't have this method,
    therefore it must be global in the module

    """
    try:
        if self._is_complemeted_data:
            return
    except AttributeError:
        pass
    if step < 1:
        step = 1. / step
    assert step > 1
    
    # check that step splits 10 into uniform intervals on the log scale
    if np.abs(0.2 / np.log10(step) - np.round(0.2 / np.log10(step))) > 1e-11:
        print(np.log10(step))
        raise NotImplementedError('0.2 / log10(step) must be an integer to be compatible with previous data')

    i = 0
    newdat = []
    self.evals = np.array(self.evals, copy=False)
    for i in range(len(self.evals) - 1):
        newdat.append(self.evals[i])
        target = self.evals[i][0] / step
        while target >= final_target and target > self.evals[i+1][0] and target / self.evals[i+1][0] - 1 > 1e-9:
            newdat.append(self.evals[i+1])
            newdat[-1][0] = target
            target /= step
    newdat.append(self.evals[-1])
    
    # raise NotImplementedError('needs yet to be re-checked, tested, approved')  # check newdat and self.evals
    self.evals = np.array(newdat)  # for portfolios, self.evals is not an array
    assert np.max(np.abs(self.evals[:-1, 0] / self.evals[1:, 0] - 10**step)) < 1e-11
    self._is_complemented_data = True # TODO: will remain true forever, this needs to be set to False again somewhere? 

def cocofy(filename):
    """Replaces cocopp references in pickles files with coco_pproc
        This could become necessary for future backwards compatibility,
        however rather should become a class method. """
    import fileinput
    for line in fileinput.input(filename, inplace=1):
#       if "bbob" in line:
        sys.stdout.write(line.replace("bbob_pproc","cocopp"))
    fileinput.close()

# CLASS DEFINITIONS

def asTargetValues(target_values):
    if isinstance(target_values, TargetValues):
        return target_values
    if isinstance(target_values, list):
        return TargetValues(target_values)
    try:
        isinstance(target_values((1, 20)), list)
        return target_values
    except:
        raise NotImplementedError("""type %s not recognized""" %
                                  str(type(target_values)))
class TargetValues(object):
    """store and retrieve a list of target function values:

        >>> import numpy as np
        >>> import cocopp.pproc as pp
        >>> targets = [10**i for i in np.arange(2, -8.1, -0.2)]
        >>> targets_as_class = pp.TargetValues(targets)
        >>> assert targets_as_class() == targets
    
    In itself this class is useless, as it does not more than a simple list
    could do, but it serves as interface for derived classes, where ``targets()``
    requires an actual argument ``targets(fun_dim)``. 
    
    Details: The optional argument for calling the class instance is needed to 
    be consistent with the derived ``class RunlengthBasedTargetValues``. 
    
    """
    def __init__(self, target_values, discretize=None):
        if 11 < 3 and isinstance(target_values, TargetValues):  # type cast passing behavior
            return self  # caveat: one might think a copy should be made
            self.__dict__ = target_values.__dict__  # this is not a copy
            return
        self.target_values = sorted(target_values, reverse=True)
        if discretize:
            self.target_values = self._discretize(self.target_values)
        self._short_info = "absolute targets"

    @property
    def short_info(self):
        return self._short_info

    @staticmethod
    def cast(target_values_or_class_instance, *args, **kwargs):
        """idempotent cast to ``TargetValues`` class type, specifically
        ``return TargetValues(target_values_or_class_instance) 
            if not isinstance(target_values_or_class_instance, TargetValues) 
            else target_values_or_class_instance`` 
            
        """
        if isinstance(target_values_or_class_instance, TargetValues):
            return target_values_or_class_instance
        else:
            return TargetValues(target_values_or_class_instance, *args, **kwargs)

    def __len__(self):
        return len(self.target_values)

    def __call__(self, fun_dim_but_not_use=None, discretize=None):
        if discretize:
            return self._discretize(self.target_values)
        return self.target_values
    @staticmethod
    def _discretize(target_list):
        """return a "similar" list with targets in [10**i/5]
        """
        number_per_magnitude = 5  # will become input arg if needed
        factor = float(number_per_magnitude)
        return [10**(np.round(factor * np.log10(t)) / factor)
                for t in target_list]
    def label(self, i):
        """return the ``i``-th target value as ``str``, to be overwritten by a derived class"""
        return toolsdivers.num2str(self.target_values[i], significant_digits=2)

    def loglabel(self, i, decimals=0):
        """return ``log10`` of the ``i``-th target value as ``str``, to be overwritten by a derived class"""
        # return str(int(np.round(np.log10(self.target_values[i]), decimals)))
        return toolsdivers.num2str(np.log10(self.target_values[i]), significant_digits=decimals+1)

    def labels(self):
        """target values as a list of ``str``"""
        i, res = 0, []
        try:
            while True:
                res.append(self.label(i))
                i += 1
        except IndexError:
            return res
 
    def loglabels(self, decimals=0):
        """``log10`` of the target values as a list of ``str``"""
        i, res = 0, []
        try:
            while True:
                res.append(self.loglabel(i, decimals))
                i += 1
        except IndexError:
            return res

    def label_name(self):
        return 'Df'

class RunlengthBasedTargetValues(TargetValues):
    """a class instance call returns f-target values based on 
    reference runlengths:
    
        >>> import cocopp
        >>> # make sure to use the right `bbob` test suite for the test below:
        >>> cocopp.genericsettings.isNoisy = False
        >>> cocopp.genericsettings.isNoiseFree = False
        >>> cocopp.config.config('GECCOBBOBTestbed')
        >>> targets = cocopp.pproc.RunlengthBasedTargetValues([0.5, 1.2, 3, 10, 50])  # by default times_dimension==True
        >>> # make also sure to have loaded the corresponding reference algo
        >>> # from BBOB-2009:
        >>> targets.reference_data = 'testbedsettings'
        >>> t = targets(fun_dim=(1, 20)) # doctest:+ELLIPSIS
        Loading best algorithm data from ...
        >>> assert 6.30957345e+01 <= t[0] <= 6.30957346e+01
        >>> assert t[-1] == 1.00000000e-08
             
    returns a list of target f-values for F1 in 20-D, based on the 
    aRT values ``[0.5,...,50]``. 
        
    Details: The computation starts from the smallest budget and the resulting f-target 
    must always be at least a factor of ``force_different_targets_factor`` smaller 
    than the previous one. If the ``smallest_target`` is superseded, the log values
    are linearly rescaled such that the easiest found target remains the same and 
    the smallest target becomes ``smallest_target``. 
    
    TODO: see compall/determineFtarget2.FunTarget
    
    """
    @staticmethod
    def cast(run_lengths_or_class_instance, *args, **kwargs):
        """idempotent cast to ``RunlengthBasedTargetValues`` class type"""
        if isinstance(run_lengths_or_class_instance, RunlengthBasedTargetValues):
            return run_lengths_or_class_instance
        else:
            return RunlengthBasedTargetValues(run_lengths_or_class_instance, *args, **kwargs)
        
    def __init__(self, run_lengths, reference_data='testbedsettings',
                 smallest_target=1e-8, times_dimension=True, 
                 force_different_targets_factor=10**0.04,
                 unique_target_values=False,
                 step_to_next_difficult_target=10**0.2):
        """calling the class instance returns run-length based
        target values based on the reference data, individually
        computed for a given ``(funcId, dimension)``. 
        
        :param run_lengths: sequence of values. 
        :param reference_data: 
            can be a string indicating the filename of a reference algorithm
            data set such as ``"refalgs/best2009-bbob.tar.gz"`` or a dictionary
            of best data sets (e.g. from ``bestalg.generate(...)``)
            or a list of algorithm folder/data names (not thoroughly
            tested). If chosen as ``testbedsettings``, the reference algorithm
            specified in testbedsettings.py will be used.
        :param smallest_target:
        :param times_dimension:
        :param force_different_targets_factor:
            given the target values are computed from the 
            ``reference_data``, enforces that all target
            values are different by at last ``forced_different_targets_factor``
            if ``forced_different_targets_factor``. Default ``10**0.04`` means 
            that within the typical precision of ``10**0.2`` at most five 
            consecutive targets can be identical.
        :param step_to_next_difficult_target:
            the next more difficult target (just) not reached within the
            target run length is chosen, where ``step_to_next_difficult_target``
            defines "how much more difficult".

        TODO: check use case where ``reference_data`` is a dictionary similar
        to ``bestalg.bestAlgorithmEntries`` with each key dim_fun a reference
        DataSet, computed by bestalg module or portfolio module.

            dsList, sortedAlgs, dictAlg = pproc.processInputArgs(args)
            ref_data = refalg.generate(dictAlg)
            targets = RunlengthBasedTargetValues([1, 2, 4, 8], ref_data)

        """
        self.reference_data = reference_data
        if force_different_targets_factor < 1:
            force_different_targets_factor **= -1 
        self._short_info = "budget-based targets"
        self.run_lengths = sorted(run_lengths)
        self.smallest_target = smallest_target
        self.step_to_next_difficult_target = step_to_next_difficult_target**np.sign(np.log(step_to_next_difficult_target))
        self.times_dimension = times_dimension
        self.unique_target_values = unique_target_values
        # force_different_targets and target_discretization could talk to each other? 
        self.force_different_targets_factor = force_different_targets_factor
        self.target_discretization_factor = 10**0.2  # in accordance with default recordings
        self.reference_algorithm = ''
        self.initialized = False

    def initialize(self):
        """lazy initialization to prevent slow import"""
        if self.initialized:
            return self
        if self.reference_data == 'testbedsettings': # refalg data are loaded according to testbedsettings
            self.reference_algorithm = testbedsettings.current_testbed.reference_algorithm_filename
            self._short_info = 'reference budgets from ' + self.reference_algorithm

            from . import bestalg
            self.reference_data = bestalg.load_reference_algorithm(self.reference_algorithm, force=True)
            # TODO: remove targets smaller than 1e-8
        elif type(self.reference_data) is str:  # self.reference_data in ('RANDOMSEARCH', 'IPOP-CMA-ES') should work
            self._short_info = 'reference budgets from ' + self.reference_data
            # dsl = DataSetList(os.path.join(sys.modules[globals()['__name__']].__file__.split('cocopp')[0],
            #                                'cocopp', 'data', self.reference_data))
            dsl = DataSetList(findfiles.COCODataArchive().get_one(self.reference_data))
            dsd = {}
            for ds in dsl:
                # ds._clean_data()
                dsd[(ds.funcId, ds.dim)] = ds
            self.reference_data = dsd
        elif isinstance(self.reference_data, list):
            if not isinstance(self.reference_data[0], string_types):
                raise ValueError("RunlengthBasedTargetValues() expected a string, dict, or list of strings as second argument,"
                + (" got a list of %s" % str(type(self.reference_data[0]))))
            # dsList, sortedAlgs, dictAlg = processInputArgs(self.reference_data)
            self.reference_data = processInputArgs(self.reference_data)[2]
            self.reference_algorithm = self.reference_data[list(self.reference_data.keys())[0]].algId
        else:
            # assert len(byalg) == 1
            # we assume here that self.reference_data is a dictionary
            # of reference data sets
            self.reference_algorithm = self.reference_data[list(self.reference_data.keys())[0]].algId
        self.initialized = True
        return self

    def __len__(self):
        return len(self.run_lengths)  

    def __call__(self, fun_dim=None, discretize=None):
        """Get all target values for the respective function and dimension  
        and reference aRT values (passed during initialization). `fun_dim`
        is a tuple ``(fun_nb, dimension)`` like ``(1, 20)`` for the 20-D
        sphere.

        ``if discretize`` all targets are in [10**i/5 for i in N], in case
        achieved via rounding on the log-scale.
        
        Details: f_target = arg min_f { ERT_ref(f) > max(1, target_budget * dimension**times_dimension_flag) }, 
        where f are the values of the ``DataSet`` ``target`` attribute. The next difficult target is chosen
        not smaller as target / 10**0.2. 
        
        Returned are the aRT for targets that, within the given budget, the
        reference algorithm just failed to achieve.

        """            
        self.initialize()
        if self.force_different_targets_factor**len(self.run_lengths) > 1e3:
                warnings.warn('enforced different target values might spread more than three orders of magnitude')
        if fun_dim is None:
            raise ValueError('call to RunlengthbasedTargetValues class instance needs the parameter ``fun_dim``, none given')
        fun_dim = tuple(fun_dim)
        dim_fun = tuple(reversed(fun_dim))
        if fun_dim[0] > 100 and self.run_lengths[-1] * fun_dim[1]**self.times_dimension < 1e3:
            ValueError("short running times don't work on noisy functions")

        if not self.reference_data:
            raise ValueError('When running with the runlegth based target values ' \
                              'the reference data (e.g. a best algorithm) must exist.')

        ds = self.reference_data[dim_fun]
        if 11 < 3:   
            try:
                ds._complement_data() # is not fully implemented and not here not necessary
            except AttributeError: # loaded classes might not have this method
                # need a hack here
                _DataSet_complement_data(ds, self.target_discretization_factor)
        # end is the first index in ds.target with a values smaller than smallest_target
        try:
            end = np.nonzero(ds.target >= self.smallest_target)[0][-1] + 1 
            # same as end = np.where(ds.target >= smallest_target)[0][-1] + 1 
        except IndexError:
            end = len(ds.target)

        if genericsettings.test:
            if 11 < 3 and not toolsdivers.equals_approximately(ds.target[end-2] / ds.target[end-1], 10**0.2, 1e-8):
                print('last two targets before index %s' % str(end))
                print(ds.target[end-2:end])
            try: 
                assert ds.ert[0] == 1  # we might have to compute these the first time
            except AssertionError:
                print(fun_dim, ds.ert[0], 'ert[0] != 1 in TargetValues.__call__')
            try: 
                # check whether there are gaps between the targets 
                assert all(toolsdivers.equals_approximately(10**0.2, ds.target[i] / ds.target[i+1]) for i in range(end-1))
                # if this fails, we need to insert the missing target values 
            except AssertionError:
                if 1 < 3:
                    print(fun_dim, ds.ert[0], 'not all targets are recorded in TargetValues.__call__ (this could be a bug)')
                    print(ds.target)
                    # 1/0
        
        # here the test computation starts
        targets = []
        if genericsettings.test: 
            for rl in self.run_lengths:
                # choose largest target not achieved by reference aRT
                indices = np.nonzero(ds.ert[:end] > np.max((1, rl * (fun_dim[1] if self.times_dimension else 1))))[0]
                if len(indices):  # larger ert exists
                    targets.append(np.max((ds.target[indices[0]],  # first missed target 
                                           (1 + 1e-9) * ds.target[indices[0] - 1] / self.step_to_next_difficult_target))) # achieved target / 10*0.2
                else:
                    # TODO: check whether this is the final target! If not choose a smaller than the last achieved one. 
                    targets.append(ds.target[end-1])  # last target
                    if targets[-1] > (1 + 1e-9) * self.smallest_target:
                        targets[-1] = (1 + 1e-9) * targets[-1] / self.step_to_next_difficult_target
                
                if len(targets) > 1 and targets[-1] >= targets[-2] and self.force_different_targets_factor > 1 and targets[-1] > self.smallest_target:
                    targets[-1] = targets[-2] / self.force_different_targets_factor
            targets = np.array(targets, copy=False)
            targets[targets < self.smallest_target] = self.smallest_target
            
            # a few more sanity checks
            if targets[-1] < self.smallest_target:
                print('runlength based targets', fun_dim, ': correction for small smallest target applied (should never happen)')
                b = float(targets[0])
                targets = np.exp(np.log(targets) * np.log(b / self.smallest_target) / np.log(b / targets[-1]))
                targets *= (1 + 1e-12) * self.smallest_target / targets[-1]
                assert b <= targets[0] * (1 + 1e-10)
                assert b >= targets[0] / (1 + 1e-10)
            assert targets[-1] >= self.smallest_target
            assert len(targets) == 1 or all(np.diff(targets) <= 0)
            assert len(ds.ert) == len(ds.target)
        
        # here the actual computation starts
        old_targets = targets
        targets = [] 
        for rl in self.run_lengths:
            # choose best target achieved by reference aRT times step_to_next_difficult_target
            indices = np.nonzero(ds.ert[:end] <= np.max((1, rl * (fun_dim[1] if self.times_dimension else 1))))[0]
            if not len(indices):
                warnings.warn('  too easy run length ' + str(rl) +
                              ' for (f,dim)=' + str(fun_dim))
                targets.append(ds.target[0])
            else:
                targets.append((1 + 1e-9) * ds.target[indices[-1]]
                               / self.step_to_next_difficult_target)
            
            if (len(targets) > 1 and targets[-1] >= targets[-2] and 
                self.force_different_targets_factor > 1):
                targets[-1] = targets[-2] / self.force_different_targets_factor
        targets = np.array(targets, copy=False)
        targets[targets < self.smallest_target] = self.smallest_target

        # a few more sanity checks
        if targets[-1] < self.smallest_target:
            print('runlength based targets', fun_dim, ': correction for small smallest target applied (should never happen)')
            b = float(targets[0])
            targets = np.exp(np.log(targets) * np.log(b / self.smallest_target) / np.log(b / targets[-1]))
            targets *= (1 + 1e-12) * self.smallest_target / targets[-1]
            assert b <= targets[0] * (1 + 1e-10)
            assert b >= targets[0] / (1 + 1e-10)
        assert targets[-1] >= self.smallest_target
        assert len(targets) == 1 or all(np.diff(targets) <= 0)
        assert len(ds.ert) == len(ds.target)

        if genericsettings.test and not all(targets == old_targets): # or (fun_dim[0] == 19 and len(targets) > 1):
            print('WARNING: target values are different compared to previous version')
            print(fun_dim)
            print(targets / old_targets - 1)
            print(targets)

        if self.unique_target_values:
            #len_ = len(targets)
            targets = np.array(list(reversed(sorted(set(targets)))))
            # print(' '.join((str(len(targets)), 'of', str(len_), 'targets kept')))
        if discretize:
            return self._discretize(targets)
        return targets    

    get_targets = __call__  # an alias
    
    def label(self, i):
        """return i-th target value as string"""
        return toolsdivers.num2str(self.run_lengths[i], significant_digits=2)

    def loglabel(self, i, decimals=1):
        """``decimals`` is used for ``round``"""
        return toolsdivers.num2str(np.log10(self.run_lengths[i]), significant_digits=decimals+1)
        # return str(np.round(np.log10(self.run_lengths[i]), decimals))
    
    def labels(self):
        """target values as a list of ``str``"""
        i, res = 0, []
        try:
            while True:
                res.append(self.label(i))
                i += 1
        except IndexError:
            return res
    
    def label_name(self):
        return 'RL' + ('/dim' if self.times_dimension else '')

    def _generate_erts(self, ds, target_values):
        """compute for all target values, starting with 1e-8, the ert value
        and store it in the reference_data_set attribute
        
        """
        raise NotImplementedError
              

class DataSet(object):
    """Unit element for the COCO post-processing.

    An instance of this class is created from one unit element of
    experimental data. One unit element would correspond to data for a
    given algorithm (a given :py:attr:`algId` and a :py:attr:`comment`
    line) and a given problem (:py:attr:`funcId` and
    :py:attr:`dimension`).

    Class attributes:

      - *funcId* -- function Id (integer)
      - *dim* -- dimension (integer)
      - *indexFiles* -- associated index files (list of strings)
      - *dataFiles* -- associated data files (list of strings)
      - *comment* -- comment for the setting (string)
      - *targetFuncValue* -- final target function value (float), might be missing
      - *precision* -- final ftarget - fopt (float), data with 
                       target[idat] < precision are optional and not relevant.  
      - *algId* -- algorithm name (string)
      - *evals* -- data aligned by function values (2xarray, list of data rows [f_val, eval_run1, eval_run2,...]), cave: in a portfolio data rows can have different lengths
      - *funvals* -- data aligned by function evaluations (2xarray)
      - *maxevals* -- maximum number of function evaluations (array)
      - *finalfunvals* -- final function values (array)
      - *readmaxevals* -- maximum number of function evaluations read
                          from index file (array)
      - *readfinalFminusFtarget* -- final function values - ftarget read
                                    from index file (array)
      - *pickleFile* -- associated pickle file name (string)
      - *target* -- target function values attained (array)
      - *ert* -- ert for reaching the target values in target (array)
      - *instancenumbers* -- list of numbers corresponding to the instances of
                     the test function considered (list of int)
      - *isFinalized* -- list of bool for if runs were properly finalized

    :py:attr:`evals` and :py:attr:`funvals` are arrays of data collected
    from :py:data:`N` data sets.

    Both have the same format: zero-th column is the value on which the
    data of a row is aligned, the :py:data:`N` subsequent columns are
    either the numbers of function evaluations for :py:attr:`evals` or
    function values for :py:attr:`funvals`.
    
    A short example::

        >>> from __future__ import print_function    
        >>> import sys
        >>> import os
        >>> import urllib
        >>> import tarfile
        >>> import cocopp
        >>> cocopp.genericsettings.verbose = False # ensure to make doctests work
        >>> def setup(infoFile):
        ...     if not os.path.exists(infoFile):
        ...         filename = cocopp.archives.bbob.get_one('2009/BIPOP-CMA-ES_hansen')
        ...         tarfile.open(filename).extractall(cocopp.archives.bbob.local_data_path)
        >>> infoFile = os.path.join(cocopp.archives.bbob.local_data_path, 'BIPOP-CMA-ES', 'bbobexp_f2.info')
        >>> print('get'); setup(infoFile) # doctest:+ELLIPSIS
        get...
        >>> dslist = cocopp.load(infoFile)
          Data consistent according to consistency_check() in pproc.DataSet
        >>> print(dslist)  # doctest:+ELLIPSIS
        [DataSet(BIPOP-CMA-ES on f2 2-D), ..., DataSet(BIPOP-CMA-ES on f2 40-D)]
        >>> type(dslist)
        <class 'cocopp.pproc.DataSetList'>
        >>> len(dslist)
        6
        >>> ds = dslist[3]  # a single data set of type DataSet
        >>> ds
        DataSet(BIPOP-CMA-ES on f2 10-D)
        >>> for d in dir(ds): print(d)  # doctest:+ELLIPSIS
        _DataSet__parseHeader
        __class__
        __delattr__
        __dict__
        ...
        __getattribute__
        ...
        __module__
        __ne__
        __new__
        __reduce__
        __reduce_ex__
        __repr__
        __setattr__
        __sizeof__
        __str__
        __subclasshook__
        __weakref__
        _attributes
        _complement_data
        _cut_data
        _detEvals2
        _detMaxEvals
        _evals
        _extra_attr
        algId
        algs
        comment
        computeERTfromEvals
        consistency_check
        createDictInstance
        createDictInstanceCount
        dataFiles
        detAverageEvals
        detERT
        detEvals
        detSuccessRates
        detSuccesses
        dim
        ert
        evals
        evals_
        evals_with_simulated_restarts
        finalfunvals
        funcId
        funvals
        generateRLData
        get_data_format
        get_suite
        get_testbed_name
        indexFiles
        info
        instancenumbers
        isBiobjective
        isFinalized
        mMaxEvals
        max_eval
        maxevals
        nbRuns
        pickle
        plot
        plot_funvals
        precision
        readfinalFminusFtarget
        readmaxevals
        reference_values
        splitByTrials
        success_ratio
        target
        testbed_name
        >>> all(ds.evals[:, 0] == ds.target)  # first column of ds.evals is the "target" f-value
        True
        >>> # investigate row 0,10,20,... and of the result columns 0,5,6, index 0 is ftarget
        >>> ev = ds.evals[0::10, (0,5,6)]  # doctest:+ELLIPSIS  
        >>> assert 3.98107170e+07 <= ev[0][0] <= 3.98107171e+07 
        >>> assert ev[0][1] == 1
        >>> assert ev[0][2] == 1
        >>> assert 6.07000000e+03 <= ev[-1][-1] <= 6.07000001e+03
        >>> # show last row, same columns
        >>> ev = ds.evals[-1,(0,5,6)]  # doctest:+ELLIPSIS
        >>> assert ev[0] == 1e-8
        >>> assert 5.67600000e+03 <= ev[1] <= 5.67600001e+03
        >>> ds.info()  # prints similar data more nicely formated 
        Algorithm: BIPOP-CMA-ES
        Function ID: 2
        Dimension DIM = 10
        Number of trials: 15
        Final target Df: 1e-08
        min / max number of evals per trial: 5676 / 6346
           evals/DIM:  best     15%     50%     85%     max |  aRT/DIM  nsucc
          ---Df---|-----------------------------------------|----------------
          1.0e+03 |     102     126     170     205     235 |    164.2  15
          1.0e+01 |     278     306     364     457     480 |    374.5  15
          1.0e-01 |     402     445     497     522     536 |    490.8  15
          1.0e-03 |     480     516     529     554     567 |    532.8  15
          1.0e-05 |     513     546     563     584     593 |    562.5  15
          1.0e-08 |     568     594     611     628     635 |    609.6  15

        >>> import numpy as np
        >>> idx = list(range(0, 50, 10)) + [-1]
        >>> # get aRT average runtime for some targets
        >>> t = np.array([idx, ds.target[idx], ds.ert[idx]]).T  # doctest:+ELLIPSIS  
        >>> assert t[0][0] == 0
        >>> assert t[0][2] == 1
        >>> assert t[-1][-2] == 1e-8
        >>> assert 6.09626666e+03 <= t[-1][-1] <= 6.09626667e+03

        Note that the load of a data set depends on the set of instances
        specified in testbedsettings' TestBed class (or its children)
        (None means all instances are read in):
        >>> import sys
        >>> import os
        >>> import urllib
        >>> import tarfile
        >>> import cocopp
        >>> cocopp.genericsettings.verbose = False # ensure to make doctests work
        >>> infoFile = os.path.join(cocopp.archives.bbob.local_data_path, 'BIPOP-CMA-ES', 'bbobexp_f2.info')
        >>> if not os.path.exists(infoFile):
        ...   filename = cocopp.archives.bbob.get_one('bbob/2009/BIPOP-CMA-ES_hansen')
        ...   tarfile.open(filename).extractall(cocopp.archives.bbob.local_data_path)
        >>> dslist = cocopp.load(infoFile)
          Data consistent according to consistency_check() in pproc.DataSet
        >>> dslist[2].instancenumbers
        [1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5, 5]
        >>> dslist[2].evals[-1]  # doctest:+ELLIPSIS
        array([...
        >>> assert (dslist[2].evals[-1])[0] == 1.0e-8
        >>> assert 2.01200000e+03 <= (dslist[2].evals[-1])[-1] <= 2.01200001e+03
        >>> # because testbedsettings.GECCOBBOBTestbed.settings['instancesOfInterest'] was None
        >>> cocopp.testbedsettings.GECCOBBOBTestbed.settings['instancesOfInterest'] = [1, 3]
        >>> cocopp.config.config('GECCOBBOBTestbed') # make sure that settings are used
        >>> dslist2 = cocopp.load(infoFile)
          Data consistent according to consistency_check() in pproc.DataSet
        >>> dslist2[2].instancenumbers
        [1, 1, 1, 3, 3, 3]
        >>> dslist2[2].evals[-1]  # doctest:+ELLIPSIS
        array([...
        >>> assert (dslist2[2].evals[-1])[0] == 1.0e-8
        >>> assert 2.20700000e+03 <= (dslist2[2].evals[-1])[-1] <= 2.20700001e+03
        >>> # set things back to cause no troubles elsewhere:
        >>> cocopp.testbedsettings.GECCOBBOBTestbed.settings['instancesOfInterest'] = None
        >>> cocopp.config.config('GECCOBBOBTestbed') # make sure that settings are used

    """

    # TODO: unit element of the post-processing: one algorithm, one problem
    # TODO: if this class was to evolve, how do we make previous data
    # compatible?

    # Private attribute used for the parsing of info files.
    _attributes = {'funcId': ('funcId', int), 
                   'function': ('funcId', int), 
                   'DIM': ('dim', int),
                   'dim': ('dim', int),
                   'Precision': ('precision', float), 
                   'Fopt': ('fopt', float),
                   'targetFuncValue': ('targetFuncValue', float),
                   'indicator': ('indicator', str),
                   'folder': ('folder', str),
                   'algId': ('algId', str),
                   'algorithm': ('algId', str),
                   'suite': ('suite', str),
                   'logger': ('logger', str),
                   'coco_version': ('coco_version', str),
                   'reference_values_hash': ('reference_values_hash', str),
                   'data_format': ('data_format', str)}

    def isBiobjective(self):
        return hasattr(self, 'indicator')

    def get_testbed_name(self):
        suite = self.get_suite()
        return testbedsettings.get_testbed_from_suite(suite)

    def get_data_format(self):
        # TODO: data_format is a specification of the files written by the 
        # experiment loggers. I believe it was never meant to be a specification
        # for a data set.
        if hasattr(self, 'data_format'):
            return getattr(self, 'data_format')
        if self.isBiobjective():
            return 'bbob-biobj'
        return None

    def get_suite(self):
        suite = None
        if hasattr(self, 'suite'):
            suite = getattr(self, 'suite')
        if not suite:
            if self.isBiobjective():
                suite = testbedsettings.default_suite_bi
            else:
                # detect by hand whether we are in the noisy or the
                # noiseless case (TODO: is there a better way?)
                if self.funcId > 100:
                    genericsettings.isNoisy = True
                    genericsettings.isNoiseless = False
                    suite = testbedsettings.default_suite_single_noisy
                else:
                    genericsettings.isNoisy = False
                    genericsettings.isNoiseless = True
                    suite = testbedsettings.default_suite_single

        return suite

    def __init__(self, header, comment, data, indexfile):
        """Instantiate a DataSet.

        The first three input arguments correspond to three consecutive
        lines of an index file (.info extension).

        :keyword string header: information of the experiment
        :keyword string comment: more information on the experiment
        :keyword string data: information on the runs of the experiment
        :keyword string indexfile: string for the file name from where
                                   the information come

        """
        # Extract information from the header line.
        self._extra_attr = []
        self.__parseHeader(header)
        # In biobjective case we have some header info in the data line.
        self.__parseHeader(data) 

        # Read in second line of entry (comment line). The information
        # is only stored if the line starts with "%", else it is ignored.
        if comment.startswith('%'):
            self.comment = comment.strip()
        else:
            #raise Exception()
            warnings.warn('Comment line: %s is skipped,' % (comment) +
                          'it does not start with \%.')
            self.comment = ''

        filepath = os.path.split(indexfile)[0]
        self.indexFiles = [indexfile]
        self.dataFiles = []
        self.instancenumbers = []
        self.algs = []
        self.success_ratio = []
        self.reference_values = {}
        self.evals = []  # to be removed if evals becomes a property, see below
        """``evals`` are the central data. Each line ``evals[i]`` has a
        (target) function value in ``evals[i][0]`` and the function evaluation
        for which this target was reached the first time in trials 1,...
        in ``evals[i][1:]``.""" 
        self._evals = []  # not in use
        self.isFinalized = []
        self.readmaxevals = []
        self.readfinalFminusFtarget = []
        self.testbed_name = self.get_testbed_name()

        if not testbedsettings.current_testbed:
            testbedsettings.load_current_testbed(self.testbed_name, TargetValues)

        # Split line in data file name(s) and run time information.
        parts = data.split(', ')
        idx_of_instances_to_load = []
        for elem in parts:
            elem = elem.strip()
            if elem.endswith('dat'):
                #Windows data to Linux processing
                filename = elem
                # while elem.find('\\ ') >= 0:
                #     filename = filename.replace('\\ ', '\\')
                filename = filename.replace('\\', os.sep)
                #Linux data to Windows processing
                filename = filename.replace('/', os.sep)
                
                folder = getattr(self, 'folder', '')
                if folder:
                    filename = os.path.join(folder, filename)
                    
                self.dataFiles.append(filename)
            elif '=' in elem: 
                # It means header info in data line (biobjective). 
                # We just skip the element.
                continue
            else:
                if not ':' in elem:
                    
                    # We might take only a subset of the given instances,
                    # given in testbedsettings.current_testbed.instancesOfInterest:
                    if testbedsettings.current_testbed.instancesOfInterest:
                        instance = ast.literal_eval(elem)

                        # If this is the best algorithm then the instance number is 0.
                        if instance > 0 and instance not in testbedsettings.current_testbed.instancesOfInterest:
                            idx_of_instances_to_load.append(False)
                            continue

                    # if elem does not have ':' it means the run was not
                    # finalized properly.
                    self.instancenumbers.append(ast.literal_eval(elem))
                    # In this case, what should we do? Either we try to process
                    # the corresponding data anyway or we leave it out.
                    # For now we leave it in.
                    idx_of_instances_to_load.append(True)
                    self.isFinalized.append(False)
                    warnings.warn('Caught an ill-finalized run in %s for %s'
                                  % (indexfile,
                                     os.path.join(filepath, self.dataFiles[-1])))
                    self.readmaxevals.append(0)
                    self.readfinalFminusFtarget.append(numpy.inf)
                else:
                    itrial, info = elem.split(':', 1)
                    # We might take only a subset of the given instances,
                    # given in testbedsettings.current_testbed.instancesOfInterest:
                    if testbedsettings.current_testbed.instancesOfInterest:
                        instance = ast.literal_eval(itrial)

                        # If this is the best algorithm then the instance number is 0.
                        if instance > 0 and instance not in testbedsettings.current_testbed.instancesOfInterest:
                            idx_of_instances_to_load.append(False)
                            continue

                    self.instancenumbers.append(ast.literal_eval(itrial))
                    idx_of_instances_to_load.append(True)
                    self.isFinalized.append(True)
                    readmaxevals, readfinalf = info.split('|', 1)
                    self.readmaxevals.append(int(readmaxevals))
                    self.readfinalFminusFtarget.append(float(readfinalf))

        if genericsettings.verbose:
            print("%s" % self.__repr__())

        # Treat successively the data in dat and tdat files:
        # put into variable dataFiles the files where to look for data
        dataFiles = list(os.path.join(filepath, os.path.splitext(i)[0] + '.dat')
                         for i in self.dataFiles)
        datasets, algorithms, reference_values, success_ratio = split(dataFiles, idx_to_load=idx_of_instances_to_load)
        dataformatsettings.current_data_format = dataformatsettings.data_format_name_to_class_mapping[self.get_data_format()]()
        data = HMultiReader(datasets)
        if genericsettings.verbose:
            print("Processing %s: %d/%d trials found." % (dataFiles, len(data), len(self.instancenumbers)))
       
        if data:
            # this takes different data formats into account to compute
            # the evals attribute and others into self:
            maxevals, finalfunvals = dataformatsettings.current_data_format.align_data_into_evals(
                                                align_data, data, self)
            # CAVEAT: maxevals may not be f-evaluations only
            # TODO: the above depends implicitely (in readalign.align_data)
            # on the global variable setting of
            # dataformatsettings.current_data_format which
            # seems like code which is bug prone and hard to maintain

            self.reference_values = reference_values
            if len(algorithms) > 0:
                algorithms = align_list(algorithms, [item[1] for item in self.evals])
            self.algs = algorithms
            if len(success_ratio) > 0:
                success_ratio = align_list(success_ratio, [item[1] for item in self.evals])
            self.success_ratio = success_ratio
            try:
                for i in range(len(maxevals)):
                    self.maxevals[i] = max(maxevals[i], self.maxevals[i])
                    self.finalfunvals[i] = min(finalfunvals[i], self.finalfunvals[i])
            except AttributeError:
                self.maxevals = maxevals
                self.finalfunvals = finalfunvals

        dataFiles = list(os.path.join(filepath, os.path.splitext(i)[0] + '.tdat')
                         for i in self.dataFiles)
                             
        if not any(os.path.isfile(dataFile) for dataFile in dataFiles):
            warnings.warn("Missing tdat files in '{0}'. Please consider to rerun the experiments." % filepath)

        datasets, algorithms, reference_values, success_ratio = split(dataFiles, idx_to_load=idx_of_instances_to_load)
        data = VMultiReader(datasets)
        if genericsettings.verbose:
            print("Processing %s: %d/%d trials found."
                   % (dataFiles, len(data), len(self.instancenumbers)))
        
        if data:
            # TODO: maxevals and evals in the constrained case will give
            # values inconsistent with the above evals attribute
            self.funvals, maxevals, finalfunvals = align_data(
                data, 
                dataformatsettings.current_data_format.evaluation_idx,
                dataformatsettings.current_data_format.function_value_idx,
                )
            # was: (adata, maxevals, finalfunvals) = align_data(data)
            try:
                for i in range(len(maxevals)):
                    self.maxevals[i] = max(maxevals[i], self.maxevals[i])
                    self.finalfunvals[i] = min(finalfunvals[i], self.finalfunvals[i])
            except AttributeError:
                self.maxevals = maxevals
                self.finalfunvals = finalfunvals
            #TODO: take for maxevals the max for each trial, for finalfunvals the min...
    
            #extensions = {'.dat':(HMultiReader, 'evals'), '.tdat':(VMultiReader, 'funvals')}
            #for ext, info in extensions.items(): # ext is defined as global
                ## put into variable dataFiles the files where to look for data
                ## basically append 
                #dataFiles = list(i.rsplit('.', 1)[0] + ext for i in self.dataFiles)
                #data = info[0](split(dataFiles))
                ## split is a method from readalign, info[0] is a method of readalign
                #if genericsettings.verbose:
                    #print("Processing %s: %d/%d trials found." #% (dataFiles, len(data), len(self.itrials)))
                #(adata, maxevals, finalfunvals) = alignData(data)
                #setattr(self, info[1], adata)
                #try:
                    #if all(maxevals > self.maxevals):
                        #self.maxevals = maxevals
                        #self.finalfunvals = finalfunvals
                #except AttributeError:
                    #self.maxevals = maxevals
                    #self.finalfunvals = finalfunvals
            #CHECKING PROCEDURE
            tmp = []
            for i in range(min((len(self.maxevals), len(self.readmaxevals)))):
                tmp.append(self.maxevals[i] == self.readmaxevals[i])
            if not all(tmp) or len(self.maxevals) != len(self.readmaxevals):
                warnings.warn('There is a difference between the maxevals in the '
                              '*.info file and in the data files.')

            self._cut_data()
            # Compute aRT
            self.computeERTfromEvals()

    @property
    def evals_(self):
        """Shall become ``evals`` attribute in future.
        
        ``evals`` are the central data. Each line ``evals[i]`` has a 
        (target) function value in ``evals[i][0]`` and the function evaluation
        for which this target was reached the first time in trials 1,...
        in ``evals[i][1:]``. 
        
        """
        return self._evals
    @evals_.setter
    def evals_(self, value):
        self._evals = value
    @evals_.deleter
    def evals_(self):
        del self._evals
        
    def _cut_data(self):
        """attributes `target`, `evals`, and `ert` are truncated to target values not 
        much smaller than defined in attribute `precision` (typically ``1e-8``). 
        Attribute `maxevals` is recomputed for columns that reach the final target
        precision. Note that in the bi-objective case the attribute `precision`
        does not exist.
        
        """

        if isinstance(testbedsettings.current_testbed, testbedsettings.GECCOBBOBTestbed):
            Ndata = np.size(self.evals, 0)
            i = Ndata
            while i > 1 and not self.isBiobjective() and self.evals[i-1][0] <= self.precision:
                i -= 1
            i += 1
            if i < Ndata:
                self.evals = self.evals[:i, :]  # assumes that evals is an array
                try:
                    self.target = self.target[:i]
                    assert self.target[-1] == self.evals[-1][0] 
                except AttributeError:
                    pass
                try:
                    self.ert = self.ert[:i]
                except AttributeError:
                    pass
            assert self.evals.shape[0] == 1 or self.isBiobjective() or self.evals[-2][0] > self.precision
            if not self.isBiobjective() and self.evals[-1][0] < self.precision: 
                self.evals[-1][0] = np.max((self.precision / 1.001, self.evals[-1, 0])) 
                # warnings.warn('exact final precision was not recorded, next lower value set close to final precision')
                # print('*** warning: final precision was not recorded')
                assert self.evals[-1][0] < self.precision # shall not have changed
            assert self.evals[-1][0] > 0
            self.maxevals = self._detMaxEvals()

    def _complement_data(self, step=10**0.2, final_target=1e-8):
        """insert a line for each target value"""
        _DataSet_complement_data(self, step, final_target)

    def consistency_check(self):
        """checks consistency of data set according to
           - number of instances           
           - instances used
        """
        is_consistent = True
        
        instancedict = dict((j, self.instancenumbers.count(j)) for j in set(self.instancenumbers))
        
        if '% Combination of ' in self.comment:
            # a short test for BestAlgSet...
            return self.instancenumbers == [0]
        
        # We might take only a subset of all provided instances...
        if not testbedsettings.current_testbed:
            expectedNumberOfInstances = 15 # standard choice
        elif not testbedsettings.current_testbed.instancesOfInterest: # case of no specified instances
            expectedNumberOfInstances = 10 if isinstance(testbedsettings.current_testbed,
                    testbedsettings.GECCOBiObjBBOBTestbed) else 15
        else:
            expectedNumberOfInstances = len(testbedsettings.current_testbed.instancesOfInterest)
        if len(set(self.instancenumbers)) < len(self.instancenumbers):
            # check exception of 2009 data sets with 3 times instances 1:5
            for i in set(self.instancenumbers):
                if i not in (1, 2, 3, 4, 5):
                    is_consistent = False
                    break
                if self.instancenumbers.count(i) != 3:
                    is_consistent = False
                    break
            if not is_consistent:
                warnings.warn('  double instances in ' + 
                                str(self.instancenumbers) + 
                                ' (f' + str(self.funcId) + ', ' + str(self.dim)
                                + 'D)')
        elif len(self.instancenumbers) < expectedNumberOfInstances:
            is_consistent = False
            warnings.warn('  less than ' + str(expectedNumberOfInstances) +
                                ' instances in ' + 
                                str(self.instancenumbers) + 
                                ' (f' + str(self.funcId) + ', ' +
                                str(self.dim) + 'D)')
        elif len(self.instancenumbers) > expectedNumberOfInstances:
            is_consistent = False
            warnings.warn('  more than ' + str(expectedNumberOfInstances) + 
                                ' instances in ' + 
                                str(self.instancenumbers)+ 
                                ' (f' + str(self.funcId) + ', ' + 
                                str(self.dim) + 'D)')
        elif (instancedict not in genericsettings.instancesOfInterest):
            is_consistent = False
            warnings.warn('  instance numbers not among the ones specified in 2009, 2010, 2012, 2013, and 2015-2018')
        return is_consistent
            
    def computeERTfromEvals(self):
        """Sets the attributes ert and target from the attribute evals."""
        self.ert = []
        self.target = []
        for i in self.evals:
            data = i.copy()
            data = data[1:]
            succ = (numpy.isnan(data)==False)
            if any(numpy.isnan(data)):
                data[numpy.isnan(data)] = self.maxevals[numpy.isnan(data)]
            self.ert.append(toolsstats.sp(data, issuccessful=succ)[0])
            self.target.append(i[0])

        self.ert = numpy.array(self.ert)
        self.target = numpy.array(self.target)

    def evals_with_simulated_restarts(self,
            targets,
            samplesize=genericsettings.simulated_runlength_bootstrap_sample_size,
            randintfirst=toolsstats.randint_derandomized,
            randintrest=toolsstats.randint_derandomized,
            bootstrap=False):
        """Return a len(targets) list of ``samplesize`` "simulated" run
        lengths (#evaluations, sorted).

        ``np.sort(np.concatenate(return_value))`` provides the combined
        sorted ECDF data over all targets which may be plotted with
        `pyplot.step` (missing the last step).

        Unsuccessful data are represented as `np.nan`.

        Simulated restarts are used for unsuccessful runs. The usage of
        `detEvals` or `evals_with_simulated_restarts` should be largely
        interchangeable, while the latter has a "success" rate of either
        0 or 1.

        TODO: change this: To get a bootstrap sample for estimating dispersion use
        ``min_samplesize=0, randint=np.random.randint``.

        Details:

        - For targets where all runs were successful, samplesize=nbRuns()
          is sufficient (and preferable) if `randint` is derandomized.
        - A single successful running length is computed by adding
          uniformly randomly chosen running lengths until the first time a
          successful one is chosen. In case of no successful run the
          result is `None`.

        TODO: if `samplesize` >> `nbRuns` and nsuccesses is large,
        the data representation becomes somewhat inefficient.

        TODO: it may be useful to make the samplesize dependent on the
        number of successes and supply the multipliers
        max(samplesizes) / samplesizes.
        """
        try: targets = targets([self.funcId, self.dim])
        except TypeError: pass
        res = []  # res[i] is a list of samplesize evals
        for evals in self.detEvals(targets, bootstrap=bootstrap):
            # prepare evals array
            evals.sort()
            indices = np.isfinite(evals)
            if not sum(indices):  # no successes
                res += [samplesize * [np.nan]]  # TODO: this is "many" data with little information
                continue
            nindices = ~indices
            assert sum(indices) + sum(nindices) == len(evals)
            evals[nindices] = self.maxevals[nindices]  # replace nan
            # let the first nsucc data in evals be those from successful runs
            evals = np.hstack([evals[indices], evals[nindices]])
            assert sum(np.isfinite(evals)) == len(evals)
            nsucc = sum(indices)

            # do the job
            indices = randintfirst(0, len(evals), samplesize)
            sums = evals[indices]
            if nsucc == len(evals):
                res += [sorted(sums)]
                continue
            failing = np.where(indices >= nsucc)[0]
            assert nsucc > 0  # prevent infinite loop
            while len(failing):  # add "restarts"
                indices = randintrest(0, len(evals), len(failing))
                sums[failing] += evals[indices]
                # keep failing indices
                failing = [failing[i] for i in range(len(failing))
                            if indices[i] >= nsucc]
            res += [sorted(sums)]

        assert set([len(evals) if evals is not None else samplesize
                for evals in res]) == set([samplesize])
        return res

    def __eq__(self, other):
        """Compare indexEntry instances."""
        res = (self.__class__ is other.__class__ and
               self.funcId == other.funcId and
               self.dim == other.dim and
               (self.isBiobjective() or self.precision == other.precision) and
               self.algId == other.algId and
               self.comment == other.comment)
        if hasattr(self, '_extra_attr'): # Backward compatibility
            for i in self._extra_attr:
                res = (res and hasattr(other, i) and
                       getattr(other, i) == getattr(self, i))
                if not res:
                    break
        return res

    def __ne__(self,other):
        return not self.__eq__(other)

    def __repr__(self):
        res = ('DataSet(%s on f%s %d-D'
               % (self.algId, str(self.funcId), self.dim))
        for i in getattr(self, '_extra_attr', ()):
            res += ', %s = %s' % (i, getattr(self, i))
        res += ')'
        return res

    def info(self, targets=None):
        """print text info to stdout"""
        if targets is None:
            targets = [1e3, 10, 0.1, 1e-3, 1e-5, 1e-8]
            if self.target[-1] < targets[-1]:
                targets += [self.target[-1]]  
        if targets[-1] < self.target[-1]:
            targets[-1] = self.target[-1]
        targets = sorted(set(targets), reverse=True)  # remove dupicates and sort

        sinfo = 'Algorithm: ' + str(self.algId)
        sinfo += '\nFunction ID: ' + str(self.funcId)
        sinfo += '\nDimension DIM = ' + str(self.dim)
        sinfo += '\nNumber of trials: ' + str(self.nbRuns())
        if not self.isBiobjective():        
            sinfo += '\nFinal target Df: ' + str(self.precision)
        # sinfo += '\nmin / max number of evals: '  + str(int(min(self.evals[0]))) + ' / '  + str(int(max(self.maxevals)))
        sinfo += '\nmin / max number of evals per trial: '  + str(int(min(self.maxevals))) + ' / '  + str(int(max(self.maxevals)))
        sinfo += '\n   evals/DIM:  best     15%     50%     85%     max |  aRT/DIM  nsucc'
        sinfo += '\n  ---Df---|-----------------------------------------|----------------'
        evals = self.detEvals(targets, copy=False)
        nsucc = self.detSuccesses(targets)
        ert = self.detERT(targets)
        for i, target in enumerate(targets):
            line = '  %.1e |' % target
            for val in toolsstats.prctile(evals[i], (0, 15, 50, 85, 100)):
                val = float(val)
                line += ' %7d' % int(np.round(val / self.dim)) if not np.isnan(val) else '     .  '
            line += ' |' + ('%9.1f' % (ert[i] / self.dim) if np.isfinite(ert[i]) else '    nan  ') 
            # line += '  %4.2f' % (nsucc[i] / float(Nruns)) if nsucc[i] < Nruns else '  1.0 '
            line += '  %2d' % nsucc[i]
            sinfo += '\n' + line
            if target < self.target[-1]:
                break
        print(sinfo)
        # return sinfo 

    def mMaxEvals(self):
        """Returns the maximum number of function evaluations over all runs (trials), 
        obsolete and replaced by attribute `max_eval`
        
        """
        return max(self.maxevals)
    
    def _detMaxEvals(self, final_target=None):
        """computes for each data column the (maximal) evaluation 
        until final_target was reached, or ``self.maxevals`` otherwise. 
        
        """
        if final_target is None:
            final_target = self.precision if not self.isBiobjective() else 1e-8
        res = np.array(self.maxevals, copy=True) if not maximal_evaluations_only_to_last_target else np.nanmax(self.evals, 0)
        final_evals = self.detEvals([final_target])[0]
        idx = np.isfinite(final_evals)
        res[idx] = final_evals[idx] 
        assert sum(res < np.inf) == len(res)
        assert len(res) == self.nbRuns()
        return res 
        
    
    @property  # cave: setters work only with new style classes
    def max_eval(self):
        """maximum number of function evaluations over all runs (trials),

            return max(self.maxevals)

        """
        return max(self.maxevals)

    def nbRuns(self):
        """Returns the number of runs."""
        return numpy.shape(self.evals)[1] - 1 

    def __parseHeader(self, header):
        """Extract data from a header line in an index entry."""
        
        # Split header into a list of key-value
        for attrname, attrvalue in parseinfo(header):
            try:
                setattr(self, self._attributes[attrname][0], attrvalue)
            except KeyError:
                warnings.warn('%s is an additional attribute.' % (attrname))
                setattr(self, attrname, attrvalue)
                self._extra_attr.append(attrname)
                # the attribute is set anyway, this might lead to some errors.
                continue
        #TODO: check that no compulsory attributes is missing:
        #dim, funcId, algId, precision
        return

    def pickle(self, outputdir=None, gzipped=True):
        """Save this instance to a pickle file.

        Saves this instance to a (by default gzipped) pickle file. If not 
        specified by argument outputdir, the location of the pickle is 
        given by the location of the first index file associated to this
        instance.

        This method will overwrite existing files.
        
        """
        # the associated pickle file does not exist
        if outputdir is not None and getattr(self, 'pickleFile', False):
            NotImplementedError('outputdir and pickleFile attribute are in conflict')

        if not getattr(self, 'pickleFile', False):  # no attribute returns False, == not hasattr(self, 'pickleFile')
            if outputdir is None:
                outputdir = os.path.split(self.indexFiles[0])[0] + '-pickle'
            if not os.path.isdir(outputdir):
                try:
                    os.mkdir(outputdir)
                except OSError:
                    print('Could not create output directory % for pickle files'
                           % outputdir)
                    raise

            self.pickleFile = os.path.join(outputdir,
                                           'ppdata_f%03d_%02d.pickle'
                                            %(self.funcId, self.dim))

        if getattr(self, 'modsFromPickleVersion', True):
            try:
                if gzipped:
                    if self.pickleFile.find('.gz') < 0:
                        self.pickleFile += '.gz'
                    f = gzip.open(self.pickleFile, 'w')
                else:        
                    f = open(self.pickleFile, 'w') # TODO: what if file already exist?
                pickle.dump(self, f)
                f.close()
                if genericsettings.verbose:
                    print('Saved pickle in %s.' %(self.pickleFile))
            except IOError as e:
                print("I/O error(%s): %s" % (e.errno, e.strerror))
            except pickle.PicklingError:
                print("Could not pickle %s" %(self))
                
    def createDictInstance(self):
        """Returns a dictionary of the instances.

        The key is the instance Id, the value is a list of index.

        """
        dictinstance = {}
        for i in range(len(self.instancenumbers)):
            dictinstance.setdefault(self.instancenumbers[i], []).append(i)

        return dictinstance

    def createDictInstanceCount(self):
        """Returns a dictionary of the instances and their count.
        
        The keys are instance id and the values are the number of
        repetitions of such instance.
        
        """
        return dict((j, self.instancenumbers.count(j)) for j in set(self.instancenumbers))

    def splitByTrials(self, whichdata=None):
        """Splits the post-processed data arrays by trials.

        :keyword string whichdata: either 'evals' or 'funvals'
                                   determines the output
        :returns: this method returns dictionaries of arrays,
                  the key of the dictionaries being the instance id, the
                  value being a smaller post-processed data array
                  corresponding to the instance Id.
                  If whichdata is 'evals' then the array contains
                  function evaluations (1st column is alignment
                  targets).
                  Else if whichdata is 'funvals' then the output data
                  contains function values (1st column is alignment
                  budgets).
                  Otherwise this method returns a tuple of these two
                  arrays in this order.

        """
        dictinstance = self.createDictInstance()
        evals = {}
        funvals = {}

        for instanceid, idx in dictinstance.items():
            evals[instanceid] = self.evals[:,
                                           numpy.ix_(list(i + 1 for i in idx))]
            funvals[instanceid] = self.funvals[:,
                                           numpy.ix_(list(i + 1 for i in idx))]

        if whichdata :
            if whichdata == 'evals':
                return evals
            elif whichdata == 'funvals':
                return funvals

        return (evals, funvals)

    def generateRLData(self, targets):
        """Determine the running lengths for reaching the target values.

        :keyword list targets: target function values of interest

        :returns: dict of arrays, one array for each target. Each array
                  are copied from attribute :py:attr:`evals` of
                  :py:class:`DataSetList`: first element is a target
                  function value smaller or equal to the element of
                  targets considered and has for other consecutive
                  elements the corresponding number of function
                  evaluations.

        """
        res = {}
        # expect evals to be sorted by decreasing function values
        it = reversed(self.evals)
        prevline = numpy.array([-numpy.inf] + [numpy.nan] * self.nbRuns())
        try:
            line = advance_iterator(it)
        except StopIteration:
            # evals is an empty array
            return res #list()

        for t in sorted(targets):
            while line[0] <= t:
                prevline = line
                try:
                    line = advance_iterator(it)
                except StopIteration:
                    break
            res[t] = prevline.copy()

        return res
        # return list(res[i] for i in targets)
        # alternative output sorted by targets
        
    def detAverageEvals(self, targets):
        """Determine the average number of f-evals for each target 
        in ``targets`` list. If a target is not reached within trial
        itrail, self.maxevals[itrial] contributes to the average. 
        
        Equals to sum(evals(target)) / nbruns. If aRT is finite 
        this equals to aRT * psucc == (sum(evals) / ntrials / psucc) * psucc, 
        where aRT, psucc, and evals are a function of target.  
          
        """
        assert not any(np.isnan(self.evals[:][0]))  # target value cannot be nan

        evalsums = []
        for evalrow in self.detEvals(targets):
            idxnan = np.isnan(evalrow)
            evalsums.append(sum(evalrow[idxnan==False]) + sum(self.maxevals[idxnan]))
        
        averages = np.array(evalsums, copy=False) / self.nbRuns()
            
        if do_assertion:
            assert all([(ert == np.inf and ps == 0) or toolsdivers.equals_approximately(ert,  averages[i] / ps)
                            for i, (ert, ps) in enumerate(zip(self.detERT(targets), self.detSuccessRates(targets)))]) 
        
        return averages
    
    def detSuccesses(self, targets):
        """Determine for each target in targets the number of 
        successful runs, keeping in return list the order in targets. 
        
            dset.SuccessRates(targets) == np.array(dset.detNbSuccesses(targets)) / dset.nbRuns()
            
        are the respective success rates. 
        
        """
        succ = []
        for evalrow in self.detEvals(targets, copy=False):
            assert len(evalrow) == self.nbRuns()
            succ.append(self.nbRuns() - sum(np.isnan(evalrow)))
        return succ

    def detSuccessRates(self, targets):
        """return a np.array with the success rate for each target 
        in targets, easiest target first
        
        """
        return np.array(self.detSuccesses(targets)) / float(self.nbRuns())

    def detERT(self, targets):
        """Determine the average running time to reach target values.
        The value is numpy.inf, if the target was never reached. 

        :keyword list targets: target function values of interest

        :returns: list of average running times (# f-evals) for the
                  respective targets.

        """
        res = {}
        tmparray = numpy.vstack((self.target, self.ert)).transpose()
        it = reversed(tmparray)
        # expect this array to be sorted by decreasing function values

        prevline = numpy.array([-numpy.inf, numpy.inf])
        try:
            line = advance_iterator(it)
        except StopIteration:
            # evals is an empty array
            return list()

        for t in sorted(targets):
            while line[0] <= t:
                prevline = line
                try:
                    line = advance_iterator(it)
                except StopIteration:
                    break
            res[t] = prevline.copy() # is copy necessary? Yes. 

        # Return a list of aRT corresponding to the input targets in
        # targets, sorted along targets
        return list(res[i][1] for i in targets)

    def detEvals(self, targets, copy=True, bootstrap=False):
        """returns len(targets) data rows self.evals[idata, 1:] each row with 
        the closest but not larger target such that self.evals[idata, 0] <= target, 
        and self.evals[idata-1, 0] > target or in the "limit" cases the
        idata==0 line or the line np.array(self.nbRuns() * [np.nan]). 
        
        Makes by default a copy of the data, however this might change in
        future.
        
        """
        evalsrows = {}  # data rows, easiest target first
        idata = self.evals.shape[0] - 1  # current data line index 
        for target in sorted(targets):  # smallest most difficult target first
            if self.evals[-1, 0] > target:  # last entry is worse than target
                evalsrows[target] = np.array(self.nbRuns() * [np.nan])
                continue
            while idata > 0 and self.evals[idata - 1, 0] <= target:  # idata-1 line is good enough
                idata -= 1  # move up
            assert self.evals[idata, 0] <= target and (idata == 0 or self.evals[idata - 1, 0] > target)
            evalsrows[target] = self.evals[idata, 1:].copy() if copy else self.evals[idata, 1:]
            
        if do_assertion:
            assert all([all((np.isnan(evalsrows[target]) + (evalsrows[target] == self._detEvals2(targets)[i])))
                        for i, target in enumerate(targets)])

        if bootstrap:
            return [np.asarray(evalsrows[t])[np.random.randint(0,
                                len(evalsrows[t]), len(evalsrows[t]))]
                    for t in targets]
        return [evalsrows[t] for t in targets]
        
    def _detEvals2(self, targets):
        """Determine the number of evaluations to reach target values.

        :keyword seq or float targets: target precisions
        :returns: list of len(targets) values, each being an array of nbRuns FEs values

        """
        tmp = {}  # dict of eval-arrays (of size Ntrials), each entry for a given target
        # expect evals to be sorted by decreasing function values
        it = reversed(self.evals)
        prevline = numpy.array([-numpy.inf] + [numpy.nan] * self.nbRuns())
        try:
            line = advance_iterator(it)
        except StopIteration:
            # evals is an empty array
            return tmp #list()

        for t in sorted(targets):
            while line[0] <= t:
                prevline = line
                try:
                    line = advance_iterator(it)
                except StopIteration:
                    break
            tmp[t] = prevline.copy()

        return list(tmp[i][1:] for i in targets)

    def plot_funvals(self, **kwargs):
        """plot data of `funvals` attribute, versatile

        TODO: seems outdated on 19/8/2016
              (using "isfinite" instead of "np.isfinite" and not called
              from anywhere)
        """
        kwargs.setdefault('clip_on', False)
        for funvals in self.funvals.T[1:]:  # loop over the rows of the transposed array
            idx = isfinite(funvals > 1e-19)
            plt.loglog(self.funvals[idx, 0], funvals[idx], **kwargs)
            plt.ylabel('target $\Delta f$ value')
            plt.xlabel('number of function evaluations')
            plt.xlim(1, max(self.maxevals))
        return plt.gca()
    def plot(self, **kwargs):
        """plot data from `evals` attribute.

        `**kwargs` is passed to `matplolib.loglog`. 
        
        TODO: seems outdated on 19/8/2016
        ("isfinite" instead of "np.isfinite" and not called from anywhere)        
        """
        kwargs.setdefault('clip_on', False)
        for evals in self.evals.T[1:]:  # loop over the rows of the transposed array
            idx = np.logical_and(self.evals[:, 0] > 1e-19, isfinite(evals))
            # plt.semilogx(self.evals[idx, 0], evals[idx])
            if 1 < 3:
                plt.loglog(evals[idx], self.evals[idx, 0], **kwargs)
                plt.ylabel('target $\Delta f$ value')
                plt.xlabel('number of function evaluations')
                plt.xlim(1, max(self.maxevals))
            else:  # old version
                plt.loglog(self.evals[idx, 0], evals[idx])
                plt.gca().invert_xaxis()
                plt.xlabel('target $\Delta f$ value')
                plt.ylabel('number of function evaluations')
        return plt.gca()

class DataSetList(list):
    """List of instances of :py:class:`DataSet`.

    This class implements some useful slicing functions.

    Also it will merge data of DataSet instances that are identical
    (according to function __eq__ of DataSet).

    """
    #Do not inherit from set because DataSet instances are mutable which means
    #they might change over time.

    def __init__(self, args=[], check_data_type=True):
        """Instantiate self from a list of folder- or filenames or 
        ``DataSet`` instances.

        :keyword list args: strings being either info file names, folder
                            containing info files or pickled data files,
                            or a list of DataSets.

        Exceptions:
        Warning -- Unexpected user input.
        pickle.UnpicklingError

        """


        if not args:
            super(DataSetList, self).__init__()
            return

        if isinstance(args, string_types):
            args = [args]

        if len(args) and (isinstance(args[0], DataSet) or
                not check_data_type and hasattr(args[0], 'algId')):
            # TODO: loaded instances are not DataSets but
            # ``or hasattr(args[0], 'algId')`` fails in self.append
            # initialize a DataSetList from a sequence of DataSet
            for ds in args:
                self.append(ds, check_data_type)
            return

        if hasattr(args[0], 'algId'):
            print('try calling DataSetList() with option ' +
                  '``check_data_type=False``')
        fnames = []
        for name in args:
            if isinstance(name, string_types) and findfiles.is_recognized_repository_filetype(name):
                fnames.extend(findfiles.main(name))
            else:
                fnames.append(name)
        for name in fnames: 
            if isinstance(name, DataSet):
                self.append(name)
            elif name.endswith('.info'):
                self.processIndexFile(name)
            elif name.endswith('.pickle') or name.endswith('.pickle.gz'):
                try:
                    # cocofy(name)
                    if name.endswith('.gz'):
                        f = gzip.open(name)
                    else:
                        f = open(name,'r')
                    try:
                        entry = pickle.load(f)
                    except pickle.UnpicklingError:
                        print('%s could not be unpickled.' %(name))
                    f.close()
                    if genericsettings.verbose > 1:
                        print('Unpickled %s.' % (name))
                    try:
                        entry.instancenumbers = entry.itrials  # has been renamed
                        del entry.itrials
                    except:
                        pass
                    # if not hasattr(entry, 'detAverageEvals')
                    self.append(entry)
                    #set_trace()
                except IOError as e:
                    print("I/O error(%s): %s" % (e.errno, e.strerror))
            else:
                s = ('File or folder ' + name + ' not found. ' +
                              'Expecting as input argument either .info ' +
                              'file(s), .pickle file(s) or a folder ' +
                              'containing .info file(s).')
                warnings.warn(s)
                print(s)
            self.sort()
        self.current_testbed = testbedsettings.current_testbed #Wassim: to be sure
        data_consistent = True
        for ds in self:
            data_consistent = data_consistent and ds.consistency_check()
        if len(self) and data_consistent:
            print("  Data consistent according to consistency_check() in pproc.DataSet")
            
    def processIndexFile(self, indexFile):
        """Reads in an index (.info?) file information on the different runs."""

        try:
            f = openfile(indexFile)
            if genericsettings.verbose:
                print('Processing %s.' % indexFile)

            # Read all data sets within one index file.
            nbLine = 1
            data_file_names = []
            header = ''
            while True:
                try:
                    if 'indicator' not in header:
                        header = advance_iterator(f)
                        while not header.strip(): # remove blank lines
                            header = advance_iterator(f)
                            nbLine += 1
                        comment = advance_iterator(f)
                        if not comment.startswith('%'):
                            warnings.warn('Entry in file %s at line %d is faulty: '
                                          % (indexFile, nbLine) +
                                          'it will be skipped.')
                            nbLine += 2
                            continue

                    data = advance_iterator(f)  # this is the filename of the data file!?
                    data_file_names.append(data)
                    nbLine += 3
                    #TODO: check that something is not wrong with the 3 lines.
                    ds = DataSet(header, comment, data, indexFile)                    
                    if len(ds.instancenumbers) > 0:                    
                        self.append(ds)
                except StopIteration:
                    break
            # Close index file
            f.close()
            if len(data_file_names) != len(set(data_file_names)):
                warnings.warn("WARNING: a data file has been referenced" +
                    " several times in file %s:" % indexFile)
                data_file_names = sorted(data_file_names)
                for i in range(1, len(data_file_names)):
                    if data_file_names[i-1] == data_file_names[i]:
                        warnings.warn("    data file " + data_file_names[i])
                warnings.warn("  This is likely to produce spurious results.")

        except IOError as e:
            print('Could not load "%s".' % indexFile)
            print('I/O error(%s): %s' % (e.errno, e.strerror))

    def append(self, o, check_data_type=False):
        """Redefines the append method to check for unicity."""

        if check_data_type and not isinstance(o, DataSet):
            warnings.warn('appending a non-DataSet to the DataSetList')
            raise Exception('Expect DataSet instance.')
        isFound = False
        for i in self:
            if i == o:
                isFound = True
                if 11 < 3 and i.instancenumbers == o.instancenumbers and any([_i > 5 for _i in i.instancenumbers]):
                    warnings.warn("same DataSet found twice, second one from "
                        + str(o.indexFiles) + " with instances "
                        + str(i.instancenumbers))
                    # todo: this check should be done in a
                    #       consistency checking method, as the one below
                    break
                if set(i.instancenumbers).intersection(o.instancenumbers) \
                        and any([_i > 5 for _i in set(i.instancenumbers).intersection(o.instancenumbers)]):
                    warn_message = ('in DataSetList.processIndexFile: instances '
                                    + str(set(i.instancenumbers).intersection(o.instancenumbers))
                                    + ' found several times.'
                                    + ' Read data for F%d in %d-D might be inconsistent' % (i.funcId, i.dim))
                    warnings.warn(warn_message)
                                  # + ' found several times. Read data for F%(argone)d in %(argtwo)d-D ' % {'argone':i.funcId, 'argtwo':i.dim}
                # tmp = set(i.dataFiles).symmetric_difference(set(o.dataFiles))
                #Check if there are new data considered.
                if 1 < 3:
                    i.dataFiles.extend(o.dataFiles)
                    i.indexFiles.extend(o.indexFiles)
                    i.funvals = alignArrayData(VArrayMultiReader([i.funvals, o.funvals]))
                    i.finalfunvals = numpy.r_[i.finalfunvals, o.finalfunvals]
                    i.evals = alignArrayData(HArrayMultiReader([i.evals, o.evals]))
                    i.maxevals = numpy.r_[i.maxevals, o.maxevals]
                    i.computeERTfromEvals()
                    i.reference_values.update(o.reference_values)
                    if getattr(i, 'pickleFile', False):
                        i.modsFromPickleVersion = True

                    for j in dir(i):
                        if isinstance(getattr(i, j), list):
                            getattr(i, j).extend(getattr(o, j))

                else:
                    if getattr(i, 'pickleFile', False):
                        i.modsFromPickleVersion = False
                    elif getattr(o, 'pickleFile', False):
                        i.modsFromPickleVersion = False
                        i.pickleFile = o.pickleFile
                break
        if not isFound:
            list.append(self, o)

    def extend(self, o):
        """Extend with elements.

        This method is implemented to prevent problems since append was
        superseded. This method could be the origin of efficiency issue.

        """
        for i in o:
            self.append(i)

    def pickle(self, *args, **kwargs):
        """Loop over self to pickle each element."""
        for i in self:
            i.pickle(*args, **kwargs)

    def dictByAlg(self):
        """Returns a dictionary of instances of this class by algorithm.

        The resulting dict uses algId and comment as keys and the
        corresponding slices as values.

        """
        d = DictAlg()
        for i in self:
            d.setdefault((i.algId, ''), DataSetList()).append(i)
        return d

    def dictByDim(self):
        """Returns a dictionary of instances of this class by dimensions.

        Returns a dictionary with dimension as keys and the
        corresponding slices as values.

        """
        d = {}
        for i in self:
            d.setdefault(i.dim, DataSetList()).append(i)
        return d

    def dictByFunc(self):
        """Returns a dictionary of instances of this class by functions.

        Returns a dictionary with the function id as keys and the
        corresponding slices as values.

        """
        d = {}
        for i in self:
            d.setdefault(i.funcId, DataSetList()).append(i)
        return d

    def dictByDimFunc(self):
        """Returns a dictionary of instances of this class 
        by dimensions and for each dimension by function.

        Returns a dictionary with dimension as keys and the
        corresponding slices as values.
        
            ds = dsl.dictByDimFunc[40][2]  # DataSet dimension 40 on F2

        """
        dsld = self.dictByDim()
        for k in dsld:
            dsld[k] = dsld[k].dictByFunc()
        return dsld
        
    def dictByNoise(self):
        """Returns a dictionary splitting noisy and non-noisy entries."""
        sorted = {}
        
        for i in self:
            if i.funcId in range(1, 93):
                sorted.setdefault('noiselessall', DataSetList()).append(i)
            elif i.funcId in range(101, 131):
                sorted.setdefault('nzall', DataSetList()).append(i)
            else:
                warnings.warn('Unknown function id.')

        return sorted

    def isBiobjective(self):
        return any(i.isBiobjective() for i in self)
        
    def dictByFuncGroupBiobjective(self):
        """Returns a dictionary of instances of this class by function groups
        for bi-objective case.

        The output dictionary has function group names as keys and the
        corresponding slices as values. 

        """
        sorted = {} 
        for i in self:
            key = getattr(i, 'folder', '')
            if key:
                sorted.setdefault(key, DataSetList()).append(i)
            else:
                warnings.warn('Unknown group name.')

        return sorted

    def dictByFuncGroupSingleObjective(self):
        """Returns a dictionary of instances of this class by function groups
        for single objective case.

        The output dictionary has function group names as keys and the
        corresponding slices as values. Current groups are based on the
        GECCO-BBOB 2009-2013 function testbeds. 

        """
        sorted = {} 

        # TODO: this should be done in the testbed, not here
        if testbedsettings.current_testbed.name == 'bbob-constrained':
            for i in self:
                if i.funcId in range(1, 19):
                    sorted.setdefault('separ', DataSetList()).append(i)
                elif i.funcId in range(19, 43):
                    sorted.setdefault('hcond', DataSetList()).append(i)
                elif i.funcId in range(43, 49):
                    sorted.setdefault('multi', DataSetList()).append(i)
                else:
                    warnings.warn('Unknown function id.')
        else:
            for i in self:
                if i.funcId in range(1, 6):
                    sorted.setdefault('separ', DataSetList()).append(i)
                elif i.funcId in range(6, 10):
                    sorted.setdefault('lcond', DataSetList()).append(i)
                elif i.funcId in range(10, 15):
                    sorted.setdefault('hcond', DataSetList()).append(i)
                elif i.funcId in range(15, 20):
                    sorted.setdefault('multi', DataSetList()).append(i)
                elif i.funcId in range(20, 25):
                    sorted.setdefault('mult2', DataSetList()).append(i)
                elif i.funcId in range(101, 107):
                    sorted.setdefault('nzmod', DataSetList()).append(i)
                elif i.funcId in range(107, 122):
                    sorted.setdefault('nzsev', DataSetList()).append(i)
                elif i.funcId in range(122, 131):
                    sorted.setdefault('nzsmm', DataSetList()).append(i)
                else:
                    warnings.warn('Unknown function id.')
                    
        return sorted

    def dictByFuncGroup(self):
        """Returns a dictionary of instances of this class by function groups.

        The output dictionary has function group names as keys and the
        corresponding slices as values.  

        """
        if self.isBiobjective():
            return self.dictByFuncGroupBiobjective()
        else:
            return self.dictByFuncGroupSingleObjective()

    def getFuncGroups(self):
        """Returns a dictionary of function groups.
        
        The output dictionary has functions group names as keys 
        and function group descriptions as values.
        """
        if self.isBiobjective():
            dictByFuncGroup = self.dictByFuncGroupBiobjective()
            groups = OrderedDict(sorted((key, key.replace('_', ' ')) for key in dictByFuncGroup.keys()))
            return groups
        elif testbedsettings.current_testbed.name == 'bbob-constrained':
            groups = []
            if any(i.funcId in range(1, 19) for i in self):
                groups.append(('separ', 'Separable functions'))
            if any(i.funcId in range(19, 43) for i in self):
                groups.append(('hcond', 'Ill-conditioned functions'))
            if any(i.funcId in range(43, 49) for i in self):
                groups.append(('multi', 'Multi-modal functions'))

            return OrderedDict(groups)
        else:
            groups = []
            if any(i.funcId in range(1, 6) for i in self):
                groups.append(('separ', 'Separable functions'))
            if any(i.funcId in range(6, 10) for i in self):
                groups.append(('lcond', 'Misc. moderate functions'))
            if any(i.funcId in range(10, 15) for i in self):
                groups.append(('hcond', 'Ill-conditioned functions'))
            if any(i.funcId in range(15, 20) for i in self):
                groups.append(('multi', 'Multi-modal functions'))
            if any(i.funcId in range(20, 25) for i in self):
                groups.append(('mult2', 'Weak structure functions'))
            if any(i.funcId in range(101, 107) for i in self):
                groups.append(('nzmod', 'Moderate noise'))
            if any(i.funcId in range(107, 122) for i in self):
                groups.append(('nzsev', 'Severe noise'))
            if any(i.funcId in range(122, 131) for i in self):
                groups.append(('nzsmm', 'Severe noise multimod.'))

            return OrderedDict(groups)

    def dictByParam(self, param):
        """Returns a dictionary of DataSetList by parameter values.

        :returns: a dictionary with values of parameter param as keys and
                  the corresponding slices of DataSetList as values.

        """

        d = {}
        for i in self:
            d.setdefault(getattr(i, param, None), DataSetList()).append(i)
        return d

    def info(self, opt=None):
        """Display some information onscreen.

        :keyword string opt: changes size of output, can be 'all'
                             (default), 'short'

        """
        #TODO: do not integrate over dimension!!!
        #      loop over all data sets!?

        if len(self) > 0:
            print('%d data set(s)' % (len(self)))
            dictAlg = self.dictByAlg()
            algs = sorted(dictAlg.keys())
            sys.stdout.write('Algorithm(s): %s' % (algs[0][0]))
            for i in range(1, len(algs)):
                sys.stdout.write(', %s' % (algs[0][0]))
            sys.stdout.write('\n')

            dictFun = self.dictByFunc()
            functions = sorted(dictFun.keys())
            nbfuns = len(set(functions))
            splural = 's' if nbfuns > 1 else ''
            print('%d Function%s with ID%s %s' % (nbfuns, splural, splural, consecutiveNumbers(functions)))

            dictDim = self.dictByDim()
            dimensions = sorted(dictDim.keys())
            sys.stdout.write('Dimension(s): %d' % (dimensions[0]))
            for i in range(1, len(dimensions)):
                sys.stdout.write(', %d' % (dimensions[i]))
            sys.stdout.write('\n')

            maxevals = []
            for i in range(len(dimensions)):
                maxeval = []
                for d in dictDim[dimensions[i]]:
                    maxeval = int(max((d.mMaxEvals(), maxeval)))
                maxevals.append(maxeval)
            print('Max evals: %s' % str(maxevals))

            if opt == 'all':
                print('Df      |     min       10      med       90      max')
                print('--------|--------------------------------------------')
                evals = list([] for i in targets_displayed_for_info)
                for i in self:
                    tmpevals = i.detEvals(targets_displayed_for_info)
                    for j in range(len(targets_displayed_for_info)):
                        evals[j].extend(tmpevals[j])
                for i, j in enumerate(targets_displayed_for_info): # never aggregate over dim...
                    tmp = toolsstats.prctile(evals[i], [0, 10, 50, 90, 100])
                    tmp2 = []
                    for k in tmp:
                        if not numpy.isfinite(k):
                            tmp2.append('%8f' % k)
                        else:
                            tmp2.append('%8d' % k)
                    print('%2.1e |%s' % (j, ' '.join(tmp2)))

            # display distributions of final values
        else:
            print(self)

    def sort(self, key1='dim', key2='funcId'):
        def cmp_fun(a, b):
            if getattr(a, key1) == getattr(b, key1):
                if getattr(a, key2) == getattr(b, key2):
                    return 0
                return 1 if getattr(a, key2) > getattr(b, key2) else -1                
            else:
                return 1 if getattr(a, key1) > getattr(b, key1) else -1
        sorted_self = list(sorted(self, key=functools.cmp_to_key(cmp_fun)))
        for i, ds in enumerate(sorted_self):
            self[i] = ds
        return self
    
        # interested in algorithms, number of datasets, functions, dimensions
        # maxevals?, funvals?, success rate?


    def run_length_distributions(self, dimension, target_values,
                                 fun_list=None,  # all functions
                                 reference_data_set_list=None,
                                 reference_scoring_function=lambda x:
                                        toolsstats.prctile(x, [5])[0],
                                 data_per_target=15,
                                 flatten_output_dict=True,
                                 simulated_restarts=False,
                                 bootstrap=False):
        """return a dictionary with an entry for each algorithm, or for
        only one algorithm the dictionary value if
        ``flatten_output_dict is True``, and the left envelope
        rld-array.

        For each algorithm the entry contains a sorted rld-array of
        evaluations to reach the targets on all functions in
        ``func_list`` or all functions in `self`, the list of solved
        functions, the list of processed functions. If the sorted
        rld-array is normalized by the reference score (after sorting),
        the last entry is the original rld.

        Example::

            %pylab
            dsl = cocopp.load(...)  # a single algorithm
            rld = dsl.run_length_distributions(10, [1e-1, 1e-3, 1e-5])
            step(rld[0][0], np.linspace(0, 1, len(rld[0][0]),
                 endpoint=True)

        TODO: change interface to return always rld_original and optional
        the scores to compare with such that we need to compute
        ``rld[0][0] / rld[0][-1]`` to get the current output?

        If ``reference_data_set_list is not None`` evaluations
        are normalized by the reference data, however
        the data remain to be sorted without normalization.

        :param simulated_restarts: use simulated trials instead of
            "raw" evaluations from calling `DataSet.detEvals`.
            `simulated_restarts` may be a `bool`, or a kwargs `dict`
            passed like ``**simulated_restarts`` to the method
            `DataSet.evals_with_simulated_restarts`, or it may indicate
            the number of simulated trials. By default, the first trial
            is chosen without replacement. That means, if the number of
            simulated trials equals to ``nbRuns()``, the result is the
            same as from `DataSet.detEvals`, bar the ordering of the
            data. If `bootstrap` is active, the number is set to
            ``nbRuns()`` and the first trial is chosen *with* replacement.
        :param bootstrap: ``if bootstrap``, the number of evaluations is
            bootstrapped within the instances/trials or via simulated
            restarts.

        """
        target_values = asTargetValues(target_values)
        dsl_dict = self.dictByDim()[dimension].dictByAlg()
        # selected dimension and go by algorithm
        rld_dict = {}  # result for each algorithm
        reference_scores = {}  # for each funcId a list of len(target_values)
        left_envelope = np.inf
        for alg in dsl_dict:
            rld_data = []  # 15 evaluation-counts per function and target
            ref_scores = []  # to compute rld_data / ref_scores element-wise
            funcs_processed = []
            funcs_solved = []
            for ds in dsl_dict[alg]:  # ds is a DataSet containing typically 15 trials
                if fun_list and ds.funcId not in fun_list:
                    continue
                assert dimension == ds.dim
                funcs_processed.append(ds.funcId)
                if not simulated_restarts:
                    evals = ds.detEvals(target_values((ds.funcId, ds.dim)),
                                        bootstrap=bootstrap)
                    if data_per_target is not None:
                        # make sure to get 15 numbers for each target
                        if 1 < 3:
                            evals = [np.sort(np.asarray(d)[toolsstats.randint_derandomized(0, len(d), data_per_target)])
                                         for d in evals]
                        else:  # this assumes that data_per_target is not smaller than nbRuns
                            evals = [np.sort(toolsstats.fix_data_number(d, data_per_target))
                                        for d in evals]
                else:
                    if isinstance(simulated_restarts, dict):
                        evals = ds.evals_with_simulated_restarts(
                                    target_values((ds.funcId, ds.dim)),
                                    bootstrap=bootstrap,
                                    **simulated_restarts)
                    elif 11 < 3 and bootstrap:  # TODO: to be removed, produce the bootstrap graph for dispersion estimate
                        n = ds.nbRuns()
                        evals = ds.evals_with_simulated_restarts(target_values((ds.funcId, ds.dim)),
                                                   samplesize=n,
                                                   randint=np.random.randint)
                    else:  # manage number of samples
                        # TODO: shouldn't number of samples be set to data_per_target?
                        if simulated_restarts is not True and simulated_restarts > 0:
                            n = simulated_restarts
                        else:
                            n = (data_per_target or 0) + 2 * ds.nbRuns() + genericsettings.simulated_runlength_bootstrap_sample_size
                        evals = ds.evals_with_simulated_restarts(
                                    target_values((ds.funcId, ds.dim)),
                                    bootstrap=bootstrap,
                                    samplesize=n)
                    if data_per_target is not None:
                        index = np.array(0.5 + np.linspace(0, n - 1, data_per_target, endpoint=True),
                                         dtype=int)
                        for i in range(len(evals)):
                            evals[i] = np.asarray(evals[i])[index]
                    # evals.complement_missing(data_per_target)  # add fully unsuccessful sample data

                if reference_data_set_list is not None:
                    if ds.funcId not in reference_scores:
                        if reference_scoring_function is None:
                            reference_scores[ds.funcId] = \
                                reference_data_set_list.det_best_data(
                                target_values((ds.funcId, ds.dim)),
                                ds.funcId, ds.dim, number=data_per_target)
                        else:
                            reference_scores[ds.funcId] = \
                                reference_data_set_list.det_best_data_lines(
                                target_values((ds.funcId, ds.dim)),
                                ds.funcId, ds.dim, reference_scoring_function)[1]
                            # value checking, could also be done later
                            for i, val in enumerate(reference_scores[ds.funcId]):
                                if not np.isfinite(val) and any(np.isfinite(evals[i])):
                                    raise ValueError('reference_value is not finite')
                                    # a possible solution would be to set ``val = 1``
                            reference_scores[ds.funcId] = \
                                np.array([data_per_target * [val]
                                    for val in reference_scores[ds.funcId]],
                                         copy=False)
                        for i, line in enumerate(reference_scores[ds.funcId]):
                            reference_scores[ds.funcId][i] = \
                                np.sort(np.asarray(line)[toolsstats.randint_derandomized(0, len(line), data_per_target)])
                                # np.sort(toolsstats.fix_data_number(line, data_per_target))
                    ref_scores.append(np.hstack(reference_scores[ds.funcId]))
                    # 'needs to be checked', qqq

                evals = np.hstack(evals)  # "stack" len(targets) * 15 values
                if any(np.isfinite(evals)):
                    funcs_solved.append(ds.funcId)
                rld_data.append(evals)

            funcs_processed.sort()
            funcs_solved.sort()
            assert map(int, np.__version__.split('.')) > [1, 4, 0], \
    """for older versions of numpy, replacing `nan` with `inf` might work
    for sorting here"""
            rld_data = np.hstack(rld_data)
            if reference_data_set_list is not None:
                ref_scores = np.hstack(ref_scores)
                idx = np.argsort(rld_data)
                if 11 < 3:  # original version to return normalized data
                    rld_original = rld_data[idx]
                    rld_data = rld_original / ref_scores[idx]
                else:
                    rld_data = rld_data[idx]
                    ref_scores = ref_scores[idx]
                    print("""interface of return values changed! Also: left_envelope is now computed w.r.t. original data""")
            else:
                rld_data.sort()  # returns None
                # nan are at the end now (since numpy 1.4.0)

            # check consistency
            if len(funcs_processed) > len(set(funcs_processed)):
                warnings.warn("function processed twice "
                              + str(funcs_processed))
                raise ValueError("function processed twice")
            if fun_list is not None and set(funcs_processed) != set(fun_list):
                warnings.warn("not all functions found for " + str(alg)
                    + " and computations disregarded " + str(ds.algId))
                continue

            left_envelope = np.fmin(left_envelope, rld_data)  # TODO: needs to be rld_data / ref_scores after interface change
            # fails if number of computed data are different
            rld_dict[alg] = [rld_data,
                             sorted(funcs_solved),
                             funcs_processed]
            if reference_data_set_list is not None:
                rld_dict[alg].append(ref_scores)

        for k, v in rld_dict.items():
            if v[2] != funcs_processed:
                print('TODO: HERE AN ASSERTION FAILED')
            # assert v[2] == funcs_processed  # the must all agree to the last

        if flatten_output_dict and len(rld_dict) == 1:
            return rld_dict.values()[0], left_envelope
        return rld_dict, left_envelope

    def get_all_data_lines(self, target_value, fct, dim):
        """return a list of all data lines in ``self`` for each
        algorithm and a list of the respective
        computed aRTs.

        Example
        -------
        Get all run lengths of all trials on f1 in 20-D to reach
        target 1e-7::

            data = dsl.get_all_data_lines(1e-7, 1, 20)[0]
            flat_data = np.hstack(data)
            plot(np.arange(1, 1+len(flat_data)) / len(flat_data),
                 sort(flat_data))  # sorted fails on nan

        """
        # TODO: make sure to get the same amount of data for each
        # algorithm / target!?
        assert np.isscalar(target_value)

        lines = []
        scores = []
        for ds in self:
            if ds.funcId != fct or ds.dim != dim:
                continue
            lines.append(ds.detEvals([target_value])[0])
            scores.append(ds.detERT([target_value])[0])

        return lines, scores

    def det_best_data(self, target_values, fct, dim,
                           number=15):
        """return a list of the ``number`` smallest evaluations over all
        data sets in ``self`` for each ``target in target_values``.

        Detail: currently, the minimal observed evaluation is computed
        instance-wise and the ``number`` "easiest" instances are returned.
        That is, if `number` is the number of instances, the best eval
        for each instance is returned.
        Also the smallest ``number`` evaluations regardless of instance
        are computed, but not returned.

        """
        try:
            target_values = target_values((fct, dim))
        except TypeError:
            target_values = target_values
        best_lines = len(target_values) * [[]]  # caveat: this is (can be?) the same instance of []
        best_dicts = [{} for i in range(len(target_values))]
        for ds in self:
            if ds.funcId != fct or ds.dim != dim:
                continue
            current_lines = ds.detEvals(target_values)
            assert len(current_lines) == len(best_lines) == len(target_values)
            for i in range(len(current_lines)):
                for j, instance in enumerate(ds.instancenumbers):
                    previous_val = best_dicts[i].setdefault(instance, np.inf)
                    best_dicts[i][instance] = min((previous_val, current_lines[i][j]))
                best_lines[i] = np.sort(np.hstack(
                    [best_lines[i], current_lines[i]]))
                best_lines[i] = best_lines[i][:min((number,
                                                    len(best_lines[i])))]
        # construct another best line instance-wise
        best_instances_lines = []
        for i in range(len(best_dicts)):
            vals = best_dicts[i].values()
            best_instances_lines.append(
                np.sort(vals)[:np.min((number, len(vals)))])

        if any(line is None for line in best_lines):
            warnings.warn('best data lines not determined, (f, dim)='
                          + str((fct, dim)))
        # print(best_lines[-1])
        # print(best_instances_lines[-1])
        # print(best_instances_lines[-1])
        assert len(best_lines) == len(best_instances_lines) == len(target_values)
        assert best_lines[-1][0] == best_instances_lines[-1][0]
        return best_instances_lines
        # return best_lines

    def det_best_data_lines(self, target_values, fct, dim,
                           scoring_function=None):
        """return a list of the respective best data lines over all data
        sets in ``self`` for each ``target in target_values`` and an
        array of the computed scores (ERT ``if scoring_function == 'ERT'``).

        A data line is the set of evaluations from all (usually 15) runs
        for a given target value. The score determines which data line is
        "best".

        If ``scoring_function is None``, the best is determined with method
        ``detERT``. Using ``scoring_function=lambda x:
        toolsstat.prctile(x, [5], ignore_nan=False)`` is another useful
        alternative.

        """
        try:
            target_values = target_values((fct, dim))
        except TypeError:
            target_values = target_values
        best_scores = np.array(len(target_values) * [np.inf])
        best_lines = len(target_values) * [None]
        for ds in self:
            if ds.funcId != fct or ds.dim != dim:
                continue
            current_lines = ds.detEvals(target_values)
            if scoring_function is None or scoring_function == 'ERT':
                current_scores = ds.detERT(target_values)
            else:
                current_scores = np.array([scoring_function(d)
                                           for d in current_lines], copy=False)
            assert len(current_lines) == len(best_lines)
            assert len(current_lines) == len(current_scores) \
                 == len(best_scores) == len(best_lines)
            for i in np.where(toolsdivers.less(current_scores,
                                               best_scores))[0]:
                best_lines[i] = current_lines[i]
                best_scores[i] = current_scores[i]

        if any(line is None for line in best_lines):
            warnings.warn('best data lines for f%s in %s-D could not be determined'
                          % (str(fct), str(dim)))
        return best_lines, best_scores

    def get_sorted_algorithms(self, dimension, target_values,
                              fun_list=None,
                              reference_dataset_list=None,
                              smallest_evaluation_to_use=3):
        """return list of the algorithms from ``self``, sorted by
        minimum loss factor in the ECDF.

        Best means to be within `loss` of the best algorithm at
        at least one point of the ECDF from the functions `fun_list`,
        i.e. minimal distance to the left envelope in the semilogx plot.

        ``target_values`` gives for each function-dimension pair a list of
        target values.

        TODO: data generation via run_length_distributions and sorting
        should probably be separated.

        """
        rld, left_envelope = self.run_length_distributions(
            dimension, target_values, fun_list,
            reference_data_set_list=reference_dataset_list)
        reference_algorithms = []
        idx = left_envelope >= smallest_evaluation_to_use
        for alg in rld:
            try:
                if reference_dataset_list:
                    reference_algorithms.append([alg, toolsstats.prctile(rld[alg][0][idx], [5])[0],
                                            rld[alg], left_envelope,
                                            toolsstats.prctile(rld[alg][0], [2, 5, 15, 25, 50], ignore_nan=False)])
                else:
                    reference_algorithms.append([alg, np.nanmin(rld[alg][0][idx] / left_envelope[idx]),
                                            rld[alg], left_envelope,
                                            toolsstats.prctile(rld[alg][0] / left_envelope, [2, 5, 15, 25, 50], ignore_nan=False)])
            except ValueError:
                warnings.warn(str(alg) + ' could not be processed for get_sorted_algorithms ')

        reference_algorithms.sort(key=lambda x: x[1])
        return reference_algorithms

    def get_reference_values_hash(self):
        all_reference_values = {}
        reference_values_hash = None
        for dataSet in self:
            # if reference values exist
            if dataSet.reference_values and \
                            dataSet.dim in testbedsettings.current_testbed.reference_values_hash_dimensions:
                key = '%d_%d' % (dataSet.funcId, dataSet.dim)
                all_reference_values[key] = dataSet.reference_values

            # If this is the reference algorithm then the reference values hash may exist.
            if reference_values_hash is None:
                reference_values_hash = getattr(dataSet, 'reference_values_hash', None)

        if not all_reference_values:
            return reference_values_hash

        reference_values_string = json.dumps(all_reference_values, sort_keys=True)
        result = hashlib.sha1(reference_values_string.encode('utf-8')).hexdigest()
        # The generated hash it's very long so we truncate it.
        return result[:16]


def parseinfoold(s):
    """Deprecated: Extract data from a header line in an index entry.

    Older but verified version of :py:meth:`parseinfo`

    The header line should be a string of comma-separated pairs of
    key=value, for instance: key = value, key = 'value'

    Keys should not use comma or quote characters.

    """
    # TODO should raise some kind of error...
    # Split header into a list of key-value
    list_kv = s.split(', ')

    # Loop over all elements in the list and extract the relevant data.
    # We loop backward to make sure that we did not split inside quotes.
    # It could happen when the key algId and the value is a string.
    p = re.compile('([^,=]+)=(.*)')
    list_kv.reverse()
    it = iter(list_kv)
    res = []
    while True:
        try:
            elem = advance_iterator(it)
            tmp = p.match(elem)
            while not tmp:
                elem = advance_iterator(it) + elem
                # add up elements of list_kv until we have a whole key = value

            elem0, elem1 = tmp.groups()
            elem0 = elem0.strip()
            elem1 = elem1.strip()
            if elem1.startswith('\'') and elem1.endswith('\''): # HACK
                elem1 = ('\'' + re.sub('([\'])', r'\\\1', elem1[1:-1]) + '\'')
            elem1 = ast.literal_eval(elem1)
            res.append((elem0, elem1))
        except StopIteration:
            break

    return res

def parseinfo(s):
    """Extract data from a header line in an index entry.

    Use a 'smarter' regular expression than :py:meth:`parseinfoold`.
    The header line should be a string of comma-separated pairs of
    key=value, for instance: key = value, key = 'value'

    Keys should not use comma or quote characters.

    """
    p = re.compile('\ *([^,=]+?)\ *=\ *(".+?"|\'.+?\'|[^,]+)\ *(?=,|$)')
    res = []
    for elem0, elem1 in p.findall(s):
        if elem1.startswith('\'') and elem1.endswith('\''): # HACK
            elem1 = ('\'' + re.sub(r'(?<!\\)(\')', r'\\\1', elem1[1:-1]) + '\'')
        try:
            elem1 = ast.literal_eval(elem1)
        except:
            if sys.version.startswith("2.6"):  # doesn't like trailing '\n'
                elem1 = ast.literal_eval(elem1.strip())  # can be default anyway?
            else:
                raise
        res.append((elem0, elem1))  # TODO: what are elem0 and elem1?
    return res


def align_list(list_to_process, evals):
    for i, item in enumerate(evals):
        if i + 1 < len(evals) and evals[i] == evals[i + 1]:
            list_to_process.insert(i, list_to_process[i])

    return list_to_process

def set_unique_algId(ds_list, ds_list_reference, taken_ids=None):
    """on return, elements in ``ds_list`` do not have an ``algId``
    attribute value from ``taken_ids`` or from
    ``ds_list_reference`` ``if taken_ids is None``.

    In case, ``BFGS`` becomes ``BFGS 2`` etc.

    """
    if taken_ids is None:
        taken_ids = []
        for ds in ds_list_reference:
            taken_ids.append(ds.algId)
    taken_ids = set(taken_ids)

    for ds in ds_list:
        if ds.algId in taken_ids:
            algId = ds.algId
            i = 2
            while algId + ' ' + str(i) in taken_ids:
                i += 1
            ds.algId = algId + ' ' + str(i)


def processInputArgs(args, process_background_algorithms=False):
    """Process command line arguments.

    Returns several instances of :py:class:`DataSetList`, and a list of 
    algorithms from a list of strings representing file and folder names,
    see below for details. This command operates folder-wise: one folder 
    corresponds to one algorithm.

    It is recommended that if a folder listed in args contain both
    :file:`info` files and the associated :file:`pickle` files, they be
    kept in different locations for efficiency reasons.

    :keyword list args: string arguments for folder names
    :keyword bool process_background_algorithms: option to process also background algorithms

    :returns (all_datasets, pathnames, datasetlists_by_alg):
      all_datasets
        a list containing all DataSet instances, this is to
        prevent the regrouping done in instances of DataSetList.
        Caveat: algorithms with the same name are overwritten!?
      pathnames
        a list of keys of datasetlists_per_alg with the ordering as
        given by the input argument args
      datasetlists_by_alg
        a dictionary which associates each algorithm via its input path
        name to a DataSetList

    """
    dsList = list()
    sortedAlgs = list()
    dictAlg = {}
    current_hash = None
    process_arguments(args, current_hash, dictAlg, dsList, sortedAlgs)
    if process_background_algorithms:
        genericsettings.foreground_algorithm_list.extend(sortedAlgs)
        for value in genericsettings.background.values():
            assert isinstance(value, (list, tuple, set))
            process_arguments(value, current_hash, dictAlg, dsList, sortedAlgs)

    store_reference_values(DataSetList(dsList))

    return dsList, sortedAlgs, dictAlg


def process_arguments(args, current_hash, dictAlg, dsList, sortedAlgs):
    for i in args:
        i = i.strip()
        if i == '':  # might cure an lf+cr problem when using cywin under Windows
            continue
        if findfiles.is_recognized_repository_filetype(i):
            filelist = findfiles.main(i)
            # Do here any sorting or filtering necessary.
            # filelist = list(i for i in filelist if i.count('ppdata_f005'))
            tmpDsList = DataSetList(filelist)
            for ds in tmpDsList:
                ds._data_folder = i
            # Nota: findfiles will find all info AND pickle files in folder i.
            # No problem should arise if the info and pickle files have
            # redundant information. Only, the process could be more efficient
            # if pickle files were in a whole other location.

            alg = i.rstrip(os.path.sep)
            if current_hash is not None and current_hash != tmpDsList.get_reference_values_hash():
                warnings.warn(" Reference values for the algorithm '%s' are different!" % alg)

            set_unique_algId(tmpDsList, dsList)
            dsList.extend(tmpDsList)
            current_hash = tmpDsList.get_reference_values_hash()
            # alg = os.path.split(i.rstrip(os.sep))[1]  # trailing slash or backslash
            # if alg == '':
            #    alg = os.path.split(os.path.split(i)[0])[1]
            print('  using:', alg)

            # Prevent duplicates
            if all(i != alg for i in sortedAlgs):
                sortedAlgs.append(alg)
                dictAlg[alg] = tmpDsList
        elif os.path.isfile(i):
            # TODO: a zipped tar file should be unzipped here, see findfiles.py
            txt = 'The post-processing cannot operate on the single file ' + str(i)
            warnings.warn(txt)
            continue
        else:
            txt = "Input folder '" + str(i) + "' could not be found."
            raise Exception(txt)


def store_reference_values(ds_list):

    dict_alg = ds_list.dictByAlg()
    for key, value in dict_alg.items():
        testbedsettings.update_reference_values(key[0], value.get_reference_values_hash())


class DictAlg(OrderedDict):
    def __init__(self, d=()):
        OrderedDict.__init__(self, d)  # was: super.__init(d)
        
    def by_dim(self):
        return dictAlgByDim(self) # TODO: put here actual implementation

def dictAlgByDim(dictAlg):
    """Returns a dictionary with problem dimension as key from
    a dictionary of DataSet lists. 

    The input argument is a dictionary with algorithm names as 
    keys and a list of :py:class:`DataSet` instances as values.
    The resulting dictionary will have dimension as key and as values
    dictionaries with algorithm names as keys.

    """
    # should become: 
    # return DictAlg(dictAlg).by_dim()
    
    res = {}

    # get the set of problem dimensions
    dims = set()
    tmpdictAlg = {} # will store DataSet by alg and dim
    for alg, dsList in dictAlg.items():
        tmp = dsList.dictByDim()
        tmpdictAlg[alg] = tmp
        dims |= set(tmp.keys())

    for d in dims:
        for alg in dictAlg:
            tmp = DataSetList()
            try:
                tmp = tmpdictAlg[alg][d]
            except KeyError:
                txt = ('No data for algorithm %s in %d-D.'
                       % (alg, d))
                warnings.warn(txt)

            if alg in res.setdefault(d, {}):
                txt = ('Duplicate data for algorithm %s in %d-D.'
                       % (alg, d))
                warnings.warn(txt)

            res.setdefault(d, OrderedDict()).setdefault(alg, tmp)
            # Only the first data for a given algorithm in a given dimension

    #for alg, dsList in dictAlg.items():
        #for i in dsList:
            #res.setdefault(i.dim, {}).setdefault(alg, DataSetList()).append(i)

    return res

def dictAlgByDim2(dictAlg, remove_empty=False):
    """Returns a dictionary with problem dimension as key.

    The difference with :py:func:`dictAlgByDim` is that there is an
    entry for each algorithm even if the resulting
    :py:class:`DataSetList` is empty.

    This function is meant to be used with an input argument which is a
    dictionary with algorithm names as keys and which has list of
    :py:class:`DataSet` instances as values.
    The resulting dictionary will have dimension as key and as values
    dictionaries with algorithm names as keys.

    """
    res = {}

    for alg, dsList in dictAlg.items():
        for i in dsList:
            res.setdefault(i.dim, OrderedDict()).setdefault(alg, DataSetList()).append(i)

    if remove_empty:
        raise NotImplementedError
        for dim, ds_dict in res.items():
            for alg, ds_dict2 in ds_dict.items():
                if not len(ds_dict2):
                    pass
            if not len(ds_dict):
                pass

    return res

def dictAlgByFun(dictAlg):
    """Returns a dictionary with function id as key.

    This method is meant to be used with an input argument which is a
    dictionary with algorithm names as keys and which has list of
    :py:class:`DataSet` instances as values.
    The resulting dictionary will have function id as key and as values
    dictionaries with algorithm names as keys.

    """
    res = {}
    funcs = set()
    tmpdictAlg = {}
    for alg, dsList in dictAlg.items():
        tmp = dsList.dictByFunc()
        tmpdictAlg[alg] = tmp
        funcs |= set(tmp.keys())

    for f in funcs:
        for alg in dictAlg:
            tmp = DataSetList()
            try:
                tmp = tmpdictAlg[alg][f]
            except KeyError:
                txt = ('No data for algorithm %s on function %d.'
                       % (alg, f)) # This message is misleading.
                warnings.warn(txt)

            if alg in res.setdefault(f, {}):
                txt = ('Duplicate data for algorithm %s on function %d-D.'
                       % (alg, f))
                warnings.warn(txt)

            res.setdefault(f, OrderedDict()).setdefault(alg, tmp)
            # Only the first data for a given algorithm in a given dimension

    return res

def dictAlgByNoi(dictAlg):
    """Returns a dictionary with noise group as key.

    This method is meant to be used with an input argument which is a
    dictionary with algorithm names as keys and which has list of
    :py:class:`DataSet` instances as values.
    The resulting dictionary will have a string denoting the noise group
    ('noiselessall' or 'nzall') and as values dictionaries with
    algorithm names as keys.

    """
    res = {}
    ng = set()
    tmpdictAlg = {}
    for alg, dsList in dictAlg.items():
        tmp = dsList.dictByNoise()
        tmpdictAlg[alg] = tmp
        ng |= set(tmp.keys())

    for n in ng:
        stmp = ''
        if n == 'nzall':
            stmp = 'noisy'
        elif n == 'noiselessall':
            stmp = 'noiseless'

        for alg in dictAlg:
            tmp = DataSetList()
            try:
                tmp = tmpdictAlg[alg][n]
            except KeyError:
                txt = ('No data for algorithm %s on %s function.'
                       % (alg, stmp))
                warnings.warn(txt)

            if alg in res.setdefault(n, {}):
                txt = ('Duplicate data for algorithm %s on %s functions.'
                       % (alg, stmp))
                warnings.warn(txt)

            res.setdefault(n, OrderedDict()).setdefault(alg, tmp)
            # Only the first data for a given algorithm in a given dimension

    return res

def dictAlgByFuncGroup(dictAlg):
    """Returns a dictionary with function group as key.

    This method is meant to be used with an input argument which is a
    dictionary with algorithm names as keys and which has list of
    :py:class:`DataSet` instances as values.
    The resulting dictionary will have a string denoting the function
    group and as values dictionaries with algorithm names as keys.

    """
    res = {}
    fg = set()
    tmpdictAlg = {}
    for alg, dsList in dictAlg.items():
        tmp = dsList.dictByFuncGroup()
        tmpdictAlg[alg] = tmp
        fg |= set(tmp.keys())  # | is bitwise OR

    for g in fg:
        for alg in dictAlg:
            tmp = DataSetList()
            try:
                tmp = tmpdictAlg[alg][g]
            except KeyError:
                txt = ('No data for algorithm %s on %s functions.'
                       % (alg, g))
                warnings.warn(txt)

            if alg in res.setdefault(g, {}):
                txt = ('Duplicate data for algorithm %s on %s functions.'
                       % (alg, g))
                warnings.warn(txt)

            res.setdefault(g, OrderedDict()).setdefault(alg, tmp)
            # Only the first data for a given algorithm in a given dimension

    return res

# TODO: these functions should go to different modules. E.g. tools.py and toolsstats.py renamed as stats.py

