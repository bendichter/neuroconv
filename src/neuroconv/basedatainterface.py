"""Authors: Cody Baker and Ben Dichter."""
from abc import abstractmethod, ABC
import uuid
from pathlib import Path
from typing import Optional, Literal

from pynwb import NWBFile

from .backends import backends
from .tools.nwb_helpers import make_nwbfile_from_metadata
from .utils import get_base_schema, get_schema_from_method_signature


class BaseDataInterface(ABC):
    """Abstract class defining the structure of all DataInterfaces."""

    @classmethod
    def get_source_schema(cls):
        """Infer the JSON schema for the source_data from the method signature (annotation typing)."""
        return get_schema_from_method_signature(cls.__init__, exclude=["source_data"])

    @classmethod
    def get_conversion_options_schema(cls):
        """Infer the JSON schema for the conversion options from the method signature (annotation typing)."""
        return get_schema_from_method_signature(cls.run_conversion, exclude=["nwbfile", "metadata"])

    def __init__(self, **source_data):
        self.source_data = source_data

    def get_metadata_schema(self):
        """Retrieve JSON schema for metadata."""
        metadata_schema = get_base_schema(
            id_="metadata.schema.json",
            root=True,
            title="Metadata",
            description="Schema for the metadata",
            version="0.1.0",
        )
        return metadata_schema

    def get_metadata(self):
        """Child DataInterface classes should override this to match their metadata."""

        metadata = dict(
            NWBFile=dict(
                session_description="Auto-generated by neuroconv",
                identifier=str(uuid.uuid4()),
            ),
        )

        return metadata

    def get_conversion_options(self):
        """Child DataInterface classes should override this to match their conversion options."""
        return dict()

    def configure_datasets(self, nwbfile: NWBFile, backend: str, dataset_configs: dict = None):
        dataset_configs = dataset_configs or dict()
        for container_id, field in self.datasets:
            dset_config = dataset_configs.get((container_id, field), backends[backend].data_io_defaults)
            data = nwbfile.get_object(container_id).getattr(field)
            nwbfile.get_object(container_id).setattr(field, backends[backend].data_io(data=data, **dset_config))

    @abstractmethod
    def run_conversion(
        self,
        nwbfile_path: Optional[str] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        backend: Literal["hdf5", "zarr"] = "hdf5",
        dataset_configs: Optional[dict] = None,
        **conversion_options,
    ):
        """
        Run the NWB conversion for the instantiated data interface.

        Parameters
        ----------
        nwbfile_path: FilePathType
            Path for where to write or load (if overwrite=False) the NWBFile.
            If specified, the context will always write to this location.
        nwbfile: NWBFile, optional
            An in-memory NWBFile object to write to the location.
        metadata: dict, optional
            Metadata dictionary with information used to create the NWBFile when one does not exist or overwrite=True.
        overwrite: bool, optional
            Whether to overwrite the NWBFile if one exists at the nwbfile_path.
            The default is False (append mode).
        backend: {"hdf5", "zarr"}
        dataset_configs: dict, optional
        verbose: bool, optional
            If 'nwbfile_path' is specified, informs user after a successful write operation.
            The default is True.
        """
        if nwbfile_path and nwbfile:
            raise ValueError("Provide either nwbfile or nwbfile_path to `run_conversion`, not both.")

        if not (nwbfile or nwbfile_path):
            raise ValueError("Provide either nwbfile or nwbfile_path to `run_conversion`.")

        if Path(nwbfile_path).exists():
            with backends[backend].nwb_io(nwbfile_path, mode="w" if overwrite else "r+", load_namespaces=True) as io:
                nwbfile = io.read()
                self.add_to_nwb(nwbfile)
                self.configure_datasets(nwbfile, backend, dataset_configs)
                io.write(nwbfile, nwbfile_path, backend=backend, dataset_configs=dataset_configs)
        else:
            if not nwbfile:
                nwbfile = make_nwbfile_from_metadata(metadata)
            self.add_to_nwb(nwbfile)
            self.configure_datasets(nwbfile, backend, dataset_configs)
            with backends[backend].nwb_io(nwbfile, mode="w" if overwrite else "r+", load_namespaces=True) as io:
                io.write(nwbfile, nwbfile_path)

    def add_to_nwb(self, nwbfile: NWBFile):
        raise NotImplementedError()
