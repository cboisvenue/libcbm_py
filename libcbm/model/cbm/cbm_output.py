from libcbm.model.cbm.cbm_variables import CBMVariables
from libcbm.storage import dataframe_functions
from libcbm.storage.dataframe import DataFrame
from libcbm.storage.dataframe import Series
import numpy as np


def _get_disturbance_type_map_func(disturbance_type_map):
    def disturbance_type_map_func(dist_id):
        if dist_id <= 0:
            return dist_id
        else:
            return disturbance_type_map[dist_id]

    return disturbance_type_map_func


def _add_timestep_series(timestep: int, dataframe: DataFrame) -> DataFrame:
    dataframe.add_column(
        Series("identifier", np.arange(0, dataframe.n_rows), "int"), 0
    )
    dataframe.add_column(Series("timestep", timestep, "int"), 1)
    return dataframe


def _concat_timestep_results(
    timestep: int, running_result: DataFrame, timestep_result: DataFrame
) -> DataFrame:

    _add_timestep_series(timestep, timestep_result)

    return dataframe_functions.concat_data_frame(
        [running_result, timestep_result]
    )


class InMemoryCBMOutput:
    def __init__(
        self,
        density: bool = False,
        classifier_map: dict[int, str] = None,
        disturbance_type_map: dict[int, str] = None,
    ):
        """Create storage and a function for complete simulation results.  The
        function return value can be passed to :py:func:`simulate` to track
        simulation results.

        Args:
            density (bool, optional): if set to true pool and flux indicators
                will be computed as area densities (tonnes C/ha). By default,
                pool and flux outputs are computed as mass (tonnes C) based on
                the area of each stand. Defaults to False.
            classifier_map (dict, optional): a classifier map for subsituting
                the internal classifier id values with classifier value names.
                If specified, the names associated with each id in the map are
                the values in the  the classifiers result DataFrame  If set to
                None the id values will be returned.
            disturbance_type_map (dict, optional): a disturbance type map for
                subsituting the internally defined disturbance type id with
                names or other ids in the parameters and state tables.  If set
                to none no substitution will occur.
        """
        self._density = density
        self._disturbance_type_map = disturbance_type_map
        self._classifier_map = classifier_map
        self.pools: DataFrame = None
        self.flux: DataFrame = None
        self.state: DataFrame = None
        self.classifiers: DataFrame = None
        self.parameters: DataFrame = None
        self.area: DataFrame = None

    def append_simulation_result(self, timestep: int, cbm_vars: CBMVariables):
        timestep_pools = (
            cbm_vars.pools.copy()
            if self._density
            else cbm_vars.pools.multiply(cbm_vars.inventory["area"])
        )
        self.pool = _concat_timestep_results(
            timestep, self.pools, timestep_pools
        )

        if cbm_vars.flux is not None and len(cbm_vars.flux.index) > 0:
            timestep_flux = (
                cbm_vars.flux.copy()
                if self._density
                else cbm_vars.flux.multiply(cbm_vars.inventory["area"], axis=0)
            )
            self.flux = _concat_timestep_results(
                timestep, self.flux, timestep_flux
            )

        if self._disturbance_type_map:
            timestep_state = cbm_vars.state.copy()
            timestep_params = cbm_vars.parameters.copy()
            dist_map_func = _get_disturbance_type_map_func(
                self._disturbance_type_map
            )
            timestep_state["last_disturbance_type"] = timestep_state[
                "last_disturbance_type"
            ].map(dist_map_func)

            timestep_params["disturbance_type"] = timestep_params[
                "disturbance_type"
            ].map(dist_map_func)
        else:
            timestep_state = cbm_vars.state
            timestep_params = cbm_vars.parameters

        self.state = _concat_timestep_results(
            timestep, self.state, timestep_state
        )

        self.state = _concat_timestep_results(
            timestep, self.parameters, timestep_params
        )

        if self._classifier_map is None:
            self.classifiers = _concat_timestep_results(
                timestep, self.classifiers, cbm_vars.classifiers
            )
        else:
            timestep_classifiers = cbm_vars.classifiers.copy()
            timestep_classifiers.map(self._classifier_map)
            self.classifiers = _concat_timestep_results(
                timestep, self.classifiers, timestep_classifiers
            )
        self.area = _concat_timestep_results(
            timestep,
            self.area,
            DataFrame(
                [cbm_vars.inventory["area"]],
                cbm_vars.inventory.n_rows,
                cbm_vars.inventory.backend_type,
            ),
        )

        self.parameters = _concat_timestep_results(
            timestep, self.parameters, cbm_vars.parameters
        )
