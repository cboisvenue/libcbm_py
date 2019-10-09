import pandas as pd
import numpy as np
from libcbm.model.cbm import cbm_variables


def sorted_disturbance_target(target_var, sort_var, target, on_unrealized):
    """Given a target variable, a sort variable, and a cumulative
    target, produce a table of index, area proportions that will
    satisfy exactly a rule based disturbance target.

    Args:
        target_var (pd.Series): a series of values fed into an
            accumulator to satisfy the cumulative target.
        sort_var (pd.Series): a variable whose descending sort order
            defines the order in which target_var values are fed into
            the accumulator.
        target (float): the cumulative target.
        on_unrealized (func): a function called when the specified parameter
            will result in an unrealized disturbance. target - sum(target_var)
            is passed as the single parameter.

    Raises:
        ValueError: specified target was less than 0
        ValueError: less than zero values are detected in target_var

    Returns:
        pandas.DataFrame: a data frame with columns:

            - disturbed_indices: the zero based indices of the records that
                should be disturbed
            - area_proportion: the proportion of each disturbed index to
                disturb, 1 indicates the entire record, and < 1 indicates to
                disturb a proportion.
    """
    if target < 0:
        raise ValueError("target is less than zero")
    if (target_var < 0).any():
        raise ValueError("less than zero values detected in target_var")
    remaining_target = target
    result = pd.DataFrame(
        columns=[
            "target_var", "sort_var", "disturbed_indices",
            "area_proportions"])

    disturbed = pd.DataFrame({
        "target_var": target_var,
        "sort_var": sort_var})
    disturbed = disturbed.sort_values(by="sort_var", ascending=False)
    # filter out records that produced nothing towards the target
    disturbed = disturbed.loc[disturbed.target_var > 0]
    if disturbed.shape[0] == 0:
        if target > 0:
            on_unrealized(remaining_target)
        return result
    # compute the cumulative sums of the target var to compare versus the
    # target value
    disturbed["target_var_sums"] = disturbed["target_var"].cumsum()
    disturbed = disturbed.reset_index()

    fully_disturbed_records = disturbed[
        disturbed.target_var_sums <= target]

    if fully_disturbed_records.shape[0] > 0:
        remaining_target = \
            target - fully_disturbed_records["target_var_sums"].max()

    result = result.append(pd.DataFrame({
        "target_var": fully_disturbed_records["target_var"],
        "sort_var": fully_disturbed_records["sort_var"],
        "disturbed_indices": fully_disturbed_records["index"],
        "area_proportions":  np.ones(len(fully_disturbed_records["index"]))}))

    partial_disturb = disturbed[disturbed.target_var_sums > target]

    if partial_disturb.shape[0] > 0 and remaining_target > 0:
        # for merch C and area targets a final record is split to meet target
        # exactly
        split_record = partial_disturb.iloc[0]
        proportion = remaining_target / split_record["target_var"]
        remaining_target = 0

        result = result.append(
            pd.DataFrame({
                "target_var": split_record["target_var"],
                "sort_var": split_record["sort_var"],
                "disturbed_indices": split_record["index"],
                "area_proportions": [proportion]
            }))
    if remaining_target > 0:
        on_unrealized(remaining_target)
    return result


def sorted_area_target(area_target_value, sort_value, inventory, on_unrealized):
    """create a sorted sequence of areas/proportions for meeting an area
    target exactly.

    Args:
        area_target_value (float): the target area to disturb
        sort_value (pd.Series): a sequence of values whose decending sort
            defines the order to accumulate areas.  Length must equal the
            number of rows in the specified inventory
        inventory (pd.DataFrame): the inventory being targetted for
            disturbance.

    pandas.DataFrame: a data frame with columns:

        - disturbed_indices: the zero based indices of the records that
            should be disturbed in order to meet the area target exactly
        - area_proportion: the proportion of each disturbed index to
            disturb, 1 indicates the entire record, and < 1 indicates to
            disturb a proportion.
    """
    if inventory.shape[0] != sort_value.shape[0]:
        raise ValueError(
            "sort_value dimension must equal number of rows in inventory")
    return sorted_disturbance_target(
        target_var=inventory.area,
        sort_var=sort_value,
        target=area_target_value,
        on_unrealized=on_unrealized)


def sorted_merch_target(carbon_target, disturbance_production, inventory,
                        sort_value, efficiency, on_unrealized):
    """create a sorted sequence of areas/proportions for meeting a merch C
    target exactly.

    Args:
        carbon_target (float): a disturbance target in CBM mass units
            (tonnes C)
        disturbance_production (pandas.DataFrame): a table of Carbon
            generated by a disturbance events on the specified inventory.
            Used in accumulating value towards the carbon_target parameter.
            See :py:func:`compute_disturbance_production`
        inventory (pd.DataFrame): the inventory being targetted for
            disturbance.
        sort_value (pd.Series): a sequence of values whose decending sort
            defines the order to accumulate carbon mass.  Length must equal
            the number of rows in the specified inventory
        efficiency (float): reduce the disturbance production and split all
            records

    Returns:
        pandas.DataFrame: a data frame with columns:

            - disturbed_indices: the zero based indices of the records that
                should be disturbed in order to meet the carbon target exactly
            - area_proportion: the proportion of each disturbed index to
                disturb, 1 indicates the entire record, and < 1 indicates to
                disturb a proportion.
    """
    if inventory.shape[0] != sort_value.shape[0]:
        raise ValueError(
            "sort_value dimension must equal number of rows in inventory")
    if inventory.shape[0] != disturbance_production.shape[0]:
        raise ValueError(
            "number of disturbance_production rows must equal number of rows "
            "in inventory")
    production_c = disturbance_production.Total * inventory.area * efficiency
    result = sorted_disturbance_target(
        target_var=production_c,
        sort_var=sort_value,
        target=carbon_target,
        on_unrealized=on_unrealized)
    result.area_proportions = result.area_proportions * efficiency
    return result


def compute_disturbance_production(cbm, pools, inventory,
                                   disturbance_type, flux_indicator_codes):

    # this is by convention in the cbm_defaults database
    disturbance_op_process_id = 3

    # The number of stands is the number of rows in the inventory table.
    # The set of inventory here is assumed to be the eligible for disturbance
    # filtered subset of records
    n_stands = inventory.shape[0]

    # allocate space for computing the Carbon flows
    disturbance_op = cbm.compute_functions.AllocateOp(n_stands)

    # set the disturbance type for all records
    disturbance_type = pd.DataFrame({
        "disturbance_type": np.ones(n_stands) * disturbance_type})
    cbm.model_functions.GetDisturbanceOps(
        disturbance_op, inventory, disturbance_type)
    flux = cbm_variables.initialize_flux(n_stands, flux_indicator_codes)
    # compute the flux based on the specified disturbance type
    cbm.compute_functions.ComputeFlux(
        [disturbance_op], [disturbance_op_process_id],
        pools.copy(), flux, enabled=None)
    cbm.compute_functions.FreeOp(disturbance_op)
    # computes C harvested by applying the disturbance matrix to the specified
    # carbon pools
    return pd.DataFrame(data={
        "DisturbanceSoftProduction": flux["DisturbanceSoftProduction"],
        "DisturbanceHardProduction": flux["DisturbanceHardProduction"],
        "DisturbanceDOMProduction": flux["DisturbanceDOMProduction"],
        "Total":
            flux["DisturbanceSoftProduction"] +
            flux["DisturbanceHardProduction"] +
            flux["DisturbanceDOMProduction"]})
