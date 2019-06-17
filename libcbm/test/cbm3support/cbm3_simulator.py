from libcbm.test.cbm3support import cbm3_python_helper
cbm3_python_helper.load_cbm3_python()
from cbm3_python.simulation import projectsimulator
from cbm3_python.cbm3data import sit_helper
from cbm3_python.cbm3data import cbm3_results
from libcbm.test import casegeneration
import os
def get_project_path(toolbox_path, name):
    #creates a default path for a cbm project databases in the toolbox installation dir
    return os.path.join(toolbox_path, "Projects", "{}.mdb".format(name))


def get_results_path(project_path):
    #creates a default path for a cbm results database in the toolbox installation dir
    name = os.path.splitext(os.path.basename(project_path))[0]
    return os.path.join(os.path.dirname(project_path), "{}_results.mdb".format(name))


def get_config_path(toolbox_path, name):
    #creates a default path for a saving the SIT configuration
    cbm3_project_dir = os.path.dirname(get_project_path(toolbox_path, name))
    return os.path.join(cbm3_project_dir, "{}.json".format(name))


def import_cbm3_project(name, cases, age_interval, num_age_classes, nsteps, cbm_exe_path,
        toolbox_path, archive_index_db_path, cbm3_project_path=None, sit_config_save_path=None):

    standard_import_tool_plugin_path=sit_helper.load_standard_import_tool_plugin()

    #there is a bug fix in this version of cbm/makelist for growth increment blips
    #cbm_exe_path = r"M:\CBM Tools and Development\Builds\CBMBuilds\20190530_growth_increment_fix"

    if not cbm3_project_path:
        cbm3_project_path = get_project_path(toolbox_path, name)
    if not sit_config_save_path:
        sit_config_save_path = get_config_path(toolbox_path, name)

    sit_config = sit_helper.SITConfig(
        imported_project_path=cbm3_project_path,
        initialize_mapping=True,
        archive_index_db_path=archive_index_db_path
    )
    sit_config.data_config(
        age_class_size=age_interval,
        num_age_classes=num_age_classes,
        classifiers=["admin", "eco", "identifier", "species"])
    sit_config.set_admin_eco_mapping("admin","eco")
    sit_config.set_species_classifier("species")
    for c in cases:
        cset = [
            c["admin_boundary"],
            c["eco_boundary"],
            casegeneration.get_classifier_name(c["id"]),
            "Spruce"] #"Spruce" does not acutally matter here, since ultimately species composition is decided in yields
        sit_config.add_inventory(classifier_set=cset, area=c["area"],
            age=c["age"], unfccc_land_class=c["unfccc_land_class"],
            delay=c["delay"], historic_disturbance=c["historic_disturbance"],
            last_pass_disturbance=c["last_pass_disturbance"])
        for component in c["components"]:
            sit_config.add_yield(classifier_set=cset, 
                        leading_species_classifier_value=component["species"],
                        values=[x[1] for x in component["age_volume_pairs"]])
        for event in c["events"]:
            sit_config.add_event(
                classifier_set=cset,
                disturbance_type=event["disturbance_type"],
                time_step=event["time_step"],
                target=1, # not yet supporting disturbance rules here, meaning each event will target only a single stand
                target_type = "Area",
                sort = "SORT_BY_SW_AGE")
    sit_config.add_event(
        classifier_set=["?","?","?","?"],
        disturbance_type="Wildfire",
        time_step=nsteps+1,
        target=1,
        target_type = "Area",
        sort = "SORT_BY_SW_AGE")
    sit_config.import_project(standard_import_tool_plugin_path,
        sit_config_save_path)
    return cbm3_project_path


def run_cbm3(aidb_path, project_path, toolbox_path, cbm_exe_path,
    cbm3_results_db_path=None):
    if not cbm3_results_db_path:
        cbm3_results_db_path = get_results_path(project_path)
    projectsimulator.run(
        aidb_path=aidb_path,
        project_path=project_path,
        toolbox_installation_dir=toolbox_path,
        cbm_exe_path=cbm_exe_path,
        results_database_path = cbm3_results_db_path)
    return cbm3_results_db_path
    