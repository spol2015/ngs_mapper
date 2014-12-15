"""
Purpose
=======

This script is now the main script for running everything necessary on a single sample. It is the script that is modified when more stages are added/removed/changed for the entirety of the pipeline.
Keep in mind that runsample.py simply requires all inputs that all stages provide that they do not provide for each other.

Current Pipeline Stages
-----------------------

* :py:mod:`miseqpipeline.trim_reads`
* :py:mod:`miseqpipeline.run_bwa_on_samplename <miseqpipeline.run_bwa>`
* :py:mod:`miseqpipeline.tagreads`
* :py:mod:`miseqpipeline.base_caller`
* :doc:`gen_flagstats`
* :py:mod:`miseqpipeline.graphsample`
* :py:mod:`miseqpipeline.fqstats`
* :py:mod:`miseqpipeline.vcf_consensus`

Basic Usage
===========

Get help usage

    .. code-block:: bash

        runsample.py -h

Usage Examples
==============

Creates a folder in the current directory called 00005-01 and puts all files from the run into that folder

    .. code-block:: bash

        runsample.py /path/to/ReadsBySample/00005-01 /path/to/Analysis/References/Den3__Thailand__FJ744727__2001.fasta 00005-01 -od 00005-01

Same example as above, but shortened a bit using bash variables

    .. code-block:: bash

        SAMPLE=00005-01
        REF=Den3__Thailand__FJ744727__2001.fasta
        READSDIR=/path/to/ReadsBySample
        REFDIR=/path/to/Analysis/References

        runsample.py ${READSDIR}/${SAMPLE} ${REFDIR}/${REF} ${SAMPLE} -od ${SAMPLE}

.. _runsample-output-directory:

Output Analysis Directory
-------------------------

* samplename.bam (:py:mod:`miseqpipeline.run_bwa_on_samplename`)
* samplename.bam.bai (:py:mod:`miseqpipeline.run_bwa_on_samplename`)
* samplename.bam.consensus.fasta (:py:mod:`miseqpipeline.vcf_consensus`)
* samplename.bam.qualdepth.json (:py:mod:`miseqpipeline.graphs`)
* samplename.bam.qualdepth.png (:py:mod:`miseqpipeline.graphs`)
* samplename.bam.vcf (:py:mod:`miseqpipeline.base_caller`)
* samplename.log (:py:mod:`miseqpipeline.runsample`)
* samplename.reads.png (:py:mod:`miseqpipeline.fqstats`)
* samplename.std.log (:py:mod:`miseqpipeline.runsample`)
* bwa.log (:py:mod:`miseqpipeline.run_bwa_on_samplename`)
* reference.fasta (:py:mod:`miseqpipeline.runsample`)
* reference.fasta.amb (:py:mod:`miseqpipeline.runsample`)
* reference.fasta.ann (:py:mod:`miseqpipeline.runsample`)
* reference.fasta.bwt (:py:mod:`miseqpipeline.runsample`)
* reference.fasta.pac (:py:mod:`miseqpipeline.runsample`)
* reference.fasta.sa( :py:mod:`miseqpipeline.runsample`)
* flagstats.txt (:py:mod:`miseqpipeline.gen_flagstats`)
* qualdepth (:py:mod:`miseqpipeline.graphs`)
    * sample.bam.qualdepth.referencename.png
    * ...
* trimmed_reads (:py:mod:`miseqpipeline.trim_reads`)
    * sampleread1.fasta
    * sampleread2.fasta
    * unpaired.fastq
* trim_stats (:py:mod:`miseqpipeline.trim_reads`)
    * sampleread.trim
"""

import argparse
import subprocess
import shlex
import sys
import os
import os.path
import tempfile
import logging
import shutil
import glob

# Everything to do with running a single sample
# Geared towards running in a Grid like universe(HTCondor...)
# Ideally the entire sample would be run inside of a prefix directory under
# /dev/shm and drop back on tmpdir if /dev/shm didn't exist

import log
# We will configure this later after args have been parsed
logger = None

class MissingCommand(Exception):
    pass

class AlreadyExists(Exception):
    pass

