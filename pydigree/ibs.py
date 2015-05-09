from itertools import izip

import numpy as np
from pydigree.cyfuncs import ibs


def get_ibs_states(ind1, ind2, chromosome_index, missingval=64):
    '''
    Efficiently returns IBS states across an entire chromsome.

    Arguments: Two individuals, and the index of the chromosome to scan. 

    Returns: A numpy array (dtype: np.uint8) of IBS states, with IBS between
    missing values coded as missingval
    '''
    if not 0 <= missingval <= 255:
        raise ValueError('Missing code must be between 0 and 255 inclusive')

    a, b = ind1.genotypes[chromosome_index]
    c, d = ind2.genotypes[chromosome_index]

    return chromwide_ibs(a, b, c, d, missingval=missingval)


def chromwide_ibs(a, b, c, d, missingval=64):
    a_eq_c = a == c
    a_eq_d = a == d
    b_eq_c = b == c
    b_eq_d = b == d

    # Catch which genotypes are missing (i.e. no '0' alleles)
    # so we can mark them later in the output
    missing = a.missing | b.missing | c.missing | d.missing

    # Any cross-genotype sharing is sufficient to be IBS=1
    ibs1 = a_eq_c | a_eq_d | b_eq_c | b_eq_d

    # Both alleles are IBS for IBS=2.
    ibs2 = (a_eq_c & b_eq_d) | (a_eq_d & b_eq_c)

    ibs_states = np.zeros(a.nmark(), dtype=np.uint8)
    ibs_states[ibs1] = 1
    ibs_states[ibs2] = 2
    ibs_states[missing] = missingval

    return ibs_states
