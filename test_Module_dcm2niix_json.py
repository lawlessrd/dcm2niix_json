#!/usr/bin/env python

from dax import XnatUtils
import pyxnat
import Module_dcm2niix_json
import logging

logging.basicConfig(level=logging.DEBUG)

proj ='LANDMAN_UPGRAD'
subj = '229415'
sess = '229415'

with XnatUtils.get_interface() as xnat:

    csess = XnatUtils.CachedImageSession(xnat,proj,subj,sess)
    sess_obj = csess.full_object()
    sess_info = csess.info()
    #print(sess_info)

    m = Module_dcm2niix_json.Module_dcm2niix_json(
	    scantype_filter = 'T1W_3D_TFE',email = 'r.dylan.lawless@vumc.org')
    m.prerun()
    m.needs_run(csess, xnat)
    m.run(sess_info,sess_obj)