def parse_args( args=sys.argv[1:] ):
    from miseqpipeline import config
    conf_parser, args, config, configfile = config.get_config_argparse(args)

    parser = argparse.ArgumentParser(
        description='Runs a single sample through the pipeline',
        parents=[conf_parser]
    )

    parser.add_argument(
        dest='readsdir',
        help='Directory that contains reads to be mapped'
    )

    parser.add_argument(
        dest='reference',
        help='The path to the reference to map to'
    )

    parser.add_argument(
        dest='prefix',
        help='The prefix to put before every output file generated. Probably the samplename'
    )

    parser.add_argument(
        '-trim_qual',
        dest='trim_qual',
        default=config['trim_reads']['q']['default'],
        help=config['trim_reads']['q']['help'],
    )

    parser.add_argument(
        '-head_crop',
        dest='head_crop',
        default=config['trim_reads']['headcrop']['default'],
        help=config['trim_reads']['headcrop']['help'],
    )

    minth_default=0.8
    parser.add_argument(
        '-minth',
        dest='minth',
        default=config['base_caller']['minth']['default'],
        help=config['base_caller']['minth']['help'],
    )

    parser.add_argument(
        '--CN',
        dest='CN',
        default=config['tagreads']['CN']['default'],
        help=config['tagreads']['CN']['help'],
    )

    default_outdir = os.getcwd()
    parser.add_argument(
        '-od',
        '--outdir',
        dest='outdir',
        default=default_outdir,
        help='The output directory for all files to be put[Default: {0}]'.format(default_outdir)
    )

    args = parser.parse_args( args )
    args.config = configfile
    return args

def make_project_repo( projpath ):
    '''
    Turn a project into a git repository. Basically just git init a project path
    '''
    gitdir = os.path.join( projpath, '.git' )
    cmd = ['git', '--work-tree', projpath, '--git-dir', gitdir, 'init']
    output = subprocess.check_output( cmd, stderr=subprocess.STDOUT )
    logger.debug( output )

def run_cmd( cmdstr, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr, script_dir=None ):
    '''
        Runs a subprocess on cmdstr and logs some timing information for each command

        @params stdin/out/err should be whatever is acceptable to subprocess.Popen for the same
        
        @returns the popen object
    '''
    global logger
    cmd = shlex.split( cmdstr )
    if script_dir is not None:
        cmd[0] = os.path.join( script_dir, cmd[0] )
    logger.debug( "Running {0}".format(' '.join(cmd)) )
    try:
        p = subprocess.Popen( cmd, stdout=stdout, stderr=stderr, stdin=stdin )
        return p
    except OSError as e:
        raise MissingCommand( "{0} is not an executable?".format(cmd[0]) )

