import unittest
import time
import os
import sys
import threading
import pprint
from helpers import OrthancTestCase, Helpers

from orthanc_api_client import OrthancApiClient, ChangeType, HttpError
from orthanc_api_client import helpers as OrthancHelpers

FAKE_SERVER_AET = 'FAKE_MOD'
FAKE_ALTERNATE_SERVER_AET = 'ALTERNATE'
FAKE_SERVER_PORT = 4999

import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fake DICOM SCP")

try:
    from pydicom import Dataset
    from pydicom.uid import (
        ExplicitVRLittleEndian,
        ImplicitVRLittleEndian,
        generate_uid,
    )
except ImportError as exc:  # pragma: no cover
    sys.stderr.write(f"[!] pydicom is required: {exc}\n    pip install pydicom\n")
    sys.exit(2)

try:
    from pynetdicom import AE, build_role, debug_logger

    # SOP class import path moved between pynetdicom 1.x and 2.x.
    try:
        from pynetdicom.sop_class import StorageCommitmentPushModel
    except ImportError:  # pynetdicom < 2.0
        from pynetdicom.sop_class import (
            StorageCommitmentPushModelSOPClass as StorageCommitmentPushModel,
        )
except ImportError as exc:  # pragma: no cover
    sys.stderr.write(f"[!] pynetdicom is required: {exc}\n    pip install pynetdicom\n")
    sys.exit(2)

from pydicom.dataset import Dataset
from pydicom.uid import ImplicitVRLittleEndian
from pynetdicom import AE, evt, build_role
from pynetdicom.sop_class import (
    StorageCommitmentPushModel,
)
from enum import Enum

import pathlib
import subprocess
import glob
here = pathlib.Path(__file__).parent.resolve()

STORAGE_COMMITMENT_SOP_CLASS = "1.2.840.10008.1.20.1"
STORAGE_COMMITMENT_SOP_INSTANCE = "1.2.840.10008.1.20.1.1"


class PendingTransaction:
    def __init__(self, transaction_uid, sop_instances):
        self.transaction_uid = transaction_uid
        self.sop_instances = sop_instances

class SimulatedFailure(Enum):
    NONE = 0
    CHANGE_TXUID = 1
    CHANGE_ONE_SOP_INSTANCE_UID = 2
    CHANGE_ONE_SOP_CLASS_UID = 3
    ADD_ONE_SOP_INSTANCE = 4
    REMOVE_ONE_SOP_INSTANCE = 5
    CHANGE_CALLED_AET = 6


