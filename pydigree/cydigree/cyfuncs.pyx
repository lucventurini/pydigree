
import numpy as np
cimport numpy as np
cimport cython
from libc.stdint cimport int32_t, uint32_t

cpdef ibs(g1,g2, missingval=None):
    '''
    Returns how many alleles (0, 1, or 2) are identical-by-state between
    two diploid genotypes, or missingval if either genotype is missing
    '''
    a, b = g1
    c, d = g2
 
    if not (a and b and c and d):
        return missingval
    if (a == c and b == d) or (a == d and b == c):
        return 2
    elif a == c or a == d or b == c or b == d:
        return 1
    return 0


def runs(sequence, predicate, minlength=2):
    """
    Identifies runs of values in an interable for which predicate(value) 
    evaluates True and yields 2-tuples of the start and end (inclusive)
    indices
    """
    cdef int inrun = False
    cdef int start, stop
    
    if not sequence:
        return []

    out = []

    for i,v in enumerate(sequence):
        if not inrun and predicate(v):
            inrun = True
            start = i
    
        elif inrun and not predicate(v):
            inrun = False
            stop = i - 1
            if stop - start >= minlength:
                out.append((start, stop))

    if predicate(v) and inrun:
        stop = i
        if stop - start >= minlength:
            out.append((start, stop))
    return out


    
def runs_gte(sequence, double minval, int minlength=2):
    """
    Identifies runs of values in an iterable where each value is greater
    than or equal to a value minval, and returns a list of 2-tuples with
    the start and end (inclusive) indices of the runs
    """
    cdef int inrun = False
    cdef int start, stop, i, l

    i = 0
    out = [] 
    for i in range(len(sequence)):
        v = sequence[i]
        if not inrun and v >= minval:
            inrun = True
            start = i
        elif inrun and v < minval:
            inrun = False
            stop = i - 1
            if stop - start >= minlength:
                out.append((start, stop))
    if inrun and (i - start) >= minlength:
        out.append((start, i))
    return out


@cython.boundscheck(False)
@cython.wraparound(False)
def runs_gte_uint8(np.ndarray[np.uint8_t] sequence, np.uint8_t minval, Py_ssize_t minlength=1):
    cdef int inrun = False
    cdef Py_ssize_t start, stop, i
    cdef np.uint8_t v
    i = 0
    out = []
    for i in range(sequence.shape[0]):
        v = sequence[i]
        if not inrun and v >= minval:
            inrun = True
            start = i
        elif inrun and v < minval:
            inrun = False
            stop = i - 1
            if stop - start >= minlength:
                out.append((start, stop))
    if inrun and (i - start) >= minlength:
        out.append((start, i))
    return out

@cython.boundscheck(False)
@cython.wraparound(False)
def fastfirstitem(tuple2d):
    cdef Py_ssize_t i, l
    tuple2d = list(tuple2d)
    l = len(tuple2d)
    out = [-1]*l
    for i in range(l):
        out[i] = tuple2d[i][0]

    return out


def interleave(list a, list b):
    if len(a) != len(b):
        raise ValueError('Lists must be same length')
    cdef Py_ssize_t n = len(a)
    cdef list output = [None] * (2*n)
    cdef Py_ssize_t index
    for index in range(n):
        output[2*index] = a[index]
        output[(2*index) + 1] = b[index]

    return output 

def all_same_type(iter, t):
    "Returns true if all items in an iterable are the same type"
    for v in iter:
        if type(v) is not t:
            return False
    return True


def set_intervals_to_value(intervals, size, value):
    '''
    Creates a numpy integer array and sets intervals to a value
    Intervals should be in the format (start_idx, stop_idx_inclusive)
    '''

    cdef int start = 0
    cdef int stop = 0
    array = np.zeros(size, dtype=np.int)
    for start, stop in intervals:
        array[start:(stop+1)] = value
    return array


cdef class Segment:
    cdef object ind1, ind2, chromosome
    cdef public int32_t start, stop
    cdef public uint32_t physical_start, physical_stop

    def __init__(self, ind1, ind2, chromosome, start, stop, physical_position):
        self.ind1 = ind1
        self.ind2 = ind2
        self.chromosome = chromosome

        if start is None or stop is None:
            self.start, self.stop = -1, -1
        
        self.physical_start, self.physical_stop = physical_position