from nose.tools import eq_, raises
from nose.plugins.attrib import attr
from mock import Mock, MagicMock, patch

from .common import BaseClass

import os
from os.path import *

class Base(BaseClass):
    pass

@patch('bwa.seqio.concat_files')
class TestFunctionalCompileReads(Base):
    def test_reads_abspath_basepath_relpath(self,mock):
        from reads import compile_reads
        outputdir = 'output'
        outputdir = join(self.tempdir,outputdir)
        # Should return/create 3 files
        reads = [('p1_1.fastq','p1_2.fastq'),'/path/to/np1.fastq',('/path/to/p2_1.fastq.fastq','../p2_1.fastq.fastq'),'../np2.fastq']
        files = ['F.fq','R.fq','NP.fq']
        expected = {
            'F':join(outputdir,files[0]),
            'R':join(outputdir,files[1]),
            'NP':join(outputdir,files[2])
        }
        eq_( expected, compile_reads( reads, outputdir ) )
        eq_( len(mock.call_args_list), 3 )

    def test_compile_reads_paired_and_unpaired(self,mock):
        from reads import compile_reads
        outputdir = 'output'
        outputdir = join(self.tempdir,outputdir)
        # Should return/create 3 files
        reads = [('p1_1.fastq','p1_2.fastq'),'np1.fastq',('p2_1.fastq.fastq','p2_1.fastq.fastq'),'np2.fastq']
        files = ['F.fq','R.fq','NP.fq']
        expected = {
            'F':join(outputdir,files[0]),
            'R':join(outputdir,files[1]),
            'NP':join(outputdir,files[2])
        }
        eq_( expected, compile_reads( reads, outputdir ) )
        eq_( len(mock.call_args_list), 3 )

    def test_compile_reads_paired_only_single(self,mock):
        from reads import compile_reads
        outputdir = 'output'
        outputdir = join(self.tempdir,outputdir)
        # Should return/create 3 files
        reads = [('p1_1.fastq','p1_2.fastq')]
        files = ['F.fq','R.fq','NP.fq']
        expected = {
            'F':join(outputdir,files[0]),
            'R':join(outputdir,files[1]),
            'NP':None
        }
        eq_( expected, compile_reads( reads, outputdir ) )
        eq_( len(mock.call_args_list), 2 )

    def test_compile_reads_paired_only_multiple(self,mock):
        from reads import compile_reads
        outputdir = 'output'
        outputdir = join(self.tempdir,outputdir)
        # Should return/create 3 files
        reads = [('p1_1.fastq','p1_2.fastq'),('p2_1.fastq','p2_2.fastq')]
        files = ['F.fq','R.fq','NP.fq']
        expected = {
            'F':join(outputdir,files[0]),
            'R':join(outputdir,files[1]),
            'NP':None
        }
        eq_( expected, compile_reads( reads, outputdir ) )
        print mock.call_args_list
        eq_( len(mock.call_args_list), 2 )

    def test_compile_reads_unpaired_only_single(self,mock):
        from reads import compile_reads
        outputdir = 'output'
        outputdir = join(self.tempdir,outputdir)
        # Should return/create 3 files
        reads = ['p1.fastq']
        files = ['F.fq','R.fq','NP.fq']
        expected = {
            'F':None,
            'R':None,
            'NP':join(outputdir,files[2])
        }
        eq_( expected, compile_reads( reads, outputdir ) )
        eq_( len(mock.call_args_list), 1 )

    def test_compile_reads_unpaired_only_multiple(self,mock):
        from reads import compile_reads
        outputdir = 'output'
        outputdir = join(self.tempdir,outputdir)
        reads = ['p1.fastq','p2.fastq']
        files = ['F.fq','R.fq','NP.fq']
        expected = {
            'F':None,
            'R':None,
            'NP':join(outputdir,files[2])
        }
        eq_( expected, compile_reads( reads, outputdir ) )
        eq_( len(mock.call_args_list), 1 )

    def test_compile_reads_non_fastq(self,mock):
        from reads import compile_reads, InvalidReadFile
        outputdir = join(self.tempdir,'output')
        reads = ['np.sff','np.ab1','np.fastq.gz']
        try:
            compile_reads( reads, outputdir )
            assert False, "Did not raise InvalidReadFile"
        except InvalidReadFile as e:
            pass
        except Exception as e:
            assert False, "Did not raise InvalidReadFile"

    def test_compile_reads_three_item_tuple(self,mock):
        from reads import compile_reads, InvalidReadFile
        outputdir = join(self.tempdir,'output')
        reads = [('one.fastq','two.fastq','three.fastq')]
        try:
            compile_reads( reads, outputdir )
            assert False, "ValueError not raised"
        except ValueError as e:
            pass

    def test_compile_reads_emptyreadfilelist(self,mock):
        from reads import compile_reads, InvalidReadFile
        outputdir = join(self.tempdir,'output')
        reads = ['np.sff','np.ab1','np.fastq.gz']
        eq_({'F':None,'R':None,'NP':None}, compile_reads( [], outputdir ) )

class TestIntegrationCompileReads(Base):
    def test_compile_reads_outputdir_not_exist(self):
        outputdir = join(self.tempdir,'output')
        self.run_compile_reads(outputdir)

    def test_compile_reads_outputdir_exists(self):
        outputdir = join(self.tempdir,'output')
        os.mkdir(outputdir)
        self.run_compile_reads(outputdir)

    def run_compile_reads(self,outputdir):
        from reads import compile_reads
        # Read dir will allow relative and abspath testing
        readdir = 'reads'
        os.mkdir(readdir)
        reads = [
            ('p1_1.fastq','p1_2.fastq'), # current dir paired
            'np1.fastq', # Current dir np
            (join(readdir,'p2_1.fastq'), abspath(join(readdir,'p2_2.fastq'))), # relative and abs paired
            join(readdir,'np2.fastq'), # relative np
            join(abspath(readdir),'np2.fastq') # relative np
        ]
        read_contents = '@Read1\nATGCATGCATGC\n+\n111111111111\n'
        # Create all the files
        expected_linecounts = {'F':0,'R':0,'NP':0}
        for read in reads:
            if len(read) == 2:
                f = self.create_file(read[0],read_contents)
                r = self.create_file(read[1],read_contents)
                expected_linecounts['F'] += f
                expected_linecounts['R'] += r
            else:
                np = self.create_file(read,read_contents)
                expected_linecounts['NP'] += np

        result = compile_reads( reads, outputdir )
        assert os.access(result['F'],os.R_OK), "Did not create Forward file"
        assert os.access(result['R'],os.R_OK), "Did not create Reverse file"
        assert os.access(result['NP'],os.R_OK), "Did not create NonPaired file"
        for k,v in expected_linecounts.items():
            with open(result[k]) as fh:
                contents = fh.read()
                print contents
                eq_( v, len(contents.splitlines()) )
