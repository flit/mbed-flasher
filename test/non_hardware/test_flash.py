#!/usr/bin/env python
"""
Copyright 2016 ARM Limited

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
# pylint:disable=missing-docstring
# pylint:disable=too-few-public-methods
# pylint:disable=invalid-name
# pylint:disable=unused-argument

import logging
import unittest
import os
import sys
import mock

from mbed_flasher.common import FlashError
from mbed_flasher.flash import Flash
from mbed_flasher.flashers.FlasherMbed import FlasherMbed
from mbed_flasher.return_codes import EXIT_CODE_SUCCESS
from mbed_flasher.return_codes import EXIT_CODE_OS_ERROR
from mbed_flasher.return_codes import EXIT_CODE_FILE_MISSING
from mbed_flasher.return_codes import EXIT_CODE_COULD_NOT_MAP_DEVICE
from mbed_flasher.return_codes import EXIT_CODE_COULD_NOT_MAP_TARGET_ID_TO_DEVICE
from mbed_flasher.return_codes import EXIT_CODE_FLASH_FAILED
from mbed_flasher.return_codes import EXIT_CODE_DAPLINK_SOFTWARE_ERROR
from mbed_flasher.return_codes import EXIT_CODE_DAPLINK_TRANSIENT_ERROR
from mbed_flasher.return_codes import EXIT_CODE_DAPLINK_TARGET_ERROR
from mbed_flasher.return_codes import EXIT_CODE_DAPLINK_INTERFACE_ERROR
from mbed_flasher.return_codes import EXIT_CODE_DAPLINK_USER_ERROR


class FlashTestCase(unittest.TestCase):
    """ Basic true asserts to see that testing is executed
    """
    bin_path = os.path.join('test', 'helloworld.bin')

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def test_run_file_does_not_exist(self):
        flasher = Flash()
        with self.assertRaises(SyntaxError) as context:
            flasher.flash(build='file.bin', target_id=None,
                          platform_name=None, device_mapping_table=None, method='simple')
        self.assertIn("target_id or target_name is required", context.exception.msg)

    # test with name longer than 30, disable the warning here
    # pylint: disable=invalid-name
    def test_run_target_id_and_platform_missing(self):
        flasher = Flash()
        with self.assertRaises(FlashError) as cm:
            flasher.flash(build='file.bin', target_id=True,
                          platform_name=False, device_mapping_table=None,
                          method='simple')

        self.assertEqual(cm.exception.return_code, EXIT_CODE_FILE_MISSING)

    @mock.patch("mbed_flasher.flash.Logger")
    def test_flash_logger_created(self, mock_logger):  # pylint: disable=no-self-use
        mock_logger.return_value = mock.MagicMock()
        flash = Flash()  # pylint: disable=unused-variable
        mock_logger.assert_called_once_with("mbed-flasher")

    @mock.patch("mbed_flasher.flash.Logger")
    def test_flash_logger_not_created(self, mock_logger):
        mock_logger.return_value = mock.MagicMock()
        very_real_logger = mock.MagicMock()
        flash = Flash(logger=very_real_logger)
        mock_logger.assert_not_called()
        self.assertEqual(very_real_logger, flash.logger)

    @mock.patch('mbed_flasher.common.Common.get_available_device_mapping')
    def test_run_with_file_with_target_id_all(self, mock_device_mapping):
        flasher = Flash()
        mock_device_mapping.return_value = []
        with self.assertRaises(FlashError) as cm:
            flasher.flash(build=self.bin_path, target_id='all',
                          platform_name=False, device_mapping_table=None,
                          method='simple')

        self.assertEqual(cm.exception.return_code, EXIT_CODE_COULD_NOT_MAP_TARGET_ID_TO_DEVICE)

    @mock.patch("time.sleep", return_value=None)
    def test_run_with_file_with_one_target_id(self, mock_sleep):
        flasher = Flash()
        with self.assertRaises(FlashError) as cm:
            flasher.flash(build=self.bin_path,
                          target_id='0240000029164e45002f0012706e0006f301000097969900',
                          platform_name=False,
                          device_mapping_table=None,
                          method='simple')

        self.assertEqual(cm.exception.return_code, EXIT_CODE_COULD_NOT_MAP_DEVICE)

    def test_raises_with_bad_file_extension(self):
        flasher = Flash()
        with self.assertRaises(FlashError) as cm:
            flasher.flash(build=__file__,
                          target_id='0240000029164e45002f0012706e0006f301000097969900',
                          platform_name=False,
                          device_mapping_table=None,
                          method='simple')

        self.assertEqual(cm.exception.return_code, EXIT_CODE_DAPLINK_USER_ERROR)

    # pylint: disable=no-self-use
    @mock.patch('os.fsync')
    def test_copy_file_with_spaces(self, mock_os_fsync):
        flasher = FlasherMbed()
        flasher.copy_file(__file__, "tar get")
        os.remove("tar get")
        mock_os_fsync.assert_called_once()

    def test_copy_file_unable_to_read(self):
        flasher = FlasherMbed()
        with self.assertRaises(FlashError):
            flasher.copy_file("not-existing-file", "target")

    # pylint: disable=no-self-use
    @mock.patch('os.fsync')
    def test_copy_empty_file(self, mock_os_fsync):
        flasher = FlasherMbed()
        with open("empty_file", 'a'):
            os.utime("empty_file", None)
        flasher.copy_file("empty_file", "target")
        os.remove("empty_file")
        os.remove("target")
        mock_os_fsync.assert_called_once()

    # pylint: disable=no-self-use
    @mock.patch('os.fsync')
    def test_copy_file_write_success(self, mock_os_fsync):
        flasher = FlasherMbed()
        with open("source_file", 'wb') as source_file:
            source_file.write(b"test data")

        flasher.copy_file("source_file", "destination")

        with open("destination", "rb") as destination:
            result = destination.read()

        # remove file before assert to clean environment
        os.remove("source_file")
        os.remove("destination")

        # make sure file.write() really worked
        self.assertEqual(result, b"test data", "copy file failed")
        mock_os_fsync.assert_called_once()

    @mock.patch('builtins.open' if sys.version_info.major > 2 else '__builtin__.open', create=True)
    @mock.patch('hashlib.sha1')
    @mock.patch('os.fsync')
    def test_copy_file_flush_is_called(self, mock_os_fsync, mock_sha1, mock_open):
        flasher = FlasherMbed()
        flasher.copy_file("source_file", "destination")

        file_handle = mock_open.return_value.__enter__.return_value

        self.assertEqual(1, file_handle.flush.call_count)
        file_handle.flush.assert_called_once()


class FlasherMbedRetry(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)

    @mock.patch("time.sleep", return_value=None)
    @mock.patch('mbed_flasher.mbed_common.MbedCommon.refresh_target')
    @mock.patch('mbed_flasher.reset.Reset.reset_board')
    @mock.patch('mbed_flasher.flashers.FlasherMbed.FlasherMbed.copy_file')
    def test_retries_on_io_error(
            self, mock_copy_file, mock_reset_board, mock_refresh_target, mock_sleep):
        target = {"target_id": "a", "mount_point": ""}
        mock_copy_file.side_effect = IOError("")
        mock_reset_board.return_value = True
        mock_refresh_target.return_value = target
        flasher = FlasherMbed()

        with self.assertRaises(FlashError) as cm:
            flasher.flash(source="", target=target, method="simple", no_reset=False)

        self.assertEqual(cm.exception.return_code, EXIT_CODE_OS_ERROR)
        self.assertEqual(mock_copy_file.call_count, 5)

    @mock.patch("time.sleep", return_value=None)
    @mock.patch('mbed_flasher.mbed_common.MbedCommon.refresh_target')
    @mock.patch('mbed_flasher.reset.Reset.reset_board')
    @mock.patch('mbed_flasher.flashers.FlasherMbed.FlasherMbed.copy_file')
    def test_retries_on_os_error(
            self, mock_copy_file, mock_reset_board, mock_refresh_target, mock_sleep):
        target = {"target_id": "a", "mount_point": ""}
        mock_copy_file.side_effect = OSError("")
        mock_reset_board.return_value = True
        mock_refresh_target.return_value = target
        flasher = FlasherMbed()

        with self.assertRaises(FlashError) as cm:
            flasher.flash(source="", target=target, method="simple", no_reset=False)

        self.assertEqual(cm.exception.return_code, EXIT_CODE_OS_ERROR)
        self.assertEqual(mock_copy_file.call_count, 5)

    @mock.patch("time.sleep", return_value=None)
    @mock.patch('mbed_flasher.mbed_common.MbedCommon.refresh_target')
    @mock.patch('mbed_flasher.reset.Reset.reset_board')
    @mock.patch('mbed_flasher.flashers.FlasherMbed.FlasherMbed.copy_file')
    def test_retries_on_daplink_sw_error(
            self, mock_copy_file, mock_reset_board, mock_refresh_target, mock_sleep):
        target = {"target_id": "a", "mount_point": ""}
        mock_copy_file.side_effect = FlashError(message="",
                                                return_code=EXIT_CODE_DAPLINK_SOFTWARE_ERROR)
        mock_reset_board.return_value = True
        mock_refresh_target.return_value = target
        flasher = FlasherMbed()

        with self.assertRaises(FlashError) as cm:
            flasher.flash(source="", target=target, method="simple", no_reset=False)

        self.assertEqual(cm.exception.return_code, EXIT_CODE_DAPLINK_SOFTWARE_ERROR)
        self.assertEqual(mock_copy_file.call_count, 5)

    @mock.patch("time.sleep", return_value=None)
    @mock.patch('mbed_flasher.mbed_common.MbedCommon.refresh_target')
    @mock.patch('mbed_flasher.reset.Reset.reset_board')
    @mock.patch('mbed_flasher.flashers.FlasherMbed.FlasherMbed.copy_file')
    def test_retries_on_daplink_transient_error(
            self, mock_copy_file, mock_reset_board, mock_refresh_target, mock_sleep):
        target = {"target_id": "a", "mount_point": ""}
        mock_copy_file.side_effect = FlashError(message="",
                                                return_code=EXIT_CODE_DAPLINK_TRANSIENT_ERROR)
        mock_reset_board.return_value = True
        mock_refresh_target.return_value = target
        flasher = FlasherMbed()

        with self.assertRaises(FlashError) as cm:
            flasher.flash(source="", target=target, method="simple", no_reset=False)

        self.assertEqual(cm.exception.return_code, EXIT_CODE_DAPLINK_TRANSIENT_ERROR)
        self.assertEqual(mock_copy_file.call_count, 5)

    @mock.patch('mbed_flasher.mbed_common.MbedCommon.refresh_target')
    @mock.patch('mbed_flasher.reset.Reset.reset_board')
    @mock.patch('mbed_flasher.flashers.FlasherMbed.FlasherMbed.copy_file')
    def test_does_not_retry_on_daplink_user_error(
            self, mock_copy_file, mock_reset_board, mock_refresh_target):
        target = {"target_id": "a", "mount_point": ""}
        mock_copy_file.side_effect = FlashError(message="",
                                                return_code=EXIT_CODE_DAPLINK_USER_ERROR)
        mock_reset_board.return_value = True
        mock_refresh_target.return_value = target
        flasher = FlasherMbed()

        with self.assertRaises(FlashError) as cm:
            flasher.flash(source="", target=target, method="simple", no_reset=False)

        self.assertEqual(cm.exception.return_code, EXIT_CODE_DAPLINK_USER_ERROR)
        self.assertEqual(mock_copy_file.call_count, 1)


class FlashVerify(unittest.TestCase):
    @mock.patch('mbed_flasher.flashers.FlasherMbed.isfile')
    def test_verify_flash_success_ok(self, mock_isfile):
        mock_isfile.return_value = False

        return_value = FlasherMbed().verify_flash_success(target={"mount_point": ""}, file_path="")
        self.assertEqual(return_value, EXIT_CODE_SUCCESS)

    # test with name longer than 30, disable the warning here
    # pylint: disable=invalid-name
    @mock.patch('mbed_flasher.flashers.FlasherMbed.FlasherMbed._read_file')
    @mock.patch('mbed_flasher.flashers.FlasherMbed.isfile')
    def test_verify_flash_success_fail_no_reason(self, mock_isfile, mock_read_file):
        def isfile_function(path):
            if "FAIL" in path:
                return True
            return False

        mock_isfile.side_effect = isfile_function
        mock_read_file.return_value = ""

        target = {"target_id": "", "mount_point": ""}
        with self.assertRaises(FlashError) as cm:
            FlasherMbed().verify_flash_success(target=target, file_path="")

        exception = cm.exception
        self.assertEqual(exception.return_code, EXIT_CODE_FLASH_FAILED)
        self.assertEqual(exception.message, "Error in FAIL.TXT is unknown: ")

    # test with name longer than 30, disable the warning here
    # pylint: disable=invalid-name
    @mock.patch('mbed_flasher.flashers.FlasherMbed.FlasherMbed._read_file')
    @mock.patch('mbed_flasher.flashers.FlasherMbed.isfile')
    def test_verify_flash_success_fail_reasons(self, mock_isfile, mock_read_file):
        def isfile_function(path):
            if "FAIL" in path:
                return True
            return False

        mock_isfile.side_effect = isfile_function
        target = {"target_id": "", "mount_point": ""}

        def check(reason, code):
            mock_read_file.return_value = reason
            with self.assertRaises(FlashError) as cm:
                FlasherMbed().verify_flash_success(target=target, file_path="")

            exception = cm.exception
            self.assertEqual(exception.return_code, code)
            self.assertEqual(exception.message, reason)

        check("An internal error has occurred", EXIT_CODE_DAPLINK_SOFTWARE_ERROR)
        check("End of stream has been reached", EXIT_CODE_DAPLINK_SOFTWARE_ERROR)
        check("End of stream is unknown", EXIT_CODE_DAPLINK_SOFTWARE_ERROR)

        check("An error occurred during the transfer", EXIT_CODE_DAPLINK_TRANSIENT_ERROR)
        check("Possible mismatch between file size and size programmed",
              EXIT_CODE_DAPLINK_TRANSIENT_ERROR)
        check("File sent out of order by PC. Target might not be programmed correctly.",
              EXIT_CODE_DAPLINK_TRANSIENT_ERROR)
        check("An error has occurred", EXIT_CODE_DAPLINK_TRANSIENT_ERROR)

        check("The transfer timed out.", EXIT_CODE_DAPLINK_USER_ERROR)
        check("The interface firmware ABORTED programming. Image is trying to set security bits",
              EXIT_CODE_DAPLINK_USER_ERROR)
        check("The hex file cannot be decoded. Checksum calculation failure occurred.",
              EXIT_CODE_DAPLINK_USER_ERROR)
        check("The hex file cannot be decoded. Parser logic failure occurred.",
              EXIT_CODE_DAPLINK_USER_ERROR)
        check("The hex file cannot be programmed. Logic failure occurred.",
              EXIT_CODE_DAPLINK_USER_ERROR)
        check("The hex file you dropped isn't compatible with this mode or device."
              "Are you in MAINTENANCE mode? See HELP FAQ.HTM", EXIT_CODE_DAPLINK_USER_ERROR)
        check("The hex file offset load address is not correct.", EXIT_CODE_DAPLINK_USER_ERROR)
        check("The starting address for the bootloader update is wrong.",
              EXIT_CODE_DAPLINK_USER_ERROR)
        check("The starting address for the interface update is wrong.",
              EXIT_CODE_DAPLINK_USER_ERROR)
        check("The application file format is unknown and cannot be parsed and/or processed.",
              EXIT_CODE_DAPLINK_USER_ERROR)

        check("The interface firmware FAILED to reset/halt the target MCU",
              EXIT_CODE_DAPLINK_TARGET_ERROR)
        check("The interface firmware FAILED to download the flash programming"
              " algorithms to the target MCU", EXIT_CODE_DAPLINK_TARGET_ERROR)
        check("The interface firmware FAILED to download the flash"
              " data contents to be programmed", EXIT_CODE_DAPLINK_TARGET_ERROR)
        check("The interface firmware FAILED to initialize the target MCU",
              EXIT_CODE_DAPLINK_TARGET_ERROR)
        check("The interface firmware FAILED to unlock the target for programming",
              EXIT_CODE_DAPLINK_TARGET_ERROR)
        check("Flash algorithm erase sector command FAILURE", EXIT_CODE_DAPLINK_TARGET_ERROR)
        check("Flash algorithm erase all command FAILURE", EXIT_CODE_DAPLINK_TARGET_ERROR)
        check("Flash algorithm write command FAILURE", EXIT_CODE_DAPLINK_TARGET_ERROR)

        check("In application programming aborted due to an out of bounds address.",
              EXIT_CODE_DAPLINK_INTERFACE_ERROR)
        check("In application programming initialization failed.",
              EXIT_CODE_DAPLINK_INTERFACE_ERROR)
        check("In application programming uninit failed.", EXIT_CODE_DAPLINK_INTERFACE_ERROR)
        check("In application programming write failed.", EXIT_CODE_DAPLINK_INTERFACE_ERROR)
        check("In application programming sector erase failed.",
              EXIT_CODE_DAPLINK_INTERFACE_ERROR)
        check("In application programming mass erase failed.", EXIT_CODE_DAPLINK_INTERFACE_ERROR)
        check("In application programming not supported on this device.",
              EXIT_CODE_DAPLINK_INTERFACE_ERROR)
        check("In application programming failed because the update sent was incomplete.",
              EXIT_CODE_DAPLINK_INTERFACE_ERROR)
        check("The bootloader CRC did not pass.", EXIT_CODE_DAPLINK_INTERFACE_ERROR)

    @mock.patch('mbed_flasher.flashers.FlasherMbed.FlasherMbed._read_file')
    @mock.patch('mbed_flasher.flashers.FlasherMbed.isfile')
    def test_verify_flash_success_new_style(self, mock_isfile, mock_read_file):
        def isfile_function(path):
            if "FAIL" in path:
                return True
            return False

        return_value = """
