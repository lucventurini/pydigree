from itertools import izip
from bisect import bisect_right

import numpy as np

from pydigree.exceptions import NotMeaningfulError
from pydigree.cyfuncs import fastfirstitem
from pydigree.io.genomesimla import read_gs_chromosome_template
from pydigree.common import all_same_type


class AlleleContainer(object):

    " A base class for the interface *Alleles object must implement"

    def empty_like(self):
        raise NotImplementedError

    def copy_span(self, template, start, stop):
        raise NotImplementedError

    def dtype(self):
        raise NotImplementedError

    def __eq__(self, other):
        raise NotImplementedError


class LabelledAlleles(AlleleContainer):

    def __init__(self, spans=None, chromobj=None, nmark=None):
        if not (chromobj or nmark):
            raise ValueError('One of chromobj or nmark must be specified')
        self.spans = spans if spans is not None else []
        self.chromobj = chromobj
        self.nmark = nmark if self.chromobj is None else self.chromobj.nmark()

    def __eq__(self, other):
        if not isinstance(other, LabelledAlleles):
            return False
        return all(x == y for x, y in izip(self.spans, other.spans))

    def __getitem__(self, index):
        for span in self.spans:
            if span.contains(index):
                return span.ancestral_allele
        raise ValueError('Index out of bounds: {}'.format(index))

    def empty_like(self):
        return LabelledAlleles([], chromobj=self.chromobj, nmark=self.nmark)

    @property
    def dtype(self):
        return type(self)

    @staticmethod
    def founder_chromosome(ind, chromidx, hap, chromobj=None, nmark=None):
        n = nmark if not chromobj else chromobj.nmark()
        spans = [InheritanceSpan(ind, chromidx, hap, 0, n)]
        return LabelledAlleles(spans=spans, chromobj=chromobj, nmark=nmark)

    def add_span(self, new_span):
        if any(new_span.stop < x.stop for x in self.spans):
            raise ValueError('Overwriting not supported for LabelledAlleles')
        if len(self.spans) == 0 and new_span.start > 0:
            raise ValueError('Spans not contiguous')
        if len(self.spans) > 0 and (not new_span.start == self.spans[-1].stop):
            raise ValueError('Spans not contiguous')
        self.spans.append(new_span)

    def copy_span(self, template, copy_start, copy_stop):
        if not isinstance(template, LabelledAlleles):
            raise ValueError(
                'LabelledAlleles can only copy from other LabelledAlleles')

        if copy_stop is None:
            copy_stop = self.nmark

        for span in template.spans:
            if copy_start > span.stop or copy_stop < span.start:
                # These are the segments that aren't relevant
                # Ours           [-------------]
                # Template [---]      OR          [-----]
                continue
            elif copy_start == span.start and copy_stop == span.stop:
                # Ours             [----------] 
                # Template         [----------]

                new_span = InheritanceSpan(span.ancestor,
                                           span.chromosomeidx,
                                           span.haplotype,
                                           copy_start,
                                           copy_stop)

                self.add_span(new_span)

            elif span.contains(copy_start) and span.contains(copy_stop):
                # Ours:         [----------------]
                # Template:  [-----------------------]
                # The span we want is a sub-span of this span

                new_span = InheritanceSpan(span.ancestor,
                                           span.chromosomeidx,
                                           span.haplotype,
                                           copy_start,
                                           copy_stop)

                self.add_span(new_span)
            
            elif span.contains(copy_start):
                # Ours:        [------------------]
                # Template: [--------]
                new_span = InheritanceSpan(span.ancestor,
                                           span.chromosomeidx,
                                           span.haplotype,
                                           copy_start,
                                           span.stop)
                self.add_span(new_span)
           
            elif span.contains(copy_stop):
                # Ours       [-----------------]
                # Template:                [-----------]
                new_span = InheritanceSpan(span.ancestor,
                                           span.chromosomeidx,
                                           span.haplotype,
                                           span.start,
                                           copy_stop)
                self.add_span(new_span)
                return
          
            elif span.start > copy_start and span.stop < copy_stop:
                # This span is a sub-span of ours
                # Ours       [------------------------]
                # Template         [-------------]
                # Make a new span object anyway for object ownership purposes
                new_span = InheritanceSpan(span.ancestor,
                                           span.chromosomeidx,
                                           span.haplotype,
                                           span.start,
                                           span.stop)
                self.add_span(new_span)
            else: 
                raise ValueError('Unforseen combination of spans')
  
    def delabel(self):
        # Check to make sure all the founders are delabeled
        if not all_same_type(self.spans, InheritanceSpan):
            for span in self.spans:
                if isinstance(span.ancestral_chromosome, LabelledAlleles):
                    raise ValueError('Ancestral chromosome {} {} {}'
                                     'has not been delabeled'.format(
                                         self.individual,
                                         self.chromosomeidx,
                                         self.haplotype))

        nc = self.spans[0].ancestral_chromosome.empty_like()
        for span in self.spans:
            nc.copy_span(span.ancestral_chromosome, span.start, span.stop)
        return nc