class FakeStorageCommitmentServer:
    _should_stop = False
    _pending_transaction = None
    _simulated_failure = SimulatedFailure.CHANGE_TXUID
    _is_running = False
    _thread = None
    event_report_response_status = None

    def __init__(self, simulated_failure= SimulatedFailure):
        self._simulated_failure = simulated_failure


    def handle_n_action(self, event):
        """Receive Orthanc's Storage Commitment N-ACTION."""

        transaction_uid = event.action_information.TransactionUID

        sop_instances = []

        if hasattr(event.action_information, "ReferencedSOPSequence"):
            for item in event.action_information.ReferencedSOPSequence:
                sop_instances.append(
                    (
                        item.ReferencedSOPClassUID,
                        item.ReferencedSOPInstanceUID,
                    )
                )

        print()
        print("Received Storage Commitment N-ACTION")
        print("------------------------------------")
        print(f"Transaction UID: {transaction_uid}")

        for sop_class, sop_instance in sop_instances:
            print(f"  {sop_class} / {sop_instance}")

        if transaction_uid is not None:
            self._pending_transaction = PendingTransaction(
                transaction_uid,
                sop_instances,
            )

        # N-ACTION success
        return 0x0000, None


    def send_event_report(
        self,
        host,
        port,
        calling_ae,
        called_ae,
        transaction_uid,
        sop_instances
    ):
        """
        Open a new association to Orthanc and send an N-EVENT-REPORT.
        """

        ae = AE(ae_title=calling_ae)

        ae.add_requested_context(
            StorageCommitmentPushModel,
            [
                ImplicitVRLittleEndian,
            ],
        )

        # We initiate the association, but act as SCP for
        # Storage Commitment.
        role = build_role(
            StorageCommitmentPushModel,
            scp_role=True,
            scu_role=False,
        )

        assoc = ae.associate(
            host,
            port,
            ae_title=called_ae,
            ext_neg=[role],
        )

        if not assoc.is_established:
            print("Could not establish association")
            return

        ds = Dataset()

        ds.TransactionUID = transaction_uid

        ds.ReferencedSOPSequence = []

        for sop_class, sop_instance in sop_instances:
            item = Dataset()
            item.ReferencedSOPClassUID = sop_class
            item.ReferencedSOPInstanceUID = sop_instance
            ds.ReferencedSOPSequence.append(item)

        print()
        print("Sending N-EVENT-REPORT")
        print("----------------------")
        print(f"Transaction UID: {transaction_uid}")

        for sop_class, sop_instance in sop_instances:
            print(f"  {sop_class} / {sop_instance}")

        status, response = assoc.send_n_event_report(
            ds,
            1,  # Event Type 1 = Request Successful
            STORAGE_COMMITMENT_SOP_CLASS,
            STORAGE_COMMITMENT_SOP_INSTANCE,
        )

        if status is None:
            print("No N-EVENT-REPORT response")
        else:
            print(
                f"N-EVENT-REPORT response: "
                f"0x{status.Status:04X}"
            )
            self.event_report_response_status = status.Status

        assoc.release()
        

    def start(self):
        self._thread = threading.Thread(target=self.execute)
        self._thread.start()
        while not self._is_running:
            time.sleep(0.1)


    def execute(self):
        ae = AE(ae_title=FAKE_SERVER_AET)

        # Receive N-ACTION from Orthanc.
        ae.add_supported_context(
            StorageCommitmentPushModel,
            [
                ImplicitVRLittleEndian,
            ],
            scp_role=True,
            scu_role=False,
        )

        handlers = [
            (
                evt.EVT_N_ACTION,
                self.handle_n_action,
            ),
        ]

        print(
            f"Listening on 0.0.0.0:{FAKE_SERVER_PORT} "
            f"as {FAKE_SERVER_AET}"
        )

        # Start SCP in the background so that we can interact
        # with it from the command line.
        server = ae.start_server(
            ("0.0.0.0", FAKE_SERVER_PORT),
            block=False,
            evt_handlers=handlers,
        )
        self._is_running = True

        try:
            while not self._should_stop:
                if self._pending_transaction is None:
                    time.sleep(0.2)
                    continue

                transaction = self._pending_transaction

                if self._simulated_failure == SimulatedFailure.NONE:
                    self.send_event_report(
                        host=Helpers.get_orthanc_ip(),
                        port=Helpers.get_orthanc_dicom_port(),
                        calling_ae=FAKE_SERVER_AET,
                        called_ae='ORTHANC',
                        transaction_uid=transaction.transaction_uid,
                        sop_instances=transaction.sop_instances
                    )
                    return

                elif self._simulated_failure == SimulatedFailure.CHANGE_TXUID:
                    self.send_event_report(
                        host=Helpers.get_orthanc_ip(),
                        port=Helpers.get_orthanc_dicom_port(),
                        calling_ae=FAKE_SERVER_AET,
                        called_ae='ORTHANC',
                        transaction_uid="1.2.3.4",
                        sop_instances=transaction.sop_instances
                    )
                    return

                elif self._simulated_failure == SimulatedFailure.CHANGE_ONE_SOP_INSTANCE_UID:
                    modified_sop_instances = transaction.sop_instances.copy()
                    modified_sop_instances[0] = (modified_sop_instances[0][0], "3.3.3")
                    self.send_event_report(
                        host=Helpers.get_orthanc_ip(),
                        port=Helpers.get_orthanc_dicom_port(),
                        calling_ae=FAKE_SERVER_AET,
                        called_ae='ORTHANC',
                        transaction_uid=transaction.transaction_uid,
                        sop_instances=modified_sop_instances
                    )
                    return

                elif self._simulated_failure == SimulatedFailure.CHANGE_ONE_SOP_CLASS_UID:
                    modified_sop_instances = transaction.sop_instances.copy()
                    modified_sop_instances[0] = ("3.3.3", modified_sop_instances[0][1])
                    self.send_event_report(
                        host=Helpers.get_orthanc_ip(),
                        port=Helpers.get_orthanc_dicom_port(),
                        calling_ae=FAKE_SERVER_AET,
                        called_ae='ORTHANC',
                        transaction_uid=transaction.transaction_uid,
                        sop_instances=modified_sop_instances
                    )
                    return

                elif self._simulated_failure == SimulatedFailure.ADD_ONE_SOP_INSTANCE:
                    modified_sop_instances = transaction.sop_instances.copy()
                    modified_sop_instances.append(("4.4.0", "4.4.1"))
                    self.send_event_report(
                        host=Helpers.get_orthanc_ip(),
                        port=Helpers.get_orthanc_dicom_port(),
                        calling_ae=FAKE_SERVER_AET,
                        called_ae='ORTHANC',
                        transaction_uid=transaction.transaction_uid,
                        sop_instances=modified_sop_instances
                    )
                    return

                elif self._simulated_failure == SimulatedFailure.REMOVE_ONE_SOP_INSTANCE:
                    modified_sop_instances = transaction.sop_instances.copy()[1:]
                    self.send_event_report(
                        host=Helpers.get_orthanc_ip(),
                        port=Helpers.get_orthanc_dicom_port(),
                        calling_ae=FAKE_SERVER_AET,
                        called_ae='ORTHANC',
                        transaction_uid=transaction.transaction_uid,
                        sop_instances=modified_sop_instances
                    )
                    return

                elif self._simulated_failure == SimulatedFailure.CHANGE_CALLED_AET:
                    modified_sop_instances = transaction.sop_instances.copy()[1:]
                    self.send_event_report(
                        host=Helpers.get_orthanc_ip(),
                        port=Helpers.get_orthanc_dicom_port(),
                        calling_ae=FAKE_ALTERNATE_SERVER_AET,  # the AET must be known from Orthanc in order to accept the incoming connection
                        called_ae='ORTHANC',
                        transaction_uid=transaction.transaction_uid,
                        sop_instances=modified_sop_instances
                    )
                    return
        finally:
            server.shutdown()

    def stop(self):
        self._should_stop = True
        self._thread.join()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()