error: File sent out of order by PC. Target might not be programmed correctly.
error type: transient, user
        """

        mock_isfile.side_effect = isfile_function
        mock_read_file.return_value = return_value

        target = {"target_id": "", "mount_point": ""}
        with self.assertRaises(FlashError) as cm:
            FlasherMbed().verify_flash_success(target=target, file_path="")

        self.assertEqual(cm.exception.return_code, EXIT_CODE_DAPLINK_TRANSIENT_ERROR)
        self.assertEqual(cm.exception.message, return_value)

    @mock.patch('mbed_flasher.flashers.FlasherMbed.FlasherMbed._read_file')
    @mock.patch('mbed_flasher.flashers.FlasherMbed.isfile')
    def test_verify_flash_success_multiple_hits(self, mock_isfile, mock_read_file):
        def isfile_function(path):
            if "FAIL" in path:
                return True
            return False

        return_value = """
error: File sent out of order by PC. Target might not be programmed correctly.
An error occurred during the transfer.
error type: transient, user
        """

        mock_isfile.side_effect = isfile_function
        mock_read_file.return_value = return_value

        target = {"target_id": "", "mount_point": ""}
        with self.assertRaises(FlashError) as cm:
            FlasherMbed().verify_flash_success(target=target, file_path="")

        self.assertEqual(cm.exception.return_code, EXIT_CODE_FLASH_FAILED)
        expected_message = "Found multiple errors from FAIL.TXT: {}".format(return_value)
        self.assertEqual(cm.exception.message, expected_message)


if __name__ == '__main__':
    unittest.main()