def main( args ):
    # So we can set the global logger
    global logger

    tmpdir = os.environ.get('TMPDIR', tempfile.tempdir)
    tdir = tempfile.mkdtemp('runsample', args.prefix, dir=tmpdir)
    bamfile = os.path.join( tdir, args.prefix + '.bam' )
    flagstats = os.path.join( tdir, 'flagstats.txt' )
    consensus = os.path.join( tdir, bamfile+'.consensus.fasta' )
    vcf = os.path.join( tdir, bamfile+'.vcf' )
    bwalog = os.path.join( tdir, 'bwa.log' )
    stdlog = os.path.join( tdir, args.prefix + '.std.log' )
    logfile = os.path.join( tdir, args.prefix + '.log' )
    CN = args.CN

    # Set the global logger
    config = log.get_config( logfile )
    logger = log.setup_logger( 'runsample', config )

    if os.path.isdir( args.outdir ):
        if os.listdir( args.outdir ):
            raise AlreadyExists( "{0} already exists and is not empty".format(args.outdir) )
    make_project_repo( tdir )

    logger.info( "--- Starting {0} --- ".format(args.prefix) )
    if args.config:
        logger.info( "--- Using custom config from {0} ---".format(args.config) )
    # Write all stdout/stderr to a logfile from the various commands
    with open(stdlog,'wb') as lfile:
        cmd_args = {
            'samplename': args.prefix,
            'tdir': tdir,
            'readsdir': args.readsdir,
            'reference': os.path.join(tdir, os.path.basename(args.reference)),
            'bamfile': bamfile,
            'flagstats': flagstats,
            'consensus': consensus,
            'vcf': vcf,
            'CN': CN,
            'trim_qual': args.trim_qual,
            'trim_outdir': os.path.join(tdir,'trimmed_reads'), 
            'head_crop': args.head_crop,
            'minth': args.minth,
            'config': args.config
        }

        # Best not to run across multiple cpu/core/threads on any of the pipeline steps
        # as multiple samples may be running concurrently already

        logger.debug( "Copying reference file {0} to {1}".format(args.reference,cmd_args['reference']) )
        shutil.copy( args.reference, cmd_args['reference'] )

        # Return code list
        rets = []

        # Trim Reads
        cmd = 'trim_reads.py {readsdir} -q {trim_qual} -o {trim_outdir} --head-crop {head_crop}'
        if cmd_args['config']:
            cmd += ' -c {config}'
        p = run_cmd( cmd.format(**cmd_args), stdout=lfile, stderr=subprocess.STDOUT )
        rets.append( p.wait() )
        if rets[-1] != 0:
            logger.critical( "{0} did not exit sucessfully".format(cmd.format(**cmd_args)) )

        # Mapping
        with open(bwalog, 'wb') as blog:
            cmd = 'run_bwa_on_samplename.py {trim_outdir} {reference} -o {bamfile}'
            if cmd_args['config']:
                cmd += ' -c {config}'
            p = run_cmd( cmd.format(**cmd_args), stdout=blog, stderr=subprocess.STDOUT )
            # Wait for the sample to map
            rets.append( p.wait() )
            # Everything else is dependant on bwa finishing so might as well die here
            if rets[-1] != 0:
                cmd = cmd.format(**cmd_args)
                logger.critical( "{0} failed to complete sucessfully. Please check the log file {1} for more details".format(cmd,bwalog) )
                sys.exit(1)

        # Tag Reads
        cmd = 'tagreads.py {bamfile} -CN {CN}'
        if cmd_args['config']:
            cmd += ' -c {config}'
        p = run_cmd( cmd.format(**cmd_args), stdout=lfile, stderr=subprocess.STDOUT )
        r = p.wait()
        if r != 0:
            logger.critical( "{0} did not exit sucessfully".format(cmd.format(**cmd_args)) )
        rets.append( r )

        # Variant Calling
        cmd = 'base_caller.py {bamfile} {reference} {vcf} -minth {minth}'
        if cmd_args['config']:
            cmd += ' -c {config}'
        p = run_cmd( cmd.format(**cmd_args), stdout=lfile, stderr=subprocess.STDOUT )
        r = p.wait()
        if r != 0:
            logger.critical( "{0} did not exit sucessfully".format(cmd.format(**cmd_args)) )
        rets.append( r )
        if rets[-1] != 0:
            cmd = cmd.format(**cmd_args)
            logger.critical( '{0} failed to complete successfully'.format(cmd.format(**cmd_args)) )

        # Flagstats
        with open(flagstats,'wb') as flagstats:
            cmd = 'samtools flagstat {bamfile}'
            p = run_cmd( cmd.format(**cmd_args), stdout=flagstats, stderr=lfile, script_dir='' )
            r = p.wait()
            if r != 0:
                logger.critical( "{0} did not exit sucessfully".format(cmd.format(**cmd_args)) )
            rets.append( r )

        # Graphics
        cmd = 'graphsample.py {bamfile} -od {tdir}'
        p = run_cmd( cmd.format(**cmd_args), stdout=lfile, stderr=subprocess.STDOUT )
        r = p.wait()
        if r != 0:
            logger.critical( "{0} did not exit sucessfully".format(cmd.format(**cmd_args)) )
        rets.append( r )

        # Read Graphics
        fastqs = ' '.join( glob.glob( os.path.join( cmd_args['trim_outdir'], '*.fastq' ) ) )
        cmd = 'fqstats.py -o {0}.reads.png {1}'.format(cmd_args['bamfile'].replace('.bam',''),fastqs)
        p = run_cmd( cmd, stdout=lfile, stderr=subprocess.STDOUT )
        r = p.wait()
        if r != 0:
            logger.critical( "{0} did not exit sucessfully".format(cmd) )
        rets.append( r )

        # Consensus
        cmd = 'vcf_consensus.py {vcf} -i {samplename} -o {consensus}'
        p = run_cmd( cmd.format(**cmd_args), stdout=lfile, stderr=subprocess.STDOUT )
        r = p.wait()
        if r != 0:
            logger.critical( "{0} did not exit sucessfully".format(cmd.format(**cmd_args)) )
        rets.append( r )

        # If sum is > 0 then one of the commands failed
        if sum(rets) != 0:
            logger.critical( "!!! There was an error running part of the pipeline !!!" )
            logger.critical( "Please check the logfile {0}".format(logfile) )
            sys.exit( 1 )
        logger.info( "--- Finished {0} ---".format(args.prefix) )

        subprocess.call( 'git add -A', cwd=tdir, shell=True, stdout=lfile, stderr=subprocess.STDOUT )
        subprocess.call( 'git commit -am \'runsample.py\'', cwd=tdir, shell=True, stdout=lfile, stderr=subprocess.STDOUT )

        logger.debug( "Moving {0} to {1}".format( tdir, args.outdir ) )
        # Cannot log any more below this line as the log file will be moved in the following code
        if not os.path.isdir( args.outdir ):
            shutil.move( tdir, args.outdir )
        else:
            file_list = [os.path.join(tdir,m) for m in os.listdir(tdir)]
            for f in file_list:
                shutil.move( f, args.outdir )