class InheritanceSpan(object):
    __slots__ = ['ancestor', 'chromosomeidx', 'haplotype', 'start', 'stop']

    def __init__(self, ancestor, chromosomeidx, haplotype, start, stop):
        self.ancestor = ancestor
        self.chromosomeidx = chromosomeidx
        self.haplotype = haplotype
        self.start = start
        self.stop = stop

    def __repr__(self):
        return 'InheritanceSpan{}'.format(self.to_tuple())

    def __eq__(self, other):
        return (self.ancestor == other.ancestor and
                self.chromosomeidx == other.chromosomeidx and
                self.haplotype == other.haplotype and
                self.start == other.start and
                self.stop == other.stop)

    @property
    def ancestral_allele(self):
        return AncestralAllele(self.ancestor, self.haplotype)

    def contains(self, index):
        'Returns true if the index specified falls within this span'
        return self.start <= index <= self.stop

    @property
    def interval(self):
        return self.start, self.stop

    def to_tuple(self):
        return (self.ancestor, self.chromosomeidx, self.haplotype,
                self.start, self.stop)

    @property
    def ancestral_chromosome(self):
        return self.ancestor.genotypes[self.chromosomeidx][self.haplotype]


class AncestralAllele(object):
    __slots__ = ['ancestor', 'haplotype']

    def __init__(self, anc, hap):
        self.ancestor = anc
        self.haplotype = hap

    def __repr__(self):
        return 'AncestralAllele: {}: {}'.format(self.ancestor, self.haplotype)

    def __eq__(self, other):
        return (self.ancestor == other.ancestor and
                self.haplotype == other.haplotype)

    def __ne__(self, other):
        return not self == other


class Alleles(np.ndarray, AlleleContainer):

    ''' A class for holding genotypes '''
    def __new__(cls, data, template=None, **kwargs):
        obj = np.asarray(data, **kwargs).view(cls)
        obj.template = template
        return obj

    def __array__finalize__(self, obj):
        if obj is None:
            return
        self.template = getattr(obj, 'template', None)

    def __lt__(self, other):
        raise NotMeaningfulError(
            'Value comparisions not meaningful for genotypes')

    def __gt__(self, other):
        raise NotMeaningfulError(
            'Value comparisions not meaningful for genotypes')

    def __le__(self, other):
        raise NotMeaningfulError(
            'Value comparisions not meaningful for genotypes')

    def __ge__(self, other):
        raise NotMeaningfulError(
            'Value comparisions not meaningful for genotypes')

    @property
    def missingcode(self):
        return 0 if np.issubdtype(self.dtype, np.integer) else ''

    @property
    def missing(self):
        " Returns a numpy array indicating which markers have missing data "
        return self == self.missingcode

    def nmark(self):
        '''
        Return the number of markers represented by the
        Alleles object
        '''
        return self.shape[0]

    def copy_span(self, template, copy_start, copy_stop):
        self[copy_start:copy_stop] = template[copy_start:copy_stop]

    def empty_like(self, blank=True):
        ''' Returns an empty Alleles object like this one '''
        z = np.zeros(self.nmark(), dtype=self.dtype)

        return Alleles(z, template=self.template)


