""" Module to generate NIFTI + JSON from DICOM with dcm2niix"""

from dax import XnatUtils, ScanModule
import os
import glob
import logging
import nibabel as nib
import subprocess as sb
import shutil
from string import Template
import tempfile
import json

LOGGER = logging.getLogger('dax')

DCM2NIIX_PATH = '/data/mcr/centos7/dcm2niix/18_SEPT_2018/console/dcm2niix'
MODULE_NAME = 'dcm2niix_json'
TMP_PATH = '/tmp/' + MODULE_NAME
TEXT_REPORT = 'ERROR/WARNING for ' + MODULE_NAME + ':\n'
CMD_TEMPLATE = '''${dcm2niix} -z y -b y -f %s_%d ${dicom}'''


def sanitize_filename(filename):
    _dir = os.path.dirname(filename)
    _old = os.path.basename(filename)
    _new = "".join([x if (x.isalnum() or x == '.') else "_" for x in _old])
    if _old != _new:
        # Rename with the sanitized filename
        os.rename(os.path.join(_dir, _old), os.path.join(_dir, _new))
        filename = os.path.join(_dir, _new)

    return filename


class Module_dcm2niix_json(ScanModule):
    """ Module to convert dicom to nifti and json using dcm2niix """
    def __init__(self,
                 mod_name=MODULE_NAME,
                 directory=tempfile.mkdtemp(),
                 email=None,
                 text_report=TEXT_REPORT,
                 dcm2niixpath=DCM2NIIX_PATH,
                 scantype_filter=None):

        """ init function overridden from base-class"""
        super(Module_dcm2niix_json, self).__init__(
            mod_name, directory, email,
            text_report=text_report)
        self.dcm2niixpath = dcm2niixpath
        self.scantype_filter = scantype_filter
        print('DEBUG:' + self.dcm2niixpath)

    def prerun(self, settings_filename=''):
        """ prerun function overridden from base-class"""
        self.make_dir(settings_filename)

    def afterrun(self, xnat, project):
        """ afterrun function overridden from base-class"""
        if self.send_an_email:
            self.send_report()

        try:
            shutil.rmtree(self.directory)
        except Exception:
            LOGGER.warn('dcm2niix:afterrun:delete failed ' + self.directory)

    def needs_run(self, cscan, xnat):
        """ needs_run function overridden from base-class
                cscan = CacheScan object from XnatUtils
            return True or False
        """

        # Check output
        if XnatUtils.has_resource(cscan, 'JSON'):
            LOGGER.debug('Has JSON')
            return False

        # Check input
        if not XnatUtils.has_resource(cscan, 'DICOM'):
            LOGGER.debug('No DICOM resource')
            return False

        if XnatUtils.is_cscan_unusable(cscan):
            LOGGER.debug('Unusable scan')
            return False

        return True

    def run(self, scan_info, scan_obj):
        """ run function to convert dicom to nifti + json and upload data"""

        if not len(scan_obj.resource('DICOM').files().get()) > 0:
            LOGGER.debug('no DICOM files')
            return

        LOGGER.debug('downloading all DICOMs...')
        scan_obj.resource('DICOM').get(self.directory, extract=True)

        # convert dcm to nii via dcm2niix
        dcm_dir = os.path.join(self.directory, 'DICOM')
        success = self.dcm2niix(dcm_dir)

        # Check if json was created
        json_list = [f for f in os.listdir(dcm_dir) if f.endswith('.json')]
        if not json_list or not success:
            LOGGER.warn('{0} conversion failed'.format(scan_info['scan_id']))
            self.log_warning_error('dcm2nii json Failed', scan_info, error=True)

            # Set scan to unusable so it gets skipped and append to scan note
            scan_obj.attrs.set('quality', 'unusable')
            _note = scan_obj.attrs.get('note')
            if _note:
                _note = _note + ';'

            _note = _note + 'dcm2niix json FAILED'
            scan_obj.attrs.set('note', _note)
        else:
            self.upload_converted_images(dcm_dir, scan_obj, scan_info)

        # clean tmp folder
        self.clean_directory()

    def dcm2niix(self, dcm_path):
        """ convert dicom to nifti + json using dcm2niix """
        LOGGER.debug('converting dcm to nii...')
        cmd_data = {'dcm2niix': self.dcm2niixpath, 'dicom': dcm_path}
        cmd = Template(CMD_TEMPLATE).substitute(cmd_data)
        print('DEBUG:running cmd:' + cmd)
        try:
            sb.check_output(cmd.split())
        except sb.CalledProcessError:
            return False

        return True

    def upload_converted_images(self, dcm_dir, scan_obj, scan_info):
        """ upload images after checking them """
        nifti_list = []
        bval_path = ''
        bvec_path = ''
        json_path = ''

        LOGGER.debug('uploading the JSON files to XNAT...')

        # Get the NIFTI/bvec/bval/JSON files from the folder:
        for fpath in glob.glob(os.path.join(dcm_dir, '*')):
            if not os.path.isfile(fpath):
                continue

            if fpath.lower().endswith('.json') and not len(scan_obj.resource('JSON').files().get()) > 0:
                fpath = sanitize_filename(fpath)
                json_path = fpath

        # Check
        success = self.check_outputs(
            scan_info, json_path)

        if not success:
            print('not successful?')
            return

        # Upload
        #XnatUtils.upload_files_to_obj(
        #    nifti_list, scan_obj.resource('NIFTI'), remove=True)

        #if os.path.isfile(bval_path) and os.path.isfile(bvec_path):
            # BVAL/BVEC
        #    XnatUtils.upload_file_to_obj(
        #        bval_path, scan_obj.resource('BVAL'), remove=True)

        #    XnatUtils.upload_file_to_obj(
        #        bvec_path, scan_obj.resource('BVEC'), remove=True)

        if os.path.isfile(json_path):
            # JSON
            XnatUtils.upload_file_to_obj(
                json_path, scan_obj.resource('JSON'), remove=True)

        # more than one NIFTI uploaded
        #if len(nifti_list) > 1:
        #    LOGGER.warn('dcm2nii:{} multiple NIFTI'.format(
        #        scan_info['scan_id']))
        #    self.log_warning_error('multiple NIFTI', scan_info)

    def check_outputs(self, scan_info, json_path):
        """ Check outputs (opening nifti works)"""
        try:
            json_obj = open(json_path)
            json_data = json.load(json_obj)
        except nib.ImageFileError:
            LOGGER.warn(
                '''dcm2niix:{}:{} is not JSON'''.format(
                        scan_info['scan_id'],
                        os.path.basename(json_path)))
            self.log_warning_error(
                    'non-valid json created', scan_info, error=True)
            return False
        
        return True