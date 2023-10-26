from abc import ABC
from typing import Optional, Tuple, List, Iterable

from MRdataset import logger
from MRdataset.base import BaseDataset
from MRdataset.dicom_utils import (is_valid_inclusion,
                                   is_dicom_file)
from MRdataset.utils import (folders_with_min_files, read_json, valid_dirs)
from protocol import ImagingSequence
from pydicom import dcmread
from pydicom.errors import InvalidDicomError


# A dataset is a collection of subjects
# A subject is a collection of sessions
# A session is a collection of runs
# A run is one instance of a sequence;
# A sequence can have multiple runs in a session
# A sequence is a collection of parameters
#
# related useful references
#   https://bids-specification.readthedocs.io/en/stable/appendices/entities.html
#
# dicom2nifti logic for naming files:
# https://github.com/icometrix/dicom2nifti/blob
# /ecbf43a66174375285fae485439ea8dd940005ba/dicom2nifti/convert_dir.py#L68
#


class DicomDataset(BaseDataset, ABC):
    """
    This class represents a dataset of dicom files. It is a subclass of BaseDataset.

    Parameters
    ----------
    data_source : str or List[str]
        The path or list of folders that contain the dicom files
    pattern : str
        The pattern to match the files extension. Default is '*'.
    name : str
        The name of the dataset. Default is 'DicomDataset'.
    config_path : str
        The path to the config file.
    verbose : bool
        Whether to print verbose output on console. Default is False.
    ds_format : str
        The format of the dataset. Default is 'dicom'. Choose one of ['dicom']
    """

    def __init__(self,
                 data_source,
                 pattern="*",
                 name='DicomDataset',
                 config_path=None,
                 verbose=False,
                 ds_format='dicom',
                 **kwargs):
        """constructor"""

        super().__init__(data_source=data_source, name=name, ds_format=ds_format)
        self.data_source = valid_dirs(data_source)
        self.pattern = pattern
        # TODO: Add option to change min_count passing it as an argument
        self.min_count = 1  # min slice count to be considered a volume
        self.verbose = verbose
        self.config_path = config_path
        self.config_dict = None

        # read the config file
        try:
            self.config_dict = read_json(self.config_path)
        except (FileNotFoundError or ValueError) as e:
            logger.error(f'Unable to read config file {self.config_path}')
            raise e

        # Whether to use echo numbers to identify multi-echo sequences
        self.use_echo_numbers = self.config_dict.get('use_echonumbers',
                                                     False)

        # These are used to skip certain sequences
        self.includes = self.config_dict.get('include_sequence', {})
        self.include_phantom = self.includes.get('phantom', None)
        self.include_moco = self.includes.get('moco', None)
        self.include_sbref = self.includes.get('sbref', None)
        self.include_derived = self.includes.get('derived', None)

        # variables specific to this class
        self._key_vars.update(['pattern', 'min_count', 'include_phantoms'])

        # if self._saved_path.exists():
        #     self._reload_saved()

        # print('')

    def load(self):
        """
        Default method to load the dataset. It iterates over all the folders
        in the data_source and finds the sub-folders with at least min_count
        files. Then it iterates over all the sub-folders and processes them
        to find the dicom slices. It then runs some basic validation on them
        and adds them to the dataset.
        """

        # if self._saved_path.exists() and not refresh:
        #     self._reload_saved()
        #     return

        for directory in self.data_source:
            # find all the sub-folders with at least min_count files
            sub_folders = folders_with_min_files(directory, self.pattern,
                                                 self.min_count)
            for folder in sub_folders:
                # process each folder
                seq = self._process_slice_collection(folder)
                if seq is None:
                    logger.info(f'Unable to process {folder}. Skipping it.')
                else:
                    self.add(subject_id=seq.subject_id, session_id=seq.session_id,
                             run_id=seq.run_id, seq_id=seq.name, seq=seq)

        # saving a copy for quicker reload
        # self.save()

    def _process_slice_collection(self, folder):
        """
        Processes a collection of dicom slices in a folder. It iterates over
        all the slices and collects the slices with divergent parameters, for
        example, EchoTime and Echonumber for multi-echo sequences.

        It then processes the divergent slices to find the varying parameters and
        updates the protocol.ImagingSequence object.

        Parameters
        ----------
        folder : Path
            The path to the folder containing the dicom slices
        """

        # within a folder, a volume can be multi-echo, so we must read them all
        #   and find a way to capture the echo time information
        dcm_files = sorted(folder.glob(self.pattern))

        # if no files found, return None
        # Not required as folders_with_min_files already checks for this
        # if len(dcm_files) < self.min_count:
        #     logger.warn(
        #         f'no files matching the pattern {self.pattern} found in {folder}',
        #         UserWarning)
        #     return None

        # run some basic validation of these dcm slice collection
        #   session_info must match
        #   parameter values must also match in general

        # However, for certain sequences, the parameter may vary
        #   (e.g. EchoTime for multi-echo). Therefore, we need to
        #   find a way to capture the varying parameters. We collect
        #   all the slices and then process them to find the varying
        #   parameters.

        # collect all the slices with diverging parameters
        divergent_slices = list()
        first_slice = None

        # iterate over all the slices
        for dcm_path in dcm_files:
            # check if it is a valid dicom file
            if not is_dicom_file(dcm_path):
                continue

            try:
                dicom = dcmread(dcm_path, stop_before_pixels=True)
            except InvalidDicomError:
                logger.info(f'Invalid DICOM file at {dcm_path}')
                continue

            # skip localizer, phantom, scouts, sbref, etc
            if not is_valid_inclusion(dicom, self.include_phantom, self.include_moco,
                                      self.include_sbref, self.include_derived):
                continue

            # until the first slice is found, we cannot compare
            #   other slices with it. So, we collect the first slice
            #   and then compare other slices with it.

            # Note that we cannot use enumerate and idx ==0 here, because we
            #   may have to skip some slices
            if len(divergent_slices) == 0:
                first_slice = ImagingSequence(
                    dicom=dicom,
                    path=folder
                )
                # We collect the first slice as a reference to compare
                #   other slices with, although it is not divergent in
                #   its true sense
                divergent_slices.append(first_slice)

            else:
                cur_slice = ImagingSequence(
                    dicom=dicom,
                    path=folder)

                # check if the session info is same
                # Session info includes subject_id, session_id, run_id
                if cur_slice.get_session_info() != first_slice.get_session_info():
                    logger.warn(f'Inconsistent session info for {dcm_path}')
                    continue

                # check if the parameters are same with the slices
                #   collected so far
                if len(divergent_slices) > 100:
                    logger.critical('Too many slices with divergent parameters. This should rarely happen.'
                                    'This would make data reading really slow. Please check the dataset.')
                flag = 0
                for slice in divergent_slices:
                    # we only compare the parameters that are subject to variation e.g. EchoTime
                    #   It is not recommended to compare all parameters as it would be
                    #   very slow. Also some parameters are e.g. SliceLocation would be
                    #   different for each slice. If SliceLocation is also compared,
                    #   we will end up having all slices in divergent_slices list.
                    if cur_slice.compare_subset_params(slice) == True:
                        flag = 1
                        break  # If number of divergent slices is large, this would make it faster

                if flag == 0:
                    divergent_slices.append(cur_slice)
        # as we also collect the first slice. We can process all slices
        #   to find the varying parameters. Atleast one slice would be
        #   present in divergent_slices.
        if len(divergent_slices) > 0:
            # if there are divergent slices, we need to process them
            #   to find the varying parameters. For now we just look for echo-time
            #   and echo-number, but we can extend this to other parameters such as
            #   flip-angle, etc.
            echo_times, echo_nums = self._process_echo_times(divergent_slices)
            first_slice.set_echo_times(echo_times, echo_nums)
            # TODO: Add support for other parameters
            # TODO: Calculate number of slices using SliceLocation
            #   See: https://stackoverflow.com/questions/59458801/how-to-sort-dicom-slices-in-correct-order # noqa
        return first_slice

    def _process_echo_times(self, divergent_slices: List) -> Tuple[Iterable, Optional[Iterable]]:
        """
        Finds the set of echo times and echo numbers from the list of
        slices. However, the echo number is not always available
        in the dicom header. In that case, we may have to look for a unique
        set of echo times. Although this is not preferred, but we can use this.

        Parameters
        ----------
        divergent_slices : list
            ImagingSequence objects with divergent parameters

        Returns
        -------
        echo_times : list
            collected list of echo times
        echo_nums : Optional[List]
            collected list of echo numbers

        """
        if self.use_echo_numbers:
            echo_dict = dict()
            for slice in divergent_slices:
                enum = slice['EchoNumber'].get_value()
                if enum not in echo_dict:
                    echo_dict[enum] = slice['EchoTime'].get_value()
            return echo_dict.values(), echo_dict.keys()
        else:
            echo_times = set()
            for slice in divergent_slices:
                echo_times.add(slice['EchoTime'].get_value())
            return echo_times, None
