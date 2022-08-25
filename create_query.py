import pydicom

ds = pydicom.Dataset()
ds.PatientName = ''
ds.QueryRetrieveLevel = 'PATIENT'
ds.SeriesInstanceUID = ''
ds.is_little_endian = False
ds.is_implicit_VR = False

pydicom.dcmwrite('query.dcm', ds)
