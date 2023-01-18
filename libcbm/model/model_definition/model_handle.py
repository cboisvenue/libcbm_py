from __future__ import annotations
import json
import numpy as np
from typing import Iterator
from contextlib import contextmanager
from libcbm.wrapper import libcbm_operation
from libcbm.wrapper.libcbm_wrapper import LibCBMWrapper
from libcbm.wrapper.libcbm_handle import LibCBMHandle
from libcbm import resources
from libcbm.storage.dataframe import DataFrame
from libcbm.storage.series import Series


class ModelHandle:
    """
    Class to facilitate optimizied pool flux operations.

    This is essentially a layer for simplifying the python
    interface to libcbm matrix processing
    """

    def __init__(
        self,
        wrapper: LibCBMWrapper,
        pools: dict[str, int],
        flux_indicators: list[dict],
    ):
        """_summary_

        Args:
            wrapper (LibCBMWrapper): low level function wrapper
            pools (dict[str, int]): the collection of named pools
            flux_indicators (list[dict]): flux indicator configuration
        """
        self.wrapper = wrapper
        self.pools = pools
        self.flux_indicators = flux_indicators

    def _matrix_rc(
        self,
        value: list,
        process_id: int,
        matrix_index: np.ndarray,
        init_value: int,
    ) -> libcbm_operation.Operation:
        return libcbm_operation.Operation(
            self.wrapper,
            libcbm_operation.OperationFormat.RepeatingCoordinates,
            value,
            process_id,
            matrix_index,
            init_value,
        )

    def _matrix_list(
        self,
        value: list,
        process_id: int,
        matrix_index: np.ndarray,
        init_value: int,
    ) -> libcbm_operation.Operation:
        return libcbm_operation.Operation(
            self.wrapper,
            libcbm_operation.OperationFormat.MatrixList,
            value,
            process_id,
            matrix_index,
            init_value,
        )

    def create_operation(
        self,
        matrices: list,
        fmt: str,
        process_id: int,
        matrix_index: np.ndarray,
        init_value: int = 1,
    ) -> libcbm_operation.Operation:
        """Create a libcbm Operation

        Args:
            matrices (list): _description_
            fmt (str): _description_
            process_id (int): _description_
            matrix_index (np.ndarray): _description_
            init_value (int, optional): _description_. Defaults to 1.

        Raises:
            ValueError: _description_

        Returns:
            libcbm_operation.Operation: initialized Operation object
        """
        if fmt == "repeating_coordinates":
            pool_id_mat = [
                [self.pools[row[0]], self.pools[row[1]], row[2]]
                for row in matrices
            ]
            return self._matrix_rc(
                pool_id_mat, process_id, matrix_index, init_value
            )
        elif fmt == "matrix_list":
            mat_list = []
            for mat in matrices:
                mat_len = len(mat)
                np_mat = np.zeros(shape=(mat_len, 3))
                for i_entry, entry in enumerate(mat):
                    np_mat[i_entry, 0] = self.pools[entry[0]]
                    np_mat[i_entry, 1] = self.pools[entry[1]]
                    np_mat[i_entry, 2] = entry[2]
                mat_list.append(np_mat)
            return self._matrix_list(
                mat_list, process_id, matrix_index, init_value
            )
        else:
            raise ValueError("unknown format")

    def compute(
        self,
        pools: DataFrame,
        flux: DataFrame,
        enabled: Series,
        operations: list[libcbm_operation.Operation],
    ) -> None:

        libcbm_operation.compute(
            dll=self.wrapper,
            pools=pools,
            operations=operations,
            op_processes=[o.op_process_id for o in operations],
            flux=flux,
            enabled=enabled,
        )


@contextmanager
def create_model_handle(
    pools: dict[str, int], flux_indicators: list[dict]
) -> Iterator[ModelHandle]:

    libcbm_config = {
        "pools": [
            {"name": p, "id": p_idx, "index": p_idx}
            for p, p_idx in pools.items()
        ],
        "flux_indicators": [
            {
                "id": f_idx + 1,
                "index": f_idx,
                "process_id": f["process_id"],
                "source_pools": [int(x) for x in f["source_pools"]],
                "sink_pools": [int(x) for x in f["sink_pools"]],
            }
            for f_idx, f in enumerate(flux_indicators)
        ],
    }

    with LibCBMHandle(
        resources.get_libcbm_bin_path(), json.dumps(libcbm_config)
    ) as handle:
        yield ModelHandle(LibCBMWrapper(handle), pools, flux_indicators)