class SparseAlleles(AlleleContainer):

    '''
    An object representing a set of haploid genotypes efficiently by 
    storing allele differences from a reference. Useful for manipulating
    genotypes from sequence data (e.g. VCF files)
    '''

    def __init__(self, data, refcode=None, template=None):
        self.template = template

        data = np.array(data)
        self.dtype = data.dtype
        self.size = data.shape[0]
        if refcode is not None:
            self.refcode = refcode
        else:
            self.refcode = 0 if np.issubdtype(self.dtype, np.integer) else '0'
        self.non_refalleles = self._array2nonref(data,
                                                 self.refcode,
                                                 self.missingcode)
        self.missingindices = self._array2missing(data,
                                                  self.missingcode)

    def __lt__(self, other):
        raise NotMeaningfulError(
            'Value comparisions not meaningful for genotypes')

    def __gt__(self, other):
        raise NotMeaningfulError(
            'Value comparisions not meaningful for genotypes')

    def __le__(self, other):
        raise NotMeaningfulError(
            'Value comparisions not meaningful for genotypes')

    def __ge__(self, other):
        raise NotMeaningfulError(
            'Value comparisions not meaningful for genotypes')

    @staticmethod
    def _array2nonref(data, refcode, missingcode):
        '''
        Returns a dict of the form index: value where the data is 
        different than a reference value
        '''
        idxes = np.where(np.logical_and(data != refcode,
                                        data != missingcode))[0]
        nonref_values = data[idxes]
        return dict(izip(idxes, nonref_values))

    @staticmethod
    def _array2missing(data, missingcode):
        ''' Returns a list of indices where there are missingvalues '''
        return list(np.where(data == missingcode))

    @property
    def missingcode(self):
        return 0 if np.issubdtype(self.dtype, np.integer) else ''

    @property
    def missing(self):
        " Returns a numpy array indicating which markers have missing data "
        base = np.zeros(self.size, dtype=np.bool_)
        base[self.missingindices] = 1
        return base

    def __eq__(self, other):
        if isinstance(other, SparseAlleles):
            return self.__speq__(other)
        elif isinstance(other, Alleles):
            return (self.todense() == other)
        elif np.issubdtype(type(other), self.dtype):
            if self.template is None:
                raise ValueError(
                    'Trying to compare values to sparse without reference')

            eq = np.array(self.template.reference, dtype=self.dtype) == other
            neq_altsites = [k for k, v in self.non_refalleles if k != other]
            eq_altsites = [k for k, v in self.non_refalleles if k == other]
            eq[neq_altsites] = False
            eq[eq_altsites] = True
            return eq
        else:
            raise ValueError(
                'Uncomparable types: {} and {}'.format(self.dtype,
                                                       type(other)))

    def __speq__(self, other):
        if self.size != other.size:
            raise ValueError('Trying to compare different-sized chromosomes')

        # SparseAlleles saves differences from a reference,
        # so all reference sites are equal, and we mark everything True
        # to start, and go through and set any differences to False
        base = np.ones(self.size, dtype=np.bool_)

        nonref_a = self.non_refalleles.viewitems()
        nonref_b = other.non_refalleles.viewitems()

        # Get the alleles that are in nonref_a or nonref_b but not both
        neq_alleles = (nonref_a ^ nonref_b)
        neq_sites = fastfirstitem(neq_alleles)

        base[neq_sites] = 0

        return base

    def __ne__(self, other):
        return np.logical_not(self == other)

    def nmark(self):
        '''
        Return the number of markers (both reference and non-reference)
        represented by the SparseAlleles object
        '''
        return self.size

    def todense(self):
        '''
        Returns a non-sparse GenotypeChromosome equivalent
        to a SparseAlleles object.
        '''

        arr = np.zeros(self.size, dtype=np.uint8).astype(self.dtype)
        for loc, allele in self.non_refalleles.iteritems():
            arr[loc] = allele

        arr[self.missing] = self.missingcode

        return Alleles(arr, template=self.template)

    def empty_like(self):
        if not np.issubdtype(self.dtype, np.int):
            raise ValueError 
        raw = np.zeros(self.nmark(), dtype=self.dtype) + self.refcode
        return SparseAlleles(raw, refcode=self.refcode, template=self.template)


