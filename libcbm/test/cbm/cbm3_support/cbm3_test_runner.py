import os
import json
import shutil
import datetime
from types import SimpleNamespace
import pandas as pd
from libcbm.test.cbm.cbm3_support import cbm3_test_io

from libcbm.test.cbm.cbm3_support import cbm3_simulator


def get_default_cbm3_paths():
    """Gets default values for an install of CBM-CFS3

    Returns:
        tuple: a triple of strings for:
            1. toolbox_install_path
            2. cbm_exe_dir
            3. aidb_path strings

    """
    toolbox_install_path = os.path.join(
        "C:/", "Program Files (x86)", "Operational-Scale CBM-CFS3")
    cbm_exe_dir = os.path.join(toolbox_install_path, "Admin", "executables")
    aidb_path = os.path.join(
        toolbox_install_path, "Admin", "DBs", "ArchiveIndex_Beta_Install.mdb")
    return toolbox_install_path, cbm_exe_dir, aidb_path


def run_cases_cbm_cfs3(name, output_dir, cases, age_interval, num_age_classes,
                       n_steps):
    """run the specified test cases with CBM-CFS3, and save the result to the
    specified output_dir

    Args:
        name (str): the name of the test case
        output_dir (str): path where the results will be copied
        cases (list): test cases as generated by the test case generator.
            See: libcbm.test.cbm.casegeneration
        age_interval (int): the number of years between age points in yield
            curves
        num_age_classes (int): the number of age points in yield curves
        n_steps (int): the number of time steps being simulated
    """
    start = datetime.datetime.utcnow()
    toolbox_install_path, cbm3_exe_path, archive_index_db_path \
        = get_default_cbm3_paths()

    cbm3_project_path = cbm3_simulator.get_project_path(
        toolbox_install_path, name)
    sit_config_save_path = cbm3_simulator.get_config_path(
        toolbox_install_path, name)
    project_path = cbm3_simulator.import_cbm3_project(
        name="stand_level_testing",
        cases=cases,
        age_interval=age_interval,
        num_age_classes=num_age_classes,
        n_steps=n_steps,
        toolbox_path=toolbox_install_path,
        archive_index_db_path=archive_index_db_path,
        sit_config_save_path=sit_config_save_path,
        cbm3_project_path=cbm3_project_path)

    cbm3_results_path = cbm3_simulator.run_cbm3(
        archive_index_db_path=archive_index_db_path,
        project_path=project_path,
        toolbox_path=toolbox_install_path,
        cbm_exe_path=cbm3_exe_path)

    cbm3_result = cbm3_simulator.get_cbm3_results(cbm3_results_path)
    end = datetime.datetime.utcnow()
    date_format = "%Y%m%d-%H:%M:%S UTC"
    cbm3_test_io.save_cbm_cfs3_test(
        name, output_dir, start.strftime(date_format),
        end.strftime(date_format), (end-start).total_seconds(),
        cbm3_project_path, cbm3_results_path, age_interval, num_age_classes,
        n_steps, cases, toolbox_install_path, cbm3_exe_path,
        archive_index_db_path, cbm3_result)