#!/usr/bin/env python

from dax import XnatUtils
import pyxnat
import Module_dcm2niix_json
import logging

logging.basicConfig(level=logging.DEBUG)

proj ='LANDMAN_UPGRAD'
subj = '229415'
sess = '229415'
scan = '101'

with XnatUtils.get_interface() as xnat:

    csess = XnatUtils.CachedImageSession(xnat,proj,subj,sess)
    sess_obj = csess.full_object()
    sess_info = csess.info()
    cscan = [s for s in csess.scans() if s.label() == scan][0]
    #print(sess_info)

    print(cscan.info())

    #scan_obj = xnat.select_scan(proj,subj,sess,scan)
    scan_obj = cscan.full_object()
    scan_info = cscan.info()
    #scan_obj.resource('secondary').get('.', extract=True)


    m = Module_dcm2niix_json.Module_dcm2niix_json(
        scantype_filter = 'T1W_3D_TFE',email = 'r.dylan.lawless@vumc.org')
    m.prerun()
    m.needs_run(csess, xnat)
    m.run(scan_info,scan_obj)