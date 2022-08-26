from pynetdicom import AE, evt, StoragePresentationContexts, \
    AllStoragePresentationContexts, ALL_TRANSFER_SYNTAXES, debug_logger
from flask import Flask

import config
import pydicom
import os

app = Flask(__name__)


def handle_store(event):
    ds = event.dataset
    if config.DEBUG:
        print(f'Saving: {ds.SOPInstanceUID}')

    ds.file_meta = event.file_meta
    ds.save_as(os.path.join(config.STORAGE_DESTINATION, ds.SOPInstanceUID), write_like_original=False)

    return 0x0000


def handle_move(event):
    ds = event.identifier

    if config.DEBUG:
        print('Move Event')

    if 'QueryRetrieveLevel' not in ds:
        yield 0xC000, None
        return

    ae_name = event.move_destination

    if config.DEBUG:
        print(ae_name)

    if ae_name in config.TRUSTED:
        if config.DEBUG:
            print(config.TRUSTED[ae_name][0], config.TRUSTED[ae_name][1])

        yield config.TRUSTED[ae_name][0], config.TRUSTED[ae_name][1]

    matching = []
    instances = get_stored_instances()

    if config.DEBUG:
        print(len(instances))

    if ds.QueryRetrieveLevel == 'PATIENT':
        if 'PatientName' in ds:
            if ds.PatientName not in ['*', '', '?']:
                matching = [
                    inst for inst in instances if inst.PatientName == ds.PatientName
                ]
            else:
                matching = [inst for inst in instances]

    if config.DEBUG:
        print(len(matching))

    yield len(matching)

    for instance in matching:
        if event.is_cancelled:
            yield 0xFE00, None
            return

        yield 0xFF00, instance


def handle_find(event):
    ds = event.identifier

    # for elem in ds:
    #     print(ds[elem.tag])

    matching = []
    instances = get_stored_instances()

    if config.DEBUG:
        print(len(instances))

    if 'QueryRetrieveLevel' not in ds:
        yield 0xC000, None
        return

    if ds.QueryRetrieveLevel == 'PATIENT':
        if 'PatientName' in ds:
            if ds.PatientName not in ['*', '', '?']:
                matching = [
                    inst for inst in instances if inst.PatientName == ds.PatientName
                ]
            else:
                matching = [inst for inst in instances]

    for instance in matching:
        if event.is_cancelled:
            yield 0xFE00, None
            return

        identifier = pydicom.Dataset()

        for elem in ds:
            tag = elem.tag
            if tag in instance:
                identifier.add_new(tag, elem.VR, instance[tag].value)

        yield 0xFF00, identifier


def get_stored_instances():
    instances = []
    if config.STORAGE_TYPE == 'files':
        fdir = config.STORAGE_DESTINATION
        for fpath in os.listdir(fdir):
            instances.append(pydicom.dcmread(os.path.join(fdir, fpath)))
    return instances


@app.route("/")
def default_info():
    instances = get_stored_instances()
    instances = sorted(instances, key=lambda x: x.StudyInstanceUID)
    report_string = ''

    report_string += 'Following hosts are permitted to use C-MOVE:<br>'
    for name, reqs in config.TRUSTED.items():
        report_string += f'{name}: {reqs}<br>'

    report_string += '<br>'

    for idx, instance in enumerate(instances):
        report_string += f'{idx}. Modality {instance.Modality}: StudyUID {instance.StudyInstanceUID}<br>'

    return report_string


def run():
    handlers = [(evt.EVT_C_STORE, handle_store),
                (evt.EVT_C_MOVE, handle_move),
                (evt.EVT_C_FIND, handle_find)]

    ae = AE()

    if config.USE_DEBUG_LOGGER:
        debug_logger()

    ae.add_supported_context('1.2.840.10008.5.1.4.1.2.1.1')
    ae.add_supported_context('1.2.840.10008.5.1.4.1.2.1.2')

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

    # if config.DEBUG:
    #     for context in ae.requested_contexts:
    #         print(context)

    ae.start_server((config.IP, config.PORT), evt_handlers=handlers, block=False)
    app.run(host=config.IP, port=config.PORT+2)


if __name__ == '__main__':
    run()
