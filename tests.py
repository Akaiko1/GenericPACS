import pydicom
import pacs
import os
from pynetdicom import AE, evt, debug_logger, ALL_TRANSFER_SYNTAXES, AllStoragePresentationContexts, \
    StoragePresentationContexts

import config

if config.USE_DEBUG_LOGGER:
    debug_logger()


def handle_store(event):
    ds = event.dataset
    if config.DEBUG:
        print(f'Saving: {ds.SOPInstanceUID}')

    ds.file_meta = event.file_meta
    ds.save_as(os.path.join(config.STORAGE_DESTINATION, ds.SOPInstanceUID), write_like_original=False)

    return 0x0000


def run_test():
    ae = AE()
    ae.ae_title = 'STORE_SCP'

    ae.add_requested_context('1.2.840.10008.5.1.4.1.2.1.1')
    ae.add_requested_context('1.2.840.10008.5.1.4.1.2.1.2')

    contexts_list = [
        "1.2.840.10008.5.1.4.1.1.1.1",
        "1.2.840.10008.5.1.4.1.1.1.2",
        '1.2.840.10008.5.1.4.1.1.1.2.1',
        '1.2.840.10008.5.1.4.1.1.7',
        '1.2.840.10008.1.1',
        '1.2.840.10008.5.1.4.1.1.88.33',
        '1.2.840.10008.5.1.4.1.1.1.1.1.1',
        '1.2.840.10008.5.1.4.1.1.1',
        '1.2.840.10008.5.1.4.1.2.3.2',
        '1.2.840.10008.5.1.4.1.2.4.2',
    ]

    syntax_list = [
        # "1.2.840.10008.1.2",
        # "1.2.840.10008.1.2.1",
        "1.2.840.10008.1.2.4.57",
        "1.2.840.10008.1.2.4.70"
    ]

    for context in contexts_list:
        ae.add_supported_context(context, syntax_list)
        for syntax in syntax_list:
            ae.add_requested_context(context, syntax)

    handlers = [(evt.EVT_C_STORE, handle_store)]
    ae.start_server((config.IP, config.PORT + 1), evt_handlers=handlers, block=False)

    # Create our Identifier (query) dataset
    ds = pydicom.Dataset()
    ds.PatientName = ''
    ds.QueryRetrieveLevel = 'PATIENT'
    ds.SeriesInstanceUID = ''

    # Associate with the peer AE at IP 127.0.0.1 and port 11112
    assoc = ae.associate("0.0.0.0", config.PORT)
    if assoc.is_established:
        # Send the C-FIND request
        responses = assoc.send_c_find(ds, '1.2.840.10008.5.1.4.1.2.1.1')
        for (status, identifier) in responses:
            if status:
                print('C-FIND query status: 0x{0:04X}'.format(status.Status))
                print(identifier)
            else:
                print('Connection timed out, was aborted or received invalid response')

        # Release the association
        assoc.release()
    else:
        print('Association rejected, aborted or never connected')
    print('C-FIND Test Finished')

    assoc = ae.associate("0.0.0.0", config.PORT)
    if assoc.is_established:
        # Use the C-MOVE service to send the identifier
        responses = assoc.send_c_move(ds, ae.ae_title, '1.2.840.10008.5.1.4.1.2.1.2')
        for (status, identifier) in responses:
            if status:
                print('C-MOVE query status: 0x{0:04x}'.format(status.Status))
            else:
                print('Connection timed out, was aborted or received invalid response')

        # Release the association
        assoc.release()
    else:
        print('Association rejected, aborted or never connected')
    print('C-MOVE Test Finished')

    assoc = ae.associate("0.0.0.0", config.PORT)

    instances = []
    if config.STORAGE_TYPE == 'files':
        fdir = config.STORAGE_DESTINATION
        for fpath in os.listdir(fdir):
            instances.append(pydicom.dcmread(os.path.join(fdir, fpath)))

    if assoc.is_established:
        # Use the C-STORE service to send the dataset
        # returns the response status as a pydicom Dataset
        for ds in instances:
            print(f'Sending: {ds.StudyInstanceUID}')
            status = assoc.send_c_store(ds)

            # Check the status of the storage request
            if status:
                # If the storage request succeeded this will be 0x0000
                print('C-STORE request status: 0x{0:04x}'.format(status.Status))
            else:
                print('Connection timed out, was aborted or received invalid response')

        # Release the association
        assoc.release()
    else:
        print('Association rejected, aborted or never connected')
        print('C-STORE Test Finished')


if __name__ == '__main__':
    # pacs.run()
    run_test()
