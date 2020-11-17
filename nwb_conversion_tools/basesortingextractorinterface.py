"""Authors: Cody Baker and Ben Dichter."""
import spikeextractors as se
import numpy as np
from pynwb import NWBFile
from pynwb.ecephys import SpikeEventSeries

from .basedatainterface import BaseDataInterface
from .utils import get_base_schema, get_schema_from_method_signature, \
    get_schema_from_hdmf_class


class BaseSortingExtractorInterface(BaseDataInterface):
    SX = None

    @classmethod
    def get_input_schema(cls):
        return get_schema_from_method_signature(cls.SX.__init__)

    def __init__(self, **input_args):
        super().__init__(**input_args)
        self.sorting_extractor = self.SX(**input_args)

    def get_metadata_schema(self):
        metadata_schema = get_base_schema()

        # ideally most of this be automatically determined from pynwb docvals
        metadata_schema['properties']['SpikeEventSeries'] = get_schema_from_hdmf_class(SpikeEventSeries)
        required_fields = ['SpikeEventSeries']
        for field in required_fields:
            metadata_schema['required'].append(field)

        return metadata_schema

    def convert_data(self, nwbfile: NWBFile, metadata_dict: dict, stub_test: bool = False,
                     write_ecephys_metadata: bool = False):
        if 'UnitProperties' not in metadata_dict:
            metadata_dict['UnitProperties'] = []
        if write_ecephys_metadata and 'Ecephys' in metadata_dict:
            n_channels = max([len(x['data']) for x in metadata_dict['Ecephys']['Electrodes']])
            recording = se.NumpyRecordingExtractor(timeseries=np.array(range(n_channels)), sampling_frequency=1)
            se.NwbRecordingExtractor.add_devices(
                recording=recording,
                nwbfile=nwbfile,
                metadata=metadata_dict
            )
            se.NwbRecordingExtractor.add_electrode_groups(
                recording=recording,
                nwbfile=nwbfile,
                metadata=metadata_dict
            )
            se.NwbRecordingExtractor.add_electrodes(
                recording=recording,
                nwbfile=nwbfile,
                metadata=metadata_dict
            )

        property_descriptions = dict()
        if stub_test:
            max_min_spike_time = max([min(x) for y in self.sorting_extractor.get_unit_ids()
                                      for x in [self.sorting_extractor.get_unit_spike_train(y)] if any(x)])
            stub_sorting_extractor = se.SubSortingExtractor(
                self.sorting_extractor,
                unit_ids=self.sorting_extractor.get_unit_ids(),
                start_frame=0,
                end_frame=1.1 * max_min_spike_time
            )
            sorting_extractor = stub_sorting_extractor
        else:
            sorting_extractor = self.sorting_extractor

        for metadata_column in metadata_dict['UnitProperties']:
            property_descriptions.update({metadata_column['name']: metadata_column['description']})
            for unit_id in sorting_extractor.get_unit_ids():
                if metadata_column['name'] == 'electrode_group':
                    data = nwbfile.electrode_groups[metadata_column['data'][unit_id]]
                else:
                    data = metadata_column['data'][unit_id]
                sorting_extractor.set_unit_property(unit_id, metadata_column['name'], data)

        se.NwbSortingExtractor.write_sorting(
            sorting_extractor,
            property_descriptions=property_descriptions,
            nwbfile=nwbfile
        )