from imports import *
from . import tdir

class Base(common.BaseClass):
    vpath = join( tdir, '.miseqpipeline' )

    @classmethod
    def setUpClass( klass ):
        super(Base,klass).setUpClass()

        # If .virtpath exists then copy it and copy it back during tearDown
        klass.virtpathfile = join(dirname(dirname(abspath(__file__))), '.virtpath')
        if exists(klass.virtpathfile):
            shutil.copy(klass.virtpathfile, klass.virtpathfile + '.bk')

        klass.mock_pip()

        # Only install once because it takes a long time
        klass.returncode, klass.output = klass.run_installer( klass.vpath )

    @classmethod
    def mock_pip( klass ):
        ''' Because I don't want to wait for pip to finish every time '''
        # Ensure there is a bin directory to put pip in
        bindir = join(klass.vpath, 'bin')
        if not isdir( bindir ):
            os.makedirs( bindir )

        # Make pip bash script that just echos what is in the supplied requirements.txt file
        pip = join( bindir, 'pip' )
        with open(pip, 'w') as fh:
            fh.write( '#!/bin/bash\n' )
            fh.write( 'echo "Args to pip: $@"\n' )
            fh.write( 'echo "Python path: $(which python)"\n' )
            fh.write( 'cat $3 | while read line\n' )
            fh.write( 'do\n' )
            fh.write( '\t[[ $line =~ ^# ]] || echo "Installing $line"\n' )
            fh.write( 'done\n' )

        # Make pip executable
        os.chmod( pip, 0755 )
    
        return pip

    @classmethod
    def tearDownClass( klass ):
        super(Base,klass).tearDownClass()
        # Resore original virtpath
        if exists(klass.virtpathfile + '.bk'):
            shutil.move(klass.virtpathfile + '.bk', klass.virtpathfile)

    def setUp( self ):
        super( Base, self ).setUp()

        self.must_exist = (
            self.vpath,
            join(self.vpath,'bin'),
            join(self.vpath,'man1'),
            join(self.vpath,'lib','python2.7','site-packages')
        )
        # Must exist in vpath/bin
        self.scripts = (
            'base_caller.py',
            'consensuses.sh',
            'gen_flagstats.sh',
            'graph_mapunmap.py',
            'graphsample.py',
            'graphs.sh',
            'graph_times.py',
            'install.sh',
            'run_bwa_on_samplename.py',
            'runsample.py',
            'runsamplesheet.sh',
            'stats_at_refpos.py',
            'tagreads.py',
            'uninstall.sh',
            'vcf_consensus.py',
            'vcf_diff.py',
            'cutadapt'
        )
        self.python_packages = (
            'matplotlib',
            'vcf',
            'numpy',
            'bwa' 
        )
        os.chdir(tdir) 

    @classmethod
    def run_installer( klass, installpath ):
        # Install to test package tempdir
        script = klass.script_path('install.sh')
        return klass.run_script( '{} {}'.format( script, installpath ) )

class TestFunctional( Base ):
    @attr('current')
    def test_install_ran_successfully( self ):
        print self.output
        eq_( 0, self.returncode )
        ok_( 'failed' not in self.output )

    def test_links_scripts( self ):
        print self.output
        binpath = join( self.vpath, 'bin' )
        print os.listdir( binpath )
        for script in self.scripts:
            path = join( binpath, script )
            try:
                os.stat(path)
            except:
                print self.output
                ok_( False, "Script {} was not linked into virtenv bin directory to path {}".format(script,path) )

    def test_creates_virtenv( self ):
        print self.output
        print os.listdir( '.' )
        for me in self.must_exist:
            ok_( exists( me ), "install did not create {}".format(me) )

    @timed(1)
    def skip_test_wrong_python_version( self ):
        # Make a mock python that returns an older version number
        with open( 'python', 'w' ) as fh:
            fh.write( "#!/bin/bash\n" )
            fh.write( "echo 2.6.0" )
        # Make it executable
        st = os.stat('python')
        import stat
        os.chmod( 'python', st.st_mode | stat.S_IEXEC )
        script = self.script_path('install.sh')
        path=tdir + ':' + os.environ['PATH']
        ret, output = self.run_script( 'export PATH={}; {} {}'.format(path,script,self.vpath) )
        eq_( 'Cannot find python version 2.7.3+', output.rstrip() )
        eq_( 1, ret )

    def test_uninstall_works( self ):
        print self.run_script( self.script_path( 'uninstall.sh' ) )
        for me in self.must_exist:
            ok_( not exists( me ), "uninstall did not remove {}".format(me) )

    def test_python_packages_importable( self ):
        # Activate the env
        activate_this = join( self.vpath, 'bin', 'activate_this.py' )
        execfile(activate_this, dict(__file__=activate_this))
        for pkg in self.python_packages:
            ok_( __import__(pkg), "Could not import {}".format(pkg) )

<<<<<<< HEAD:tests/test_install.py
    def test_trimmomatic_installed( self ):
        print self.output
=======
    def skip_test_trimmomatic_installed( self ):
>>>>>>> setuppy:miseqpipeline/tests/_tst_install.py
        trimmomatic_path = glob( join( self.vpath, 'lib', 'Trimmo*' ) )[0]
        trimmomatic_jar_path = glob( join( trimmomatic_path, 'trimmo*' ) )[0]
        ok_( exists( trimmomatic_jar_path ), 'Did not install Trimmomatic' )
        cmd = 'java -jar {}'.format(trimmomatic_jar_path)
        rc, output = TestFunctional.run_script( cmd )
        eq_( 1, rc, '{} cannot execute correctly'.format(trimmomatic_jar_path) )
        ok_( 'Usage:' in output, 'Usage: was not in output from trimmomatic' )