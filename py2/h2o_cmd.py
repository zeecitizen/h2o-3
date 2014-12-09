
import h2o_nodes
from h2o_test import dump_json, verboseprint
import h2o_util
import h2o_print as h2p
from h2o_test import OutputObj

#************************************************************************
def runStoreView(node=None, **kwargs):
    if not node: node = h2o_nodes.nodes[0]

    print "\nStoreView:"
    # FIX! are there keys other than frames and models
    a = node.frames()
    # print "storeview frames:", dump_json(a)
    frameList = [af['key']['name'] for af in a['frames']]

    for f in frameList:
        print "frame:", f
    print "# of frames:", len(frameList)

    b = node.models()
    # print "storeview models:", dump_json(b)
    modelList = [bm['key'] for bm in b['models']]
    for m in modelList:
        print "model:", m
    print "# of models:", len(modelList)
    
    return {'keys': frameList + modelList}

#************************************************************************
def runExec(node=None, **kwargs):
    if not node: node = h2o_nodes.nodes[0]
    a = node.rapids(**kwargs)
    return a


def runInspect(node=None, key=None, verbose=False, **kwargs):
    if not key: raise Exception('No key for Inspect')
    if not node: node = h2o_nodes.nodes[0]
    a = node.frames(key, **kwargs)
    if verbose:
        print "inspect of %s:" % key, dump_json(a)
    return a

#************************************************************************
def infoFromParse(parse):
    if not parse:
        raise Exception("parse is empty for infoFromParse")
    # assumes just one result from Frames
    if 'frames' not in parse:
        raise Exception("infoFromParse expects parse= param from parse result: %s" % parse)
    if len(parse['frames'])!=1:
        raise Exception("infoFromParse expects parse= param from parse result: %s " % parse['frames'])

    # it it index[0] or key '0' in a dictionary?
    frame = parse['frames'][0]
    # need more info about this dataset for debug
    numCols = len(frame['columns'])
    numRows = frame['rows']
    key_name = frame['key']['name']

    return numRows, numCols, key_name


#************************************************************************
# make this be the basic way to get numRows, numCols
def infoFromInspect(inspect):
    if not inspect:
        raise Exception("inspect is empty for infoFromInspect")
    # assumes just one result from Frames
    if 'frames' not in inspect:
        raise Exception("infoFromInspect expects inspect= param from Frames result (single): %s" % inspect)
    if len(inspect['frames'])!=1:
        raise Exception("infoFromInspect expects inspect= param from Frames result (single): %s " % inspect['frames'])

    # it it index[0] or key '0' in a dictionary?
    frame = inspect['frames'][0]

    if frame['isText']:
        raise Exception("infoFromInspect only for parsed frames?: %s " % frame['isText'])

    # need more info about this dataset for debug
    columns = frame['columns']
    key_name = frame['key']['name']
    # look for nonzero num_missing_values count in each col
    missingList = []
    labelList = []
    typeList = []
    for i, colDict in enumerate(columns): # columns is a list
        mins = colDict['mins']
        maxs = colDict['maxs']
        missing = colDict['missing']
        label = colDict['label']
        stype = colDict['type']
        missingList.append(missing)
        labelList.append(label)
        typeList.append(stype)
        if missing!=0:
            print "%s: col: %s %s, missing: %d" % (key_name, i, label, missing)

    print "inspect typeList:", typeList

    # make missingList empty if all 0's
    if sum(missingList)==0:
        missingList = []

    # no type per col in inspect2
    numCols = len(frame['columns'])
    numRows = frame['rows']
    byteSize = frame['byteSize']

    print "\n%s numRows: %s, numCols: %s, byteSize: %s" % (key_name, numRows, numCols, byteSize)
    return missingList, labelList, numRows, numCols

