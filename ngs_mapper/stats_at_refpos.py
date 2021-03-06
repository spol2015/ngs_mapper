"""
Purpose
-------

This script is intended to aid in variant calling. It generates statistics about a given location in a BAM file.

Usage
-----

    .. code-block:: bash

        stats_at_refpos <bamfile> <regionstring>

Notes
-----

**regionstring**

The region string is a bit confusing if you are unsure what it is. The region string basically is how you tell samtools how to narrow down the results of what should be returned.
The format is as follows:
<reference identifier>:<start ref base position>-<end ref base position>

**Note:** You need to put the whole region string inside of quotes when you run stats_at_refpos

Examples:

* If you wanted only base 1046 from Ref1

    .. code-block:: bash

        stats_at_refpos somebamfile.bam 'Ref1:1046-1046'

About Quality Defaults: 
-----------------------

Currently we are now using 25 as the minimum quality threshold of q25, which is 10^(-25/10) or 0.00316 or 3.16 in 1000 chance of an error.

Tips & Tricks
-------------

* How do you get reference names that are in the BAM file?

    .. code-block:: bash

        samtools idxstats somebamfile.bam

    There is also a little blurp in the help of the script about how to use awk to get them as well
"""

import argparse
import sys
import itertools
from compat import OrderedDict
from ngs_mapper import samtools

def main():
    args = parse_args()
    return stats_at_pos( args.bamfile, args.regionstr, args.minmq, args.minbq, args.maxd )

def parse_args(args=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        description='''Gives stats about a given site in a bam file''',
        epilog='''You might use this command to get a list of available reference 
names to use for the regionstr. In the future there will be a list command for this
but for now use this:                                                 
samtools idxstats <in.bam> | awk '!/^*/ {print $1}' | sort | uniq'''
    )

    parser.add_argument(
        dest='bamfile',
        help='Bam file path for stats'
    )

    parser.add_argument(
        dest='regionstr',
        help='Region string to use in format of {refname}:{start}-{stop} where ' \
            'refname should be a reference identifier inside of the bamfile, ' \
            'start and stop are the reference position to look at. Example: ' \
            'Den1Reference:1046-1046. You can see more about regionstr in the ' \
            ' samtools documentation.'
    )

    default_minmq = 25.0
    parser.add_argument(
        '-mmq',
        '--min-mapping-qual',
        dest='minmq',
        type=float,
        default=default_minmq,
        help='Minimum mapping quality to be included in stats. Keep reads that are >= [Default: %(default)s]'
    )

    default_minbq = 25.0
    parser.add_argument(
        '-mbq',
        '--min-base-qual',
        dest='minbq',
        type=float,
        default=default_minbq,
        help='Minimum base quality to be included in stats. Keep bases that are >= [Default: %(default)s]'
    )

    default_maxdepth = 100000
    parser.add_argument(
        '-m',
        '--max-depth',
        dest='maxd',
        type=int,
        default=default_maxdepth,
        help='Maximum read depth at position to use[Default: %(default)s]'
    )
    
    return parser.parse_args(args)

def stats_at_pos( bamfile, regionstr, minmq, minbq, maxd ):
    base_stats = compile_stats( stats( bamfile, regionstr, minmq, minbq, maxd ) )
    print "Maximum Depth: {0}".format(maxd)
    print "Minumum Mapping Quality Threshold: {0}".format(minmq)
    print "Minumum Base Quality Threshold: {0}".format(minbq)
    print "Average Mapping Quality: {0}".format(base_stats['AvgMapQ'])
    print "Average Base Quality: {0}".format(base_stats['AvgBaseQ'])
    print "Depth: {0}".format(base_stats['TotalDepth'])
    for base, bstats in base_stats['Bases'].iteritems():
        print "Base: {0}".format(base)
        print "\tDepth: {0}".format( bstats['Depth'] )
        print "\tAverage Mapping Quality: {0}".format( bstats['AvgMapQ'] )
        print "\tAverage Base Quality: {0}".format( bstats['AvgBaseQ'] )
        print "\t% of Total: {0}".format( bstats['PctTotal'] )

    return base_stats

def stats( bamfile, regionstr, minmq, minbq, maxd ):
    out = samtools.mpileup( bamfile, regionstr, minmq, minbq, maxd )
    
    try:
        o = out.next()
        col = samtools.MPileupColumn( o )
        out.close()
        return col.base_stats()
    except StopIteration:
        return {
            'depth': 0,
            'mqualsum': 0.0,
            'bqualsum': 0.0
        }

def compile_stats( stats ):
    '''
        @param stats - {'depth': 0, 'mqualsum': 0, 'bqualsum': 0, 'ATGCN*..': [quals]} depth is total depth at a position and qualsum is sum of all quality scores bqualsum is read quality sums ATGCN* will be keys for each base seen and the list of quality scores for them
        @return - Dictionary of stats at each base and overall stats {'Bases': {'A': [quals], 'depth': 0, 'avgqual': 0.0}}
    '''
    if stats['depth'] == 0:
        return {
            'TotalDepth': 0,
            'AvgMapQ': 0,
            'AvgBaseQ': 0,
            'Bases': {}
        }
    base_stats = {}
    base_stats['TotalDepth'] = stats['depth']
    base_stats['AvgMapQ'] = round(stats['mqualsum']/stats['depth'],2)
    base_stats['AvgBaseQ'] = round(stats['bqualsum']/stats['depth'],2)
    base_stats['Bases'] = {}
    for base, quals in stats.iteritems():
        # Only interested in base stats in this loop
        if base not in ('depth','mqualsum','bqualsum'):
            if base not in base_stats['Bases']:
                base_stats['Bases'][base] = {}
            mquals = quals['mapq']
            bquals = quals['baseq']
            base_stats['Bases'][base]['Depth'] = len(mquals)
            base_stats['Bases'][base]['AvgMapQ'] = round(float(sum(mquals))/len(mquals),2)
            base_stats['Bases'][base]['AvgBaseQ'] = round(float(sum(bquals))/len(bquals),2)
            base_stats['Bases'][base]['PctTotal'] = round((float(len(mquals))/stats['depth'])*100,2)

    # Quit out of loop we are done
    # Order bases by PctTotal, then AvgBaseQ descending
    def cmp_func(x,y):
        x1 = x[1]
        y1 = y[1]
        if x1['PctTotal'] < y1['PctTotal']:
            return -1
        elif x1['PctTotal'] > y1['PctTotal']:
            return 1
        else:
            if x1['AvgBaseQ'] < y1['AvgBaseQ']:
                return -1
            elif x1['AvgBaseQ'] > y1['AvgBaseQ']:
                return 1
            else:
                return 0

    sorted_bases = sorted(
        base_stats['Bases'].items(),
        cmp=cmp_func,
        #key=lambda x: x[1]['PctTotal']+x[1]['AvgBaseQ'],
        reverse=True
    )
    base_stats['Bases'] = OrderedDict(sorted_bases)
    return base_stats