class ChromosomeTemplate(object):

    """
    Chromsome is a class that keeps track of marker frequencies and distances.
    Not an actual chromosome with genotypes, which you would find under
    Individual.

    Markers are currently diallelic and frequencies are given for minor
    alleles. Marker frequencies must sum to 1. Major allele frequency
    is then f = 1 - f_minor.

    linkageequilibrium_chromosome generates chromsomes that are generated from
    simulating all markers with complete independence (linkage equilibrium).
    This is not typically what you want: you won't find any LD for association
    etc. linkageequilibrium_chromosome is used for 'seed' chromosomes when
    initializing a population pool or when simulating purely family-based
    studies for linkage analysis.
    """

    def __init__(self, label=None):
        # Chromosome name
        self.label = label
        # A list of floats that represent the position of the marker in cM
        self.genetic_map = []
        # A list of integers that doesnt do anything. Just for decoration
        self.physical_map = []
        # A list of floats representing minor allele frequencies
        self.frequencies = np.array([])
        # List of marker names
        self.labels = []
        # Reference Alleles
        self.reference = []
        # Alternates
        self.alternates = []

    def __str__(self):
        return 'ChromosomeTemplate object %s: %s markers, %s cM' % \
            (self.label if self.label is not None else 'object',
             len(self.frequencies),
             max(self.genetic_map) if self.genetic_map else 0)

    @property
    def outputlabel(self):
        ''' The label outputted when written to disk '''
        if self.label:
            return self.label
        else:
            return 0

    def __iter__(self):
        return izip(self.labels, self.genetic_map, self.physical_map)

    def _iinfo(self):
        return izip(self.labels, self.genetic_map, self.physical_map,
                    self.frequencies)

    @staticmethod
    def from_genomesimla(filename):
        return read_gs_chromosome_template(filename)

    def nmark(self):
        ''' Returns the number of markers on the chromosome '''
        return len(self.genetic_map)

    def size(self):
        ''' Returns the size of the chromosome in centimorgans '''
        return self.genetic_map[-1] - self.genetic_map[0]

    def add_genotype(self, frequency=None, map_position=None, label=None,
                     bp=None, reference=None, alternates=None):
        try:
            frequency = float(frequency) if frequency is not None else -1
        except TypeError:
            raise ValueError('Invalid value for frequency %s' % frequency)
        self.genetic_map.append(map_position)
        self.frequencies = np.append(self.frequencies, frequency)
        self.physical_map.append(bp)
        self.labels.append(label)
        self.reference.append(reference)
        self.alternates.append(alternates)

    def set_frequency(self, position, frequency):
        """ Manually change an allele frequency """
        self.frequencies[position] = frequency

    def empty_chromosome(self, dtype=np.uint8):
        return Alleles(np.zeros(self.nmark(), dtype=dtype))

    def closest_marker(self, position, map_type='physical'):
        "Returns the index of the closest marker to a position"
        if map_type == 'physical':
            mp = self.physical_map
        elif map_type == 'genetic':
            mp = self.genetic_map
        else:
            raise ValueError("Map type must be 'physical' or 'genetic'")

        # Find the index in mp with value lte to position
        left_idx = bisect_right(mp, position) - 1

        if left_idx == self.nmark() - 1:
            # If we're already at the last marker, we know to just return
            # left_idx
            return left_idx

        right_idx = left_idx + 1

        right_pos = mp[right_idx]
        left_pos = mp[left_idx]

        if abs(right_pos - position) < abs(left_pos - position):
            return right_idx
        else:
            return left_idx

    def linkageequilibrium_chromosome(self):
        """ Returns a randomly generated chromosome """
        if (self.frequencies < 0).any():
            raise ValueError('Not all frequencies are specified')
        r = np.random.random(self.nmark())
        r = np.array(r < self.frequencies, dtype=np.uint8) + 1
        return Alleles(r)

    def linkageequilibrium_chromosomes(self, nchrom):
        """ Returns a numpy array of many randomly generated chromosomes """
        chroms = np.random.random((nchrom, self.nmark()))
        chroms = np.uint8((chroms < self.frequencies) + 1)
        return [Alleles(r) for r in chroms]