#************************************************************************
# does all columns unless you specify column index.
# only will return first or specified column
def runSummary(node=None, key=None, expected=None, column=None, noPrint=False, **kwargs):
    if not key: raise Exception('No key for Summary')
    if not node: node = h2o_nodes.nodes[0]
    # return node.summary(key, **kwargs)

    class Column(object):
        def __init__(self, column):
            assert isinstance(column, dict)
            for k,v in column.iteritems():
                setattr(self, k, v) # achieves self.k = v

        def __iter__(self):
            for attr, value in self.__dict__.iteritems():
                yield attr, value

    inspect = runInspect(key=key)
    # change missingList definition: None if all empty, otherwise align to cols. 0 if 0?
    missingList, labelList, numRows, numCols = infoFromInspect(inspect)

    # doesn't take indices? only column labels?
    # return first column, unless specified

    if not (column is None or isinstance(column, (basestring, int))):
        raise Exception("column param should be string or integer index or None %s %s" % (type(column), column))

    # either return the first col, or the col indentified by label. the column identifed could be string or index?
    if column is None: # means the summary json when we ask for col 0, will be what we return (do all though)
        labelsToDo = labelList
    elif isinstance(column, int):
        labelsToDo = [labelList[column]]
    elif isinstance(column, basestring):
        labelsToDo = [column]
    else:
        raise Exception("wrong type %s for column %s" % (type(column), column))

    # we get the first column as result after walking across all, if no column parameter
    desiredResult = None
    for colIndex, label in enumerate(labelList):
        print "doing summary on %s" % label
        summaryResult = node.summary(key=key, column=label)
        if not desiredResult:
            desiredResult = summaryResult

        # verboseprint("column", column, "summaryResult:", dump_json(summaryResult))
        # this should be the same for all the cols? Or does the checksum change?
        frame = summaryResult['frames'][0]
        default_pctiles = frame['default_pctiles']
        checksum = frame['checksum']
        rows = frame['rows']
        coJson = frame['columns'][0]

        # assert len(columns) == numCols
        assert rows == numRows
        assert checksum !=0 and checksum is not None
        assert rows!=0 and rows is not None
        assert not frame['isText']
        # FIX! why is frame['key'] = None here?
        # assert frame['key'] == key, "%s %s" % (frame['key'], key)

        # only one column
        # checks that json is as expected, I guess.
        co = OutputObj(coJson, 'summary %s' % label)
        # just touching them will make sure they exist
        # how are enums binned. Stride of 1? (what about domain values)
        coList = [co.base, len(co.bins), len(co.data),
            co.domain, co.label, co.maxs, co.mean, co.mins, co.missing, co.ninfs, co.pctiles,
            co.pinfs, co.precision, co.sigma, co.str_data, co.stride, co.type, co.zeros]

        if not noPrint:
            for k,v in co:
                # only print [0] of mins and maxs because of the e308 values when they don't have dataset values
                if k=='mins' or k=='maxs':
                    print "%s[0]" % k, v[0]
                else:
                    print k, v

        if expected is not None:
            print "len(co.bins):", len(co.bins)
            print "co.label:", co.label, "mean (2 places):", h2o_util.twoDecimals(co.mean)
            # what is precision. -1?
            print "co.label:", co.label, "std dev. (2 places):", h2o_util.twoDecimals(co.sigma)

            print "FIX! hacking the co.pctiles because it's short by two"
            
            if co.pctiles:
                pctiles = [0] + co.pctiles + [0]
            else:
                pctiles = None

            # the thresholds h2o used, should match what we expected
                # expected = [0] * 5
            # Fix. doesn't check for expected = 0?
            if expected[0]: h2o_util.assertApproxEqual(co.mins[0], expected[0], tol=maxDelta, 
                msg='min is not approx. expected')
            if expected[1]: h2o_util.assertApproxEqual(pctiles[3], expected[1], tol=maxDelta, 
                msg='25th percentile is not approx. expected')
            if expected[2]: h2o_util.assertApproxEqual(pctiles[5], expected[2], tol=maxDelta, 
                msg='50th percentile (median) is not approx. expected')
            if expected[3]: h2o_util.assertApproxEqual(pctiles[7], expected[3], tol=maxDelta, 
                msg='75th percentile is not approx. expected')
            if expected[4]: h2o_util.assertApproxEqual(co.maxs[0], expected[4], tol=maxDelta, 
                msg='max is not approx. expected')

            # figure out the expected max error
            # use this for comparing to sklearn/sort
            MAX_QBINS = 1000
            if expected[0] and expected[4]:
                expectedRange = expected[4] - expected[0]
                # because of floor and ceil effects due we potentially lose 2 bins (worst case)
                # the extra bin for the max value, is an extra bin..ignore
                expectedBin = expectedRange/(MAX_QBINS-2)
                maxErr = expectedBin # should we have some fuzz for fp?

            else:
                print "Test won't calculate max expected error"
                maxErr = 0

            pt = h2o_util.twoDecimals(pctiles)

            # only look at [0] for now...bit e308 numbers if unpopulated due to not enough unique values in dataset column
            mx = h2o_util.twoDecimals(co.maxs[0])
            mn = h2o_util.twoDecimals(co.mins[0])

            print "co.label:", co.label, "co.pctiles (2 places):", pt
            print "default_pctiles:", default_pctiles
            print "co.label:", co.label, "co.maxs: (2 places):", mx
            print "co.label:", co.label, "co.mins: (2 places):", mn

            # FIX! why would pctiles be None? enums?
            if pt is None:
                compareActual = mn, [None] * 3, mx
            else:
                compareActual = mn, pt[3], pt[5], pt[7], mx

            h2p.green_print("actual min/25/50/75/max co.label:", co.label, "(2 places):", compareActual)
            h2p.green_print("expected min/25/50/75/max co.label:", co.label, "(2 places):", expected)

    return desiredResult


# this parses the json object returned for one col from runSummary...returns an OutputObj object
# summaryResult = h2o_cmd.runSummary(key=hex_key, column=0)
# co = h2o_cmd.infoFromSummary(summaryResult)
# print co.label
def infoFromSummary(summaryResult, column=0):
    # this should be the same for all the cols? Or does the checksum change?
    frame = summaryResult['frames'][0]
    default_pctiles = frame['default_pctiles']
    checksum = frame['checksum']
    rows = frame['rows']

    assert column < len(frame['columns']), "You're asking for column %s but there are only %s" % \
        (column, len(frame['columns']))
    coJson = frame['columns'][column]
      

    assert checksum !=0 and checksum is not None
    assert rows!=0 and rows is not None
    assert not frame['isText']

    # FIX! why is frame['key'] = None here?
    # assert frame['key'] == key, "%s %s" % (frame['key'], key)

    co = OutputObj(coJson, 'infoFromSummary %s' % coJson['label'])
    # how are enums binned. Stride of 1? (what about domain values)
    coList = [co.base, len(co.bins), len(co.data),
        co.domain, co.label, co.maxs, co.mean, co.mins, co.missing, co.ninfs, co.pctiles,
        co.pinfs, co.precision, co.sigma, co.str_data, co.stride, co.type, co.zeros]

    print "you can look at this attributes in the returned object (which is OutputObj if you assigned to 'co')"
    for k,v in co:
        print "co.%s" % k,

    print "\nReturning", co.label, "for column", column
    return co


