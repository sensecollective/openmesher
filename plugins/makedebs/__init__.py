import logging, interfaces, os, datetime, sys
import glob, tempfile, subprocess

from StringIO import StringIO
from lib import nested_dict_merge

def dump_config_files(base_path, files_dict):
            for router in files_dict:
                for cfgfile in files_dict[router]:
                    cfgfile_path = os.path.abspath(base_path + '/' + router + '/' + cfgfile)
                    #logging.debug('Creating file %s for router %s' %(cfgfile_path, router))
                    fpath, fname = os.path.split(cfgfile_path)
                    _mkdirs(fpath)
                    fh = open(cfgfile_path, 'w')
                    fh.write(files_dict[router][cfgfile])
                    fh.close()
                    if fname == 'rules':
                        #BUG: Hack to make dpkg rules file executable
                        os.chmod(cfgfile_path, 0744)

def _mkdirs(path):
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno == 17:
            pass
        else:
            raise
    
    def files(self):
        """ Return a dictionary of routers containing a dictionary of filenames and contents """
        return self._files

class MakeDEBs(interfaces.IOpenMesherPackagePlugin):
    def activate(self):
        self._changelog_template = self._env.get_template('makedebs/changelog.conf')
        self._compat_template = self._env.get_template('makedebs/compat.conf')
        self._control_template = self._env.get_template('makedebs/control.conf')
        self._rules_template = self._env.get_template('makedebs/rules.conf')
        self._postinst_template = self._env.get_template('makedebs/postinst.conf')
    
    def setupargs(self, parser):
        parser.add_argument('--dpkg-version', default='1.0', action='store', help='Version number of the deb to create')

    #BUG: Need to fix the plugin arch so services can pass their config dirs to the package generator
    def process(self, mesh, configPlugins = None, cliargs = None, include_dirs = ['openvpn', 'quagga', 'shorewall', 'mesh-reverse.db'], restart_services = ['openvpn', 'quagga', 'shorewall']):
        logging.debug('Generating control files for package...')
        
        for router in mesh.routers:
            self._files[router] = {}
            changelog_date = datetime.datetime.strftime(datetime.datetime.now(), '%A, %d %B %Y %H:%M:%S -0800')
            
            #BUG: %z doesn't work for some dumb reason: http://www.aczoom.com/blog/ac/2007-02-24/strftime-in-python
            # changelog_date = datetime.datetime.strftime(datetime.datetime.utcnow(), '%A, %d %B %Y %H:%M:%S +%z')
            self._files[router]['/debian/changelog'] = self._changelog_template.render(
                hostname=mesh.routers[router].hostname.lower(),
                package_version = cliargs.dpkg_version,
                changelog_date = changelog_date,
            )
            
            self._files[router]['/debian/compat'] = self._compat_template.render()
            
            self._files[router]['/debian/control'] = self._control_template.render(
                hostname = mesh.routers[router].hostname.lower(),
                fqdn = mesh.routers[router].fqdn,
                changelog_date = changelog_date,
            )
            
            #BUG: Need to figure out which files need to be installed / services restarted from various plugins
            self._files[router]['/debian/rules'] = self._rules_template.render(
                hostname = mesh.routers[router].hostname.lower(),
                dirs = include_dirs,
            )
            
            self._files[router]['/debian/postinst'] = self._postinst_template.render(
                restart = restart_services,
            )
        logging.debug('Writing control files...')
        
        base_path = tempfile.mkdtemp(prefix='openmesher-')
        logging.info('Base path: %s' %(base_path))
        _mkdirs(base_path)
        
        dump_config_files(base_path, self._files)
        
        #Begin packaging into dpkg
        logging.info('Assembling files for debs...')
        for plugin in configPlugins:
            logging.debug('Processing package files from plugin %s...' %(plugin))
            dump_config_files(base_path, plugin.files())
        
        for router in self._files:
            logging.info('Building package for router: %s' %(router))
            router_path = os.path.abspath(base_path + '/' + router)
            sCMD = 'fakeroot debian/rules binary'
            process = subprocess.Popen(sCMD, shell=True, stdout=subprocess.PIPE, cwd=router_path)
            process.wait()
            if process.returncode != 0:
                raise Exception('Package generation failed in %s.  Do you have debhelper and fakeroot installed?' %(base_path))




#        print 'Connecting to %s' %(router)
#        fh = open(base_path + '/' + router.lower().split('.')[0] + '.deb')
#        ssh = paramiko.SSHClient()
#        ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
#        ssh.connect(router.lower(), username='root')
#        sftp = ssh.open_sftp()
#        print 'Transferring deb...'
#        remote_file = sftp.file('/root/%s.deb' %(router.lower().split('.')[0]), "wb")
#        remote_file.set_pipelined(True)
#        remote_file.write(fh.read())
#        sftp.close()
#        ssh.close()
#        print 'Complete'