class TestStorageCommitment(OrthancTestCase):

    @classmethod
    def prepare(cls):
        print('-------------- preparing TestStorageCommitment tests')

        if not Helpers.tests_run_in_docker:

            cls.clear_storage(storage_name="TestStorageCommitment")

            config = {  # this config is used only on desktop -> check the docker-compose-storage-commitment.yml for docker config
                    "DicomModalities": {
                        "fake-mod": {
                            "AET": FAKE_SERVER_AET,
                            "Port": FAKE_SERVER_PORT,
                            "Host": "localhost"
                        },
                        "alternate-mod": {
                            "AET": FAKE_ALTERNATE_SERVER_AET,
                            "Port": FAKE_SERVER_PORT,
                            "Host": "localhost"
                        }
                    },
                }

            config_path = cls.generate_configuration(
                config_name="storage_commitment",
                storage_name="StorageCommitment",
                config=config,
                plugins=Helpers.plugins
            )

            if Helpers.break_after_preparation:
                print(f"++++ It is now time to start your Orthanc under tests with configuration file '{config_path}' +++++")
                input("Press Enter to continue")
            else:
                print('-------------- launching StorageCommitment tests')
                cls.launch_orthanc_under_tests(
                    config_path=config_path,
                    config_name="storage_commitment",
                    storage_name="StorageCommitment",
                    plugins=Helpers.plugins
                )

            print('-------------- waiting for orthanc-under-tests to be available')

        # else:
        #     cls.o = OrthancApiClient(f"{Helpers.orthanc_under_tests_hostname}:{Helpers.orthanc_under_tests_http_port}")

        cls.o.wait_started()
        

    def wait_transaction_complete(self, transaction_uid, timeout=10):
        retry = 0
        while retry < timeout:
            r = self.o.get_json(f"/storage-commitment/{transaction_uid}")
            if r['Status'] != "Pending":
                return r['Status']
            retry += 1
            time.sleep(1)

        return r['Status']

    def test_valid_transaction(self):

        with FakeStorageCommitmentServer(SimulatedFailure.NONE) as server:

            r = self.o.post("/modalities/fake-mod/storage-commitment", json={
                "DicomInstances": [{
                    "SOPClassUID": "1.1.0",
                    "SOPInstanceUID": "1.1.1"
                }]}).json()

            self.assertEqual('Success', self.wait_transaction_complete(r['ID']))
            self.assertEqual(0x0000, server.event_report_response_status)


    def test_transaction_uuid_validation(self):
        if self.o.is_orthanc_version_at_least(1, 13, 1):
            with FakeStorageCommitmentServer(SimulatedFailure.CHANGE_TXUID) as server:

                r = self.o.post("/modalities/fake-mod/storage-commitment", json={
                    "DicomInstances": [{
                        "SOPClassUID": "1.1.0",
                        "SOPInstanceUID": "1.1.1"
                    }]}).json()

                self.assertEqual('Pending', self.wait_transaction_complete(r['ID'], timeout=2))
                self.assertEqual(0x0211, server.event_report_response_status)


    def test_changed_sop_instance(self):
        if self.o.is_orthanc_version_at_least(1, 13, 1):
            with FakeStorageCommitmentServer(SimulatedFailure.CHANGE_ONE_SOP_INSTANCE_UID) as server:

                r = self.o.post("/modalities/fake-mod/storage-commitment", json={
                    "DicomInstances": [{
                        "SOPClassUID": "1.1.0",
                        "SOPInstanceUID": "1.1.1"
                    }, {
                        "SOPClassUID": "1.2.0",
                        "SOPInstanceUID": "1.2.1"
                    }]}).json()

                self.assertEqual('Pending', self.wait_transaction_complete(r['ID'], timeout=2))
                self.assertEqual(0x0117, server.event_report_response_status)

    def test_add_sop_instance(self):
        if self.o.is_orthanc_version_at_least(1, 13, 1):
            with FakeStorageCommitmentServer(SimulatedFailure.ADD_ONE_SOP_INSTANCE) as server:

                r = self.o.post("/modalities/fake-mod/storage-commitment", json={
                    "DicomInstances": [{
                        "SOPClassUID": "1.1.0",
                        "SOPInstanceUID": "1.1.1"
                    }]}).json()

                self.assertEqual('Pending', self.wait_transaction_complete(r['ID'], timeout=2))
                self.assertEqual(0x0117, server.event_report_response_status)

    def test_remove_sop_instance(self):
        if self.o.is_orthanc_version_at_least(1, 13, 1):
            with FakeStorageCommitmentServer(SimulatedFailure.REMOVE_ONE_SOP_INSTANCE) as server:

                r = self.o.post("/modalities/fake-mod/storage-commitment", json={
                    "DicomInstances": [{
                        "SOPClassUID": "1.1.0",
                        "SOPInstanceUID": "1.1.1"
                    }, {
                        "SOPClassUID": "1.2.0",
                        "SOPInstanceUID": "1.2.1"
                    }]}).json()

                self.assertEqual('Pending', self.wait_transaction_complete(r['ID'], timeout=2))
                self.assertEqual(0x0110, server.event_report_response_status)

    def test_change_sop_class(self):
        if self.o.is_orthanc_version_at_least(1, 13, 1):
            with FakeStorageCommitmentServer(SimulatedFailure.CHANGE_ONE_SOP_CLASS_UID) as server:

                r = self.o.post("/modalities/fake-mod/storage-commitment", json={
                    "DicomInstances": [{
                        "SOPClassUID": "1.1.0",
                        "SOPInstanceUID": "1.1.1"
                    }, {
                        "SOPClassUID": "1.2.0",
                        "SOPInstanceUID": "1.2.1"
                    }]}).json()

                self.assertEqual('Pending', self.wait_transaction_complete(r['ID'], timeout=2))
                self.assertEqual(0x0119, server.event_report_response_status)

    def test_change_call_aet(self):
        if self.o.is_orthanc_version_at_least(1, 13, 1):
            with FakeStorageCommitmentServer(SimulatedFailure.CHANGE_CALLED_AET) as server:

                r = self.o.post("/modalities/fake-mod/storage-commitment", json={
                    "DicomInstances": [{
                        "SOPClassUID": "1.1.0",
                        "SOPInstanceUID": "1.1.1"
                    }, {
                        "SOPClassUID": "1.2.0",
                        "SOPInstanceUID": "1.2.1"
                    }]}).json()

                self.assertEqual('Pending', self.wait_transaction_complete(r['ID'], timeout=2))
                self.assertEqual(0x0110, server.event_report_response_status)
