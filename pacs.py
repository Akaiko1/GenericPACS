from pynetdicom import AE, evt, StoragePresentationContexts, \
    AllStoragePresentationContexts, ALL_TRANSFER_SYNTAXES, debug_logger
from flask import Flask, request

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

    if ds.QueryRetrieveLevel == 'STUDY':
        if 'StudyInstanceUID' in ds:
            if ds.StudyInstanceUID not in ['*', '', '?']:
                matching = [
                    inst for inst in instances if inst.StudyInstanceUID == ds.StudyInstanceUID
                ]
            else:
                matching = [inst for inst in instances]

    if config.DEBUG:
        print(len(matching))

    matching = [m for m in matching if m.Modality in ['MG', 'CT']]

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

    if ds.QueryRetrieveLevel == 'STUDY':
        if 'StudyInstanceUID' in ds:
            if ds.StudyInstanceUID not in ['*', '', '?']:
                matching = [
                    inst for inst in instances if inst.StudyInstanceUID == ds.StudyInstanceUID
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


@app.route("/interactions", methods=['GET', 'POST'])
def display_actions():
    if request.method == 'POST':
        ae = get_ae()

        assoc = ae.associate(request.form['ip'], config.PORT)

        instances = get_stored_instances()
        instances = [ins for ins in instances if ins.StudyInstanceUID == request.form['study']]
        instances = [ins for ins in instances if ins.Modality in ['MG', 'CT']]

        if assoc.is_established:
            for ds in instances:
                print(f'Sending: {ds.StudyInstanceUID}')
                status = assoc.send_c_store(ds)

                if status:
                    print('C-STORE request status: 0x{0:04x}'.format(status.Status))
                else:
                    print('Connection timed out, was aborted or received invalid response')

            # Release the association
            assoc.release()
        else:
            print('Association rejected, aborted or never connected')

    instances = get_stored_instances()

    studies = []
    for instance in instances:
        if instance.StudyInstanceUID not in studies:
            studies.append(instance.StudyInstanceUID)

    studies_string = [f'<option value="{s}">{s}</option>' for s in studies]
    ip_string = [f'<option value="{s[0]}">{s[0]}</option>' for s in config.TRUSTED.values()]
    return f"""
    <!doctype html>
    <title>Интерактивный функционал PACS</title>
    <form method=post enctype=multipart/formdata>
    <label for="name">Отправить мне C-STORE:</label><br>
        <select id="study" name="study">{studies_string}</select>
        <select id="ip" name="ip">{ip_string}</select>
        <input type="submit">
    </form>
    """


def run():
    handlers = [(evt.EVT_C_STORE, handle_store),
                (evt.EVT_C_MOVE, handle_move),
                (evt.EVT_C_FIND, handle_find)]

    if config.USE_DEBUG_LOGGER:
        debug_logger()

    ae = get_ae()

    # if config.DEBUG:
    #     for context in ae.requested_contexts:
    #         print(context)

    ae.start_server((config.IP, config.PORT), evt_handlers=handlers, block=False)
    app.run(host=config.IP, port=config.PORT+2)


def get_ae():
    ae = AE()

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

    for context in AllStoragePresentationContexts:
        ae.add_supported_context(context.abstract_syntax, ALL_TRANSFER_SYNTAXES)

    for context in contexts_list:
        for syntax in syntax_list:
            ae.add_requested_context(context, syntax)
    return ae


if __name__ == '__main__':
    run()
